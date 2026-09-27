"""Concurrent load against the deployed pilot, with the real model and a spend cap.

    BENCH_PASSWORD=... ./.venv/bin/python scripts/loadtest/pilot_load.py \\
        --url https://sourcebook.duckdns.org --levels 5 10 20 40 \\
        --deployed-sha <sha> --setting CHAT_RATE_LIMIT=600/minute \\
        --setting CACHE_ENABLED=0 --out docs/releases/v1.0.0/evidence/pilot-load.json

run.py finds the thread-pool ceiling with the model faked on a laptop.
live_benchmark.py times a handful of requests against the pilot, one path at a
time. This script sits between them (issue #212): the deployed stack (Caddy ->
Nginx -> one API worker, real OpenAI and Atlas) at a few concurrency levels, so
the capacity claim rests on a measured run of the system people use.

Every request can cost money, so the run is bounded before it starts. The
levels must fit under --max-requests, the operator confirms the estimated cost,
and a level with --max-errors or more failures ends the run. Each level sends
that many first-turn questions at once from the answerable tier (the same pool
as live_benchmark.py), each in its own session.

Two pilot settings decide what this measures, and the report records them as
the operator passes them with --setting:

- CHAT_RATE_LIMIT is per client address, so from one client the default
  30/minute caps the whole run. Raise it for the run window, then restore it.
  A 429 is counted on its own, never as a failed answer.
- The answer cache serves a repeated first-turn question without a model call.
  With CACHE_ENABLED=0 for the window every request generates, which is the
  worst case. Left on, the report shows the mix of paths it got.

Throughput is completed requests over the time from the level's start to its
last `done` event, the definition run.py uses. The stream stays open after
`done` for the follow-up suggestions, a second model call; the time including
them is kept as a separate field.

Each answered request leaves a conversation on the pilot, and the pilot lists
every conversation to every user. When the run ends, however it ends, the
script deletes the conversations it created (--keep-conversations skips this).
Its query_logs rows need a step on the host; the page has it.

The report is written after every level, so an interrupted run still leaves
evidence. docs/load-testing-demo.md has the protocol and the results. Answer
text, the password, and the token are never stored, so the report is safe to
commit.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import platform
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from scripts.loadtest.live_benchmark import (
    DEFAULT_COST_PER_GENERATION_USD,
    PATH_ERROR,
    PATH_GENERATED,
    PATH_RATE_LIMITED,
    QUESTION_POOL,
    Record,
    Step,
    _fmt,
    _stream_url,
    fetch_token,
    pct,
    run_step,
)

DEFAULT_LEVELS = [5, 10, 20, 40]
DEFAULT_MAX_REQUESTS = 80
# Seconds between levels, so one level's tail does not overlap the next.
DEFAULT_SETTLE_S = 10.0

Sender = Callable[[Step], Awaitable[Record]]


def planned_requests(levels: list[int]) -> int:
    return sum(levels)


def level_steps(run_id: str, concurrency: int) -> list[Step]:
    """One first-turn question per virtual user, each in a session of its own."""
    return [
        Step(
            name=f"c{concurrency} #{i + 1}",
            question=QUESTION_POOL[i % len(QUESTION_POOL)],
            session_id=f"load-{run_id}-c{concurrency}-{i}",
            expected=PATH_GENERATED,
        )
        for i in range(concurrency)
    ]


def summarize_level(
    concurrency: int, records: list[Record], to_last_done_s: float, wall_s: float | None = None
) -> dict:
    """What one level did. Latency is over generated answers only, so a cache hit
    or a refusal does not flatter the numbers; the path counts show the mix.
    Throughput runs to the last `done`; wall_s also includes the follow-ups."""
    by_path: dict[str, int] = {}
    for r in records:
        by_path[r.observed] = by_path.get(r.observed, 0) + 1
    generated = [r for r in records if r.observed == PATH_GENERATED]
    ttft = [r.ttft_s for r in generated if r.ttft_s is not None]
    total = [r.total_s for r in generated if r.total_s is not None]
    rate_limited = by_path.get(PATH_RATE_LIMITED, 0)
    errors = by_path.get(PATH_ERROR, 0)
    answered = len(records) - rate_limited
    completed = answered - errors
    error_kinds: dict[str, int] = {}
    for r in records:
        if r.observed == PATH_ERROR:
            key = r.error or "unknown"
            error_kinds[key] = error_kinds.get(key, 0) + 1
    return {
        "concurrency": concurrency,
        "requests": len(records),
        "by_path": by_path,
        "completed": completed,
        "rate_limited": rate_limited,
        "errors": errors,
        "error_rate": errors / answered if answered else 0.0,
        "error_kinds": error_kinds,
        "to_last_done_s": to_last_done_s,
        "wall_incl_follow_ups_s": wall_s if wall_s is not None else to_last_done_s,
        "throughput_rps": completed / to_last_done_s if to_last_done_s else 0.0,
        "generated_ttft_s": {
            "n": len(ttft),
            "p50": pct(ttft, 50),
            "p95": pct(ttft, 95),
            "max": max(ttft, default=None),
        },
        "generated_total_s": {
            "n": len(total),
            "p50": pct(total, 50),
            "p95": pct(total, 95),
            "max": max(total, default=None),
        },
    }


async def _send_level(send: Sender, steps: list[Step]) -> tuple[list[Record], float, float]:
    """Send one level at once. Returns the records, the time to the last `done`
    (or error), and the wall time, which also covers the follow-up suggestions."""
    started = time.perf_counter()
    done_at: list[float] = []

    async def timed(step: Step) -> Record:
        sent = time.perf_counter()
        record = await send(step)
        # total_s stops at `done` (or the error), not at the follow-ups.
        if record.total_s is not None:
            done_at.append(sent - started + record.total_s)
        return record

    batch = await asyncio.gather(*[timed(step) for step in steps])
    wall = time.perf_counter() - started
    return list(batch), max(done_at, default=wall), wall


async def run_levels(
    send: Sender,
    run_id: str,
    levels: list[int],
    max_errors: int,
    settle_s: float = DEFAULT_SETTLE_S,
    log: Callable[[list[dict], list[Record]], None] = lambda levels, records: None,
) -> tuple[list[dict], list[Record]]:
    """Each level in turn, all of its requests at once. A level with max_errors or
    more errors ends the run: the system is failing, and more load only costs.
    Rate limiting (429) is not an error and does not stop the run.

    `log` gets the levels and records so far after each level."""
    levels_out: list[dict] = []
    records: list[Record] = []
    for index, concurrency in enumerate(levels):
        if index:
            await asyncio.sleep(settle_s)
        batch, to_last_done, wall = await _send_level(send, level_steps(run_id, concurrency))
        summary = summarize_level(concurrency, batch, to_last_done, wall)
        records.extend(batch)
        levels_out.append(summary)
        log(levels_out, records)
        if summary["errors"] >= max_errors:
            break
    return levels_out, records


def _conversation_url(base_url: str, session_id: str) -> str:
    parts = urlsplit(base_url)
    path = "/api/conversations/" + quote(session_id, safe="")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


async def delete_conversations(
    client: httpx.AsyncClient, base_url: str, token: str, session_ids: list[str]
) -> dict:
    """Delete the conversations the run created. A 404 is a request that never
    persisted one (rate limited, or failed before the answer), not a failure."""
    counts = {"deleted": 0, "not_found": 0, "failed": 0}
    for session_id in session_ids:
        try:
            response = await client.delete(
                _conversation_url(base_url, session_id),
                headers={"Authorization": f"Bearer {token}"},
                timeout=30.0,
            )
        except httpx.HTTPError:
            counts["failed"] += 1
            continue
        if response.status_code == 200:
            counts["deleted"] += 1
        elif response.status_code == 404:
            counts["not_found"] += 1
        else:
            counts["failed"] += 1
    return counts


def write_report(path: str, report: dict) -> None:
    """Replace the report in one step, so a crash mid-write leaves the last good one."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    os.replace(tmp, path)


