"""The document library: derived from passages, rebuilt when the corpus changes."""

from conftest import FAKE_DB

from sourcebook.api.limiter import limiter
from sourcebook.api.routes.documents import _preview
from sourcebook.rag.cache import get_corpus_version


def _seed_passages(*docs: tuple[str, str, str, int]):
    """(source, title, category, chunk count) tuples, with a heading in chunk 0."""
    for source, title, category, count in docs:
        for i in range(count):
            FAKE_DB["passages"].insert_one(
                {
                    "source": source,
                    "doc_id": source.split("/")[-1][:-3],
                    "title": title,
                    "category": category,
                    "owner": None,
                    "effective_date": None,
                    "chunk_index": i,
                    "text": f"# {title}\nParagraph {i} of {title}. " + "words " * 60,
                    "embedding": [0.0] * 4,
                }
            )


def test_preview_skips_headings_and_cuts_on_a_word():
    assert _preview("# Heading\n\nShort body.") == "Short body."
    long = _preview("# H\n" + "word " * 100)
    assert len(long) <= 201 and long.endswith("…") and not long.endswith(" …")


def test_library_is_built_from_passages_without_vectors(client, auth):
    _seed_passages(
        ("documents/pto.md", "PTO", "Leave", 3), ("documents/expenses.md", "Expenses", "Finance", 2)
    )

    body = client.get("/api/documents", headers=auth).json()
    assert body["total"] == 2
    assert [d["title"] for d in body["items"]] == ["Expenses", "PTO"]
    pto = body["items"][1]
    assert pto["passage_count"] == 3
    assert pto["preview"].startswith("Paragraph 0 of PTO.")
    assert "embedding" not in pto

    assert client.get("/api/documents/categories", headers=auth).json() == ["Finance", "Leave"]


def test_search_and_filters_and_paging(client, auth):
    _seed_passages(("documents/a.md", "Alpha (x)", "One", 1), ("documents/b.md", "Beta", "Two", 1))

    assert client.get("/api/documents", params={"q": "(x)"}, headers=auth).json()["total"] == 1
    assert client.get("/api/documents", params={"q": "ALPHA"}, headers=auth).json()["total"] == 1
    assert (
        client.get("/api/documents", params={"category": "Two"}, headers=auth).json()["items"][0][
            "title"
        ]
        == "Beta"
    )
    page = client.get("/api/documents", params={"limit": 1, "skip": 1}, headers=auth).json()
    assert page["total"] == 2 and [d["title"] for d in page["items"]] == ["Beta"]
    assert len(client.get("/api/documents", params={"limit": 0}, headers=auth).json()["items"]) == 1


def test_passages_are_returned_in_order(client, auth):
    _seed_passages(("documents/pto.md", "PTO", "Leave", 3))
    texts = client.get(
        "/api/documents/passages", params={"source": "documents/pto.md"}, headers=auth
    ).json()
    assert [t.split("\n")[1][:11] for t in texts] == ["Paragraph 0", "Paragraph 1", "Paragraph 2"]
    assert (
        client.get("/api/documents/passages", params={"source": "nope"}, headers=auth).status_code
        == 404
    )


def test_body_is_served_whole_and_only_to_signed_in_users(client, auth):
    _seed_passages(("documents/pto.md", "PTO", "Leave", 3))
    FAKE_DB["document_bodies"].insert_one(
        {
            "source": "documents/pto.md",
            "doc_id": "pto",
            "title": "PTO",
            "category": "Leave",
            "owner": None,
            "effective_date": None,
            "body": "## Overview\n\nFull-time employees **accrue** 15 days.",
        }
    )

    response = client.get(
        "/api/documents/body", params={"source": "documents/pto.md"}, headers=auth
    )
    assert response.status_code == 200
    assert response.json() == {
        "source": "documents/pto.md",
        "body": "## Overview\n\nFull-time employees **accrue** 15 days.",
    }

    # Indexed before bodies were stored: passages exist, the reading copy does not.
    FAKE_DB["document_bodies"].delete_many({})
    missing = client.get("/api/documents/body", params={"source": "documents/pto.md"}, headers=auth)
    assert missing.status_code == 404
    assert "re-run ingestion" in missing.json()["detail"]
    unknown = client.get("/api/documents/body", params={"source": "nope"}, headers=auth)
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Document not found."
    assert (
        client.get("/api/documents/body", params={"source": "documents/pto.md"}).status_code == 401
    )


def test_reingestion_rebuilds_the_library_once(client, auth, hr_auth):
    _seed_passages(("documents/pto.md", "PTO", "Leave", 1))
    assert client.get("/api/documents", headers=auth).json()["total"] == 1

    # A stale library is served until the corpus version moves.
    FAKE_DB["passages"].delete_many({})
    _seed_passages(("documents/new.md", "New", "Leave", 1))
    assert [d["title"] for d in client.get("/api/documents", headers=auth).json()["items"]] == [
        "PTO"
    ]

    before = get_corpus_version()
    result = client.post("/api/documents/reindex", headers=hr_auth).json()
    assert result["documents"] == 1 and result["corpus_version"] != before
    assert [d["title"] for d in client.get("/api/documents", headers=auth).json()["items"]] == [
        "New"
    ]


def test_empty_corpus(client, auth, hr_auth):
    _seed_passages(("documents/pto.md", "PTO", "Leave", 1))
    assert client.get("/api/documents", headers=auth).json()["total"] == 1

    FAKE_DB["passages"].delete_many({})
    before = get_corpus_version()
    result = client.post("/api/documents/reindex", headers=hr_auth).json()

    assert result["ok"] is True
    assert result["documents"] == 0
    assert result["corpus_version"] != before
    assert client.get("/api/documents", headers=auth).json() == {"items": [], "total": 0}
    assert client.get("/api/documents/categories", headers=auth).json() == []
    assert client.post("/api/documents/reindex", headers=hr_auth).json()["documents"] == 0


def test_reindex_rate_limited_per_client(client, hr_auth):
    limiter.enabled = True
    limiter.reset()
    statuses = [
        client.post("/api/documents/reindex", headers=hr_auth).status_code for _ in range(3)
    ]
    assert statuses == [200, 200, 429]


def test_reindex_is_for_hr_only(client, auth):
    # A rebuild drops every cached answer, so an employee session cannot start one.
    before = get_corpus_version()
    response = client.post("/api/documents/reindex", headers=auth)
    assert response.status_code == 403
    assert get_corpus_version() == before
