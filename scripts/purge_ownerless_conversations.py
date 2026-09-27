"""Delete conversations and projects stored before owners existed (#300).

Since #299 every conversation and project carries the owner id of the browser
that made it, and every route filters on it. Records from before that have no
``owner``, so no session can list, open, or delete them, but they still hold
the questions employees typed. This script removes them.

It changes nothing unless ``--delete`` is given. Without it, it prints how many
records would go. Escalation records are left alone: they copy the question and
answer they were filed from, and HR Requests reads only them.

    .venv/bin/python -m scripts.purge_ownerless_conversations
    .venv/bin/python -m scripts.purge_ownerless_conversations --delete

Do not run it against production without an explicit operations decision.
"""

import argparse

from dotenv import load_dotenv

# Before the db import: sourcebook.api.db opens its collections at import, so
# MONGODB_URI has to be in the environment by then. On the pilot host it is
# only in .env, and loading it after the import failed there on 2026-09-27.
load_dotenv()

from sourcebook.api.db import conversations_col, projects_col  # noqa: E402

OWNERLESS = {"owner": {"$exists": False}}


def purge_ownerless(*, delete: bool) -> dict[str, int]:
    """Count, and with ``delete`` remove, the records that have no owner."""
    if not delete:
        return {
            "conversations": conversations_col.count_documents(OWNERLESS),
            "projects": projects_col.count_documents(OWNERLESS),
        }
    # Conversations first: an owned conversation can only be assigned to an
    # owned project, so no project deleted here is still in use.
    return {
        "conversations": conversations_col.delete_many(OWNERLESS).deleted_count,
        "projects": projects_col.delete_many(OWNERLESS).deleted_count,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Delete conversations and projects that have no owner."
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="delete them; without this flag the script only counts",
    )
    args = parser.parse_args(argv)

    result = purge_ownerless(delete=args.delete)
    counts = f"{result['conversations']} conversations and {result['projects']} projects"
    if args.delete:
        print(f"Deleted {counts} with no owner.")
    else:
        print(f"{counts} have no owner. Nothing changed; pass --delete to remove them.")


if __name__ == "__main__":
    main()
