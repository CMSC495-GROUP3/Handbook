"""A minimal in-memory stand-in for the pymongo collection API.

Covers only the operations this application actually performs. It is
deliberately partial — a fake that is obviously incomplete is safer than one
that looks complete and diverges under conditions nobody tested.

Shared by the load-test server and the cache/analytics checks so both exercise
the same behaviour.
"""

from __future__ import annotations

import copy
import itertools
from typing import Any


def _matches(doc: dict, query: dict) -> bool:
    """Support the handful of query forms used in this codebase."""
    for field, condition in query.items():
        if field == "$or":
            if not any(_matches(doc, branch) for branch in condition):
                return False
            continue
        if field == "$and":
            if not all(_matches(doc, branch) for branch in condition):
                return False
            continue
        value = doc.get(field)
        if isinstance(condition, dict):
            for op, operand in condition.items():
                if op == "$exists" and (field in doc) is not bool(operand):
                    return False
                if op == "$nin" and value in operand:
                    return False
                if op == "$in" and value not in operand:
                    return False
                if op == "$gte" and not (value is not None and value >= operand):
                    return False
                if op == "$lt" and not (value is not None and value < operand):
                    return False
                if op == "$lte" and not (value is not None and value <= operand):
                    return False
                if op == "$gt" and not (value is not None and value > operand):
                    return False
                if op == "$regex":
                    import re as _re

                    flags = _re.IGNORECASE if "i" in condition.get("$options", "") else 0
                    if value is None or not _re.search(operand, str(value), flags):
                        return False
        elif value != condition:
            return False
    return True


def _project(doc: dict, projection: dict | None) -> dict:
    if not projection:
        return copy.deepcopy(doc)
    excludes = {k for k, v in projection.items() if v == 0}
    includes = {k for k, v in projection.items() if v == 1}
    out = {}
    for key, value in doc.items():
        if key in excludes:
            continue
        if includes and key not in includes and key != "_id":
            continue
        out[key] = copy.deepcopy(value)
    if "_id" in excludes:
        out.pop("_id", None)
    return out


def _set_path(doc: dict, path: str, value: Any) -> None:
    """Assign through a dotted path, so "messages.3.flag" reaches into the
    list the way Mongo's positional update does."""
    parts = path.split(".")
    target: Any = doc
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target.setdefault(part, {})
    last = parts[-1]
    if isinstance(target, list):
        target[int(last)] = value
    else:
        target[last] = value


def _apply_update(doc: dict, update: dict, inserted: bool) -> None:
    for field, value in update.get("$set", {}).items():
        _set_path(doc, field, value)
    for field, value in update.get("$inc", {}).items():
        doc[field] = doc.get(field, 0) + value
    for field, spec in update.get("$push", {}).items():
        doc.setdefault(field, []).extend(spec.get("$each", [spec]))
    if inserted:
        for field, value in update.get("$setOnInsert", {}).items():
            doc.setdefault(field, value)


_MISSING = object()


def _field(doc: dict, path: str) -> Any:
    """Follow a dotted path ("_id.hash"); _MISSING if any step is absent."""
    value: Any = doc
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return _MISSING
        value = value[part]
    return value


def _is_missing(doc: dict, expr: Any) -> bool:
    """True when expr is a field path the document does not have."""
    return isinstance(expr, str) and expr.startswith("$") and _field(doc, expr[1:]) is _MISSING


def _resolve(doc: dict, expr: Any) -> Any:
    """A field path ("$refused", "$_id.hash"), {"$eq": [a, b]},
    {"$cond": [if, then, else]}, {"$size": array}, {"$slice": [array, n]} with
    n >= 0, an object of expressions
    ({"hash": "$question_hash"}), or a literal."""
    if isinstance(expr, str) and expr.startswith("$"):
        value = _field(doc, expr[1:])
        return None if value is _MISSING else value
    if isinstance(expr, dict) and "$size" in expr:
        return len(_resolve(doc, expr["$size"]))
    if isinstance(expr, dict) and "$slice" in expr:
        array, n = expr["$slice"]
        return _resolve(doc, array)[:n]
    if isinstance(expr, dict) and "$eq" in expr:
        left, right = expr["$eq"]
        return _resolve(doc, left) == _resolve(doc, right)
    if isinstance(expr, dict) and "$cond" in expr:
        condition, then, otherwise = expr["$cond"]
        return _resolve(doc, then if _resolve(doc, condition) else otherwise)
    if isinstance(expr, dict) and not any(key.startswith("$") for key in expr):
        # Mongo leaves a field out of the object when its path is missing,
        # so {"s": "$absent"} is {} but {"s": "$stored_null"} is {"s": None}.
        return {key: _resolve(doc, sub) for key, sub in expr.items() if not _is_missing(doc, sub)}
    return expr


def _hashable(value: Any) -> Any:
    """A dict key for a group _id. Field order counts, as it does in Mongo."""
    if isinstance(value, dict):
        return tuple((key, _hashable(sub)) for key, sub in value.items())
    if isinstance(value, list):
        return tuple(_hashable(item) for item in value)
    return value


def _group(rows: list[dict], spec: dict) -> list[dict]:
    """$group with $sum, $first and $addToSet, the accumulators the coverage report uses.

    _id may be a field path or an object of them, and groups come out in the
    order their first row went in.
    """
    groups: dict[Any, dict] = {}
    for row in rows:
        key = _resolve(row, spec["_id"])
        slot = _hashable(key)
        is_new = slot not in groups
        group = groups.setdefault(slot, {"_id": key})
        for field, accumulator in spec.items():
            if field == "_id":
                continue
            (op, expr), *_ = accumulator.items()
            if op == "$sum":
                value = _resolve(row, expr)
                # Mongo's $sum skips non-numbers, booleans included.
                numeric = isinstance(value, int | float) and not isinstance(value, bool)
                group[field] = group.get(field, 0) + (value if numeric else 0)
            elif op == "$first":
                if is_new:
                    group[field] = _resolve(row, expr)
            elif op == "$addToSet":
                members = group.setdefault(field, [])
                # A missing field adds nothing; a stored null is a member, as in Mongo.
                value = _resolve(row, expr)
                if not _is_missing(row, expr) and value not in members:
                    members.append(value)
            else:
                raise NotImplementedError(f"FakeCollection $group does not implement {op}.")
    return list(groups.values())