def render_markdown(levels: list[dict], cost_per_generation: float) -> str:
    """The results table for docs/load-testing-demo.md."""
    columns = [
        "Concurrent",
        "Completed",
        "Generated / cached / refused",
        "429",
        "Errors",
        "req/s",
        "TTFT p50",
        "TTFT p95",
        "Total p50",
        "Total p95",
    ]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for level in levels:
        paths = level["by_path"]
        ttft = level["generated_ttft_s"]
        total = level["generated_total_s"]
        lines.append(
            f"| {level['concurrency']} | {level['completed']} "
            f"| {paths.get('generated', 0)} / {paths.get('cached', 0)} / {paths.get('refused', 0)} "
            f"| {level['rate_limited']} | {level['errors']} | {level['throughput_rps']:.2f} "
            f"| {_fmt(ttft['p50'])} | {_fmt(ttft['p95'])} | {_fmt(total['p50'])} | {_fmt(total['p95'])} |"
        )
    generated = sum(level["by_path"].get(PATH_GENERATED, 0) for level in levels)
    requests = sum(level["requests"] for level in levels)
    lines += ["", f"Requests: {requests}. Estimated cost: ${generated * cost_per_generation:.2f}."]
    kinds: dict[str, int] = {}
    for level in levels:
        for kind, count in level["error_kinds"].items():
            kinds[kind] = kinds.get(kind, 0) + count
    if kinds:
        lines.append(
            "Errors: " + "; ".join(f"{count} x {kind}" for kind, count in kinds.items()) + "."
        )
    return "\n".join(lines)


