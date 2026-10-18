"""
MongoDB/GridFS raw file store -- the landing zone for every uploaded
statement (PDF or CSV), ahead of the parsed/categorized data in SQLite
(db.py). See docs/design-mongodb-file-store.md for why this split exists
and why files are deduplicated by content hash rather than filename.
"""

import hashlib
import os

import gridfs
from bson import ObjectId
from pymongo import MongoClient

DEFAULT_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
DEFAULT_DB_NAME = "finance_advisor"
BUCKET_NAME = "statements"

_client: MongoClient | None = None
_bucket: gridfs.GridFSBucket | None = None
_db_name: str | None = None


def connect(uri: str = DEFAULT_URI, db_name: str = DEFAULT_DB_NAME) -> gridfs.GridFSBucket:
    """(Re)connect to the given MongoDB database. Tests pass a throwaway
    db_name for isolation from real uploaded files."""
    global _client, _bucket, _db_name
    _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    _bucket = gridfs.GridFSBucket(_client[db_name], bucket_name=BUCKET_NAME)
    _db_name = db_name
    return _bucket


def _get_bucket() -> gridfs.GridFSBucket:
    if _bucket is None:
        connect()
    return _bucket


def store_file(customer_id: str, data: bytes, filename: str, issuer: str, content_type: str) -> tuple[str, bool]:
    """Store raw file bytes, deduplicated by SHA-256 within the owning
    customer's files. Returns (file_id, created) -- created is False when
    that customer already has a file with identical content, in which
    case its id is reused rather than storing a second copy."""
    bucket = _get_bucket()
    digest = hashlib.sha256(data).hexdigest()

    existing = bucket.find({"metadata.sha256": digest, "metadata.customer_id": customer_id}).limit(1)
    for doc in existing:
        return str(doc._id), False

    file_id = bucket.upload_from_stream(
        filename,
        data,
        metadata={"customer_id": customer_id, "issuer": issuer, "content_type": content_type, "sha256": digest},
    )
    return str(file_id), True


def get_file_bytes(file_id: str) -> bytes:
    bucket = _get_bucket()
    return bucket.open_download_stream(ObjectId(file_id)).read()


def list_files(customer_id: str) -> list[dict]:
    bucket = _get_bucket()
    files = []
    for doc in bucket.find({"metadata.customer_id": customer_id}).sort("uploadDate", 1):
        metadata = doc.metadata or {}
        files.append(
            {
                "file_id": str(doc._id),
                "filename": doc.filename,
                "issuer": metadata.get("issuer"),
                "content_type": metadata.get("content_type"),
                "upload_date": doc.upload_date,
            }
        )
    return files


def backfill_customer_id(customer_id: str) -> None:
    """Assign every pre-auth file (metadata.customer_id missing) to the
    given customer. Idempotent -- a no-op once nothing is left unassigned.
    GridFSBucket's own `_collection` attribute is the bare bucket-name
    collection, not `<bucket>.files` where metadata actually lives -- the
    files collection has to be addressed directly."""
    _get_bucket()  # ensure connected
    files_collection = _client[_db_name][f"{BUCKET_NAME}.files"]
    files_collection.update_many(
        {"metadata.customer_id": {"$exists": False}}, {"$set": {"metadata.customer_id": customer_id}}
    )


def clear_all() -> None:
    """Test-only: drop the entire connected database (files + chunks)."""
    _get_bucket()  # ensure connected
    _client.drop_database(_db_name)
