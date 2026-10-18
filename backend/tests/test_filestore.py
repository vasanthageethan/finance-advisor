from bson import ObjectId

import filestore


def test_store_and_list_files_scoped_by_customer():
    id_a, created_a = filestore.store_file("customer-a", b"hello", "a.pdf", "chase_credit", "application/pdf")
    id_b, created_b = filestore.store_file("customer-b", b"different", "b.pdf", "chase_credit", "application/pdf")
    assert created_a and created_b

    files_a = filestore.list_files("customer-a")
    files_b = filestore.list_files("customer-b")
    assert [f["file_id"] for f in files_a] == [id_a]
    assert [f["file_id"] for f in files_b] == [id_b]


def test_dedup_is_scoped_per_customer():
    """Two different customers uploading byte-identical content must get
    two separate files, not share one GridFS doc owned by only one of
    them."""
    id_a, created_a = filestore.store_file("customer-a", b"same bytes", "a.pdf", "chase_credit", "application/pdf")
    id_b, created_b = filestore.store_file("customer-b", b"same bytes", "b.pdf", "chase_credit", "application/pdf")
    assert created_a and created_b
    assert id_a != id_b


def test_backfill_customer_id_assigns_pre_auth_files():
    """Regression test: backfill_customer_id previously targeted
    GridFSBucket's own `_collection` attribute, which is NOT the
    `<bucket>.files` collection metadata actually lives in -- the update
    silently matched zero documents."""
    file_id, _ = filestore.store_file("", b"pre-auth file", "old.pdf", "chase_credit", "application/pdf")
    # Simulate a pre-auth document: no customer_id in its metadata at all.
    files_collection = filestore._client[filestore._db_name][f"{filestore.BUCKET_NAME}.files"]
    files_collection.update_one({"_id": ObjectId(file_id)}, {"$unset": {"metadata.customer_id": ""}})

    assert filestore.list_files("real-customer") == []  # not assigned yet

    filestore.backfill_customer_id("real-customer")

    files = filestore.list_files("real-customer")
    assert len(files) == 1
    assert files[0]["file_id"] == file_id