def parse_settings(pairs: list[str]) -> dict[str, str]:
    settings: dict[str, str] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise ValueError(f"--setting expects KEY=VALUE, got {pair!r}")
        settings[key] = value
    return settings


async def run(args: argparse.Namespace, password: str) -> dict:
    run_id = uuid.uuid4().hex[:8]
    token = fetch_token(args.url, password)
    url = _stream_url(args.url)
    print(f"\n  pilot load -> {args.url}  (run id {run_id}, levels {args.levels})\n")

    report = {
        "run_id": run_id,
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "url": args.url,
        "label": args.label,
        "deployed_sha": args.deployed_sha or None,
        "pilot_settings": parse_settings(args.setting),
        "client": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "location": args.client_location,
        },
        "plan": {
            "levels": args.levels,
            "max_requests": args.max_requests,
            "max_errors": args.max_errors,
            "settle_s": args.settle,
            "cost_per_generation_usd": args.cost_per_generation,
        },
        "levels": [],
        "records": [],
        "cleanup": None,
        "complete": False,
    }

    def save(levels: list[dict], records: list[Record]) -> None:
        report["levels"] = levels
        report["records"] = [asdict(r) for r in records]
        if args.out:
            write_report(args.out, report)

    def show(levels: list[dict], records: list[Record]) -> None:
        level = levels[-1]
        ttft = level["generated_ttft_s"]
        print(
            f"  {level['concurrency']:>4} concurrent  {level['completed']:>3} completed  "
            f"{level['rate_limited']:>3} x 429  {level['errors']:>3} errors  "
            f"{level['throughput_rps']:6.2f} req/s  TTFT p50 {_fmt(ttft['p50'])} p95 {_fmt(ttft['p95'])}"
        )
        save(levels, records)

    sent_sessions: list[str] = []
    limits = httpx.Limits(max_connections=max(args.levels) + 10)
    async with httpx.AsyncClient(limits=limits) as client:

        async def send(step: Step) -> Record:
            sent_sessions.append(step.session_id)
            record = await run_step(client, url, token, step)
            record.answer = None
            return record

        try:
            levels, _ = await run_levels(
                send, run_id, args.levels, args.max_errors, args.settle, log=show
            )
            report["complete"] = True
        finally:
            # Runs on an error or Ctrl-C too: the pilot lists every conversation
            # to every user, so the run's own must not outlive it.
            if not args.keep_conversations and sent_sessions:
                report["cleanup"] = await delete_conversations(
                    client, args.url, token, sent_sessions
                )
                print(f"  conversations cleaned up: {report['cleanup']}")
            if args.out:
                write_report(args.out, report)

    print("\n" + render_markdown(levels, args.cost_per_generation) + "\n")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--url", default="https://sourcebook.duckdns.org")
    parser.add_argument(
        "--levels",
        type=int,
        nargs="+",
        default=DEFAULT_LEVELS,
        help="Concurrent requests per level, run in order.",
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=DEFAULT_MAX_REQUESTS,
        help="Hard cap on chat requests. The run refuses to start if the levels add up to more.",
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=5,
        help="End the run after a level with this many errors or more.",
    )
    parser.add_argument(
        "--settle", type=float, default=DEFAULT_SETTLE_S, help="Seconds between levels."
    )
    parser.add_argument(
        "--cost-per-generation", type=float, default=DEFAULT_COST_PER_GENERATION_USD
    )
    parser.add_argument(
        "--setting",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="A pilot setting in force for the run, recorded in the report. Repeat per setting.",
    )
    parser.add_argument("--deployed-sha", default="", help="Full SHA the pilot is running.")
    parser.add_argument(
        "--client-location", default="", help="Where the client ran, e.g. 'home, Maryland'."
    )
    parser.add_argument("--label", default="")
    parser.add_argument(
        "--keep-conversations",
        action="store_true",
        help="Leave the run's conversations on the pilot instead of deleting them at the end.",
    )
    parser.add_argument(
        "--out", default="", help="Write the JSON report here, after every level and at the end."
    )
    parser.add_argument("--yes", action="store_true", help="Skip the paid-run confirmation.")
    return parser.parse_args(argv)


