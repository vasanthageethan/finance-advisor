"""
One-time migration: upload the real statement PDFs already sitting in the
gitignored local folders (chase-credit/, chase-checking/,
capitalone-credit/, sofi-checkings-savings/ at the repo root) into
MongoDB/GridFS. After this runs once, the backend reads exclusively from
Mongo (see docs/design-mongodb-file-store.md) -- these folders are no
longer read by the running app, only by this script.

Usage (from backend/, with the venv active and MongoDB reachable):
    python scripts/migrate_local_files_to_mongo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import filestore  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOCAL_STATEMENT_DIRS = {
    "chase_credit": _REPO_ROOT / "chase-credit",
    "chase_checking": _REPO_ROOT / "chase-checking",
    "capitalone_credit": _REPO_ROOT / "capitalone-credit",
    "sofi_checking_savings": _REPO_ROOT / "sofi-checkings-savings",
}


def main() -> None:
    filestore.connect()
    uploaded = 0
    skipped = 0
    for issuer, directory in LOCAL_STATEMENT_DIRS.items():
        if not directory.is_dir():
            continue
        for pdf_path in sorted(directory.glob("*.pdf")):
            data = pdf_path.read_bytes()
            file_id, created = filestore.store_file(data, pdf_path.name, issuer, "application/pdf")
            print(f"{'uploaded' if created else 'already present'}: {pdf_path.name} ({issuer}) -> {file_id}")
            uploaded += 1 if created else 0
            skipped += 0 if created else 1
    print(f"\nDone. {uploaded} new file(s) uploaded, {skipped} already present (deduplicated by content).")
    print("Start/restart the backend to parse them into the relational store.")


if __name__ == "__main__":
    main()
