"""Ingestion — chunk, embed, and store the policy corpus.

Run once after the documents are in S3, and again whenever they change:

    python -m sourcebook.rag.embed_documents

This is the "embed documents once into Atlas" half of the design. Nothing here
runs at query time.
"""

import os
import sys

import boto3
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

from sourcebook.rag.cache import bump_corpus_version
from sourcebook.rag.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DOCUMENT_BODIES_COLLECTION,
    PASSAGES_COLLECTION,
    S3_DOCUMENT_PREFIX,
)
from sourcebook.rag.documents import document_record, parse_document, passage_records
from sourcebook.rag.llm import get_provider
from sourcebook.rag.mongo import get_collection

load_dotenv()

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
)
# Splits on paragraph, then line, then sentence boundaries before resorting to a
# hard character cut, so a chunk usually ends somewhere meaningful. The overlap
# keeps a clause that straddles a boundary intact in at least one chunk.
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)


def fetch_documents_from_s3() -> list[tuple[str, str]]:
    """Return (key, contents) for every document under the configured prefix."""
    bucket = os.getenv("S3_BUCKET_NAME")
    if not bucket:
        sys.exit("S3_BUCKET_NAME is not set. Copy .env.example to .env and fill it in.")

    documents: list[tuple[str, str]] = []
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=S3_DOCUMENT_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue  # directory placeholder
            # utf-8-sig drops a byte-order mark, which would otherwise hide the
            # header block from the parser and put it in the document body.
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8-sig")
            documents.append((key, body))

    return documents


def embed_and_store() -> None:
    collection = get_collection(PASSAGES_COLLECTION)
    bodies = get_collection(DOCUMENT_BODIES_COLLECTION)
    documents = fetch_documents_from_s3()
    if not documents:
        sys.exit(
            f"No documents found under s3://{os.getenv('S3_BUCKET_NAME')}/{S3_DOCUMENT_PREFIX} — "
            f"run python -m sourcebook.rag.seed_documents first."
        )

    provider = get_provider()
    # One entry per document: its passage records and, when it has any, its
    # reading copy. Kept together so they are written together below.
    prepared: list[tuple[list[dict], dict | None]] = []
    active_chunks: dict[str, set[int]] = {}

    # Prepare the complete replacement corpus before changing the live collection.
    # If parsing or embedding fails, the existing corpus remains untouched.
    for key, raw in documents:
        document = parse_document(key, raw)
        chunks = splitter.split_text(document["body"])
        records = passage_records(document, key, chunks)

        texts = [record["text"] for record in records]
        embeddings = provider.embed_many(texts)
        if len(embeddings) != len(records):
            raise RuntimeError(
                f"Embedding provider returned {len(embeddings)} vectors "
                f"for {len(records)} passages from {key}."
            )
        for record, embedding in zip(records, embeddings, strict=False):
            record["embedding"] = embedding

        # A document with no passages is absent from the library, so it keeps
        # no reading copy either.
        prepared.append((records, document_record(document, key) if records else None))
        active_chunks[key] = {record["chunk_index"] for record in records}

        print(f"  {document['title'][:45]:45} {len(records):>3} passages")

    # Upsert the new corpus while the previous corpus remains queryable. Each
    # document's reading copy goes in right after its passages, so a body is
    # at most one document's worth of writes behind the passages it belongs to.
    passage_count = 0
    body_sources: list[str] = []
    for records, body in prepared:
        for record in records:
            collection.update_one(
                {
                    "source": record["source"],
                    "chunk_index": record["chunk_index"],
                },
                {"$set": record},
                upsert=True,
            )
        passage_count += len(records)
        if body is not None:
            bodies.update_one({"source": body["source"]}, {"$set": body}, upsert=True)
            body_sources.append(body["source"])

    # Remove documents that no longer exist in S3.
    active_sources = list(active_chunks)
    stale_count = collection.delete_many({"source": {"$nin": active_sources}}).deleted_count
    stale_bodies = bodies.delete_many({"source": {"$nin": body_sources}}).deleted_count

    # Remove obsolete chunks when an existing document now produces fewer passages.
    for source, chunk_indexes in active_chunks.items():
        if chunk_indexes:
            stale_count += collection.delete_many(
                {
                    "source": source,
                    "chunk_index": {"$nin": list(chunk_indexes)},
                }
            ).deleted_count
        else:
            stale_count += collection.delete_many({"source": source}).deleted_count

    # Only invalidate cached answers after the replacement corpus is complete.
    version = bump_corpus_version()

    print(f"\nDone. {len(documents)} documents → {passage_count} passages in MongoDB.")
    print(f"Removed {stale_count} stale passages and {stale_bodies} stale document bodies.")
    print(f"Corpus version now {version[:8]} — cached answers invalidated.")
    print(
        "\nIf you have not created it yet, add an Atlas Vector Search index named "
        f'"{os.getenv("VECTOR_INDEX_NAME", "vector_index")}" on the '
        f'"{PASSAGES_COLLECTION}" collection; see docs/install.md, Load the corpus.'
    )


if __name__ == "__main__":
    embed_and_store()