def validate(args: argparse.Namespace) -> str | None:
    """Why the plan cannot run, or None."""
    if not args.levels or min(args.levels) < 1:
        return "--levels must be positive"
    if args.max_errors < 1:
        return "--max-errors must be at least 1"
    planned = planned_requests(args.levels)
    if planned > args.max_requests:
        return (
            f"the levels add up to {planned} requests, over --max-requests {args.max_requests}; "
            "drop a level or raise the cap"
        )
    try:
        parse_settings(args.setting)
    except ValueError as exc:
        return str(exc)
    if args.out:
        # Checked before the paid run, not after it.
        directory = os.path.dirname(os.path.abspath(args.out))
        if not os.path.isdir(directory) or not os.access(directory, os.W_OK):
            return f"cannot write --out {args.out!r}: {directory} is missing or not writable"
    return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    problem = validate(args)
    if problem:
        print(problem, file=sys.stderr)
        return 2
    try:
        password = os.environ.get("BENCH_PASSWORD") or getpass.getpass("Pilot password: ")
    except EOFError:
        password = ""
    if not password:
        print("a password is required (BENCH_PASSWORD or the prompt)", file=sys.stderr)
        return 2
    planned = planned_requests(args.levels)
    if not args.yes:
        cost = planned * args.cost_per_generation
        try:
            answer = input(
                f"This sends up to {planned} paid chat requests to {args.url} "
                f"(an estimate of ${cost:.2f} if all generate; the request count is the "
                f"hard bound). Continue? [y/N] "
            )
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("aborted")
            return 1
    try:
        report = asyncio.run(run(args, password))
    except httpx.HTTPError as exc:
        print(f"login or connection failed before any chat request: {exc}", file=sys.stderr)
        return 2
    if args.out:
        print(f"  wrote {args.out}")
    # 1 when any level had errors, including the 503s the top level is expected
    # to produce once the provider bound is reached. See the page.
    return 0 if not any(level["errors"] for level in report["levels"]) else 1


if __name__ == "__main__":
    sys.exit(main())