class _Cursor:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    def sort(self, key, direction=1):
        if isinstance(key, list):
            for field, dirn in reversed(key):
                self._docs.sort(
                    key=lambda d: (d.get(field) is None, d.get(field)), reverse=dirn < 0
                )
        else:
            self._docs.sort(key=lambda d: (d.get(key) is None, d.get(key)), reverse=direction < 0)
        return self

    def skip(self, n):
        self._docs = self._docs[n:]
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


class FakeCollection:
    def __init__(self, name: str = ""):
        self.name = name
        self._docs: list[dict] = []
        self._ids = itertools.count(1)

    # ── reads ────────────────────────────────────────────────────────────────
    def find_one(self, query: dict, projection: dict | None = None):
        for doc in self._docs:
            if _matches(doc, query):
                return _project(doc, projection)
        return None

    def find(self, query: dict | None = None, projection: dict | None = None):
        return _Cursor([_project(d, projection) for d in self._docs if _matches(d, query or {})])

    def count_documents(self, query: dict, **kwargs) -> int:
        return sum(1 for d in self._docs if _matches(d, query))

    def distinct(self, field: str):
        return list({d.get(field) for d in self._docs})

    # ── writes ───────────────────────────────────────────────────────────────
    def insert_one(self, doc: dict):
        doc = copy.deepcopy(doc)
        doc.setdefault("_id", next(self._ids))
        self._docs.append(doc)
        return type("R", (), {"inserted_id": doc["_id"]})()

    def insert_many(self, docs: list[dict]):
        for d in docs:
            self.insert_one(d)

    def update_one(self, query: dict, update: dict, upsert: bool = False):
        for doc in self._docs:
            if _matches(doc, query):
                _apply_update(doc, update, inserted=False)
                return type("R", (), {"matched_count": 1, "modified_count": 1})()
        if upsert:
            doc = {k: v for k, v in query.items() if not isinstance(v, dict)}
            doc.setdefault("_id", next(self._ids))
            _apply_update(doc, update, inserted=True)
            self._docs.append(doc)
            return type("R", (), {"matched_count": 0, "modified_count": 0})()
        return type("R", (), {"matched_count": 0, "modified_count": 0})()

    def find_one_and_update(
        self, query: dict, update: dict, upsert: bool = False, return_document: Any = True, **kwargs
    ):
        for doc in self._docs:
            if _matches(doc, query):
                _apply_update(doc, update, inserted=False)
                return copy.deepcopy(doc)
        if upsert:
            doc = {k: v for k, v in query.items() if not isinstance(v, dict)}
            doc.setdefault("_id", next(self._ids))
            _apply_update(doc, update, inserted=True)
            self._docs.append(doc)
            return copy.deepcopy(doc)
        return None

    def update_many(self, query: dict, update: dict):
        for doc in self._docs:
            if _matches(doc, query):
                _apply_update(doc, update, inserted=False)

    def delete_one(self, query: dict):
        for i, doc in enumerate(self._docs):
            if _matches(doc, query):
                del self._docs[i]
                return type("R", (), {"deleted_count": 1})()
        return type("R", (), {"deleted_count": 0})()

    def delete_many(self, query: dict):
        before = len(self._docs)
        self._docs = [d for d in self._docs if not _matches(d, query)]
        return type("R", (), {"deleted_count": before - len(self._docs)})()

    def bulk_write(self, operations):
        for op in operations:
            self.update_one(op._filter, op._doc, upsert=op._upsert)

    def create_index(self, *args, **kwargs):
        return "index"

    def drop_index(self, name):
        return None

    def aggregate(self, pipeline, **kwargs):
        """The $match / $group / $addFields / $project / $sort / $limit subset
        the coverage report runs.

        Any other stage raises. $vectorSearch in particular is Atlas-only and
        cannot be emulated meaningfully.
        """
        rows = [copy.deepcopy(d) for d in self._docs]
        for stage in pipeline:
            (op, spec), *_ = stage.items()
            if op == "$match":
                rows = [r for r in rows if _matches(r, spec)]
            elif op == "$group":
                rows = _group(rows, spec)
            elif op == "$sort":
                # Null sorts first ascending and last descending, as in Mongo.
                for field, direction in reversed(spec.items()):
                    rows.sort(
                        key=lambda r: (r.get(field) is not None, r.get(field)),
                        reverse=direction < 0,
                    )
            elif op == "$addFields":
                rows = [{**r, **{f: _resolve(r, e) for f, e in spec.items()}} for r in rows]
            elif op == "$project":
                if any(v != 0 for v in spec.values()):
                    raise NotImplementedError("FakeCollection $project supports exclusion only.")
                rows = [{k: v for k, v in r.items() if k not in spec} for r in rows]
            elif op == "$limit":
                rows = rows[:spec]
            else:
                raise NotImplementedError(f"FakeCollection.aggregate does not implement {op}.")
        return iter(rows)


class FakeDB:
    """Dict of collections, created on demand."""

    def __init__(self):
        self._collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self._collections.setdefault(name, FakeCollection(name))

    def reset(self):
        self._collections.clear()
