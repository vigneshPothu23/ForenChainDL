
import hashlib
import sqlite3
from pathlib import Path

from forenchain.evidence_store import (
    DATABASE_PATH,
    ROOT,
    initialize_database,
)


def verify_evidence(evidence_id: str, file_path=None):
    """Compare a file's SHA-256 against the registered evidence hash."""

    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        record = connection.execute(
            """
            SELECT evidence_id, case_id, stored_path, sha256
            FROM evidence
            WHERE evidence_id = ?
            """,
            (evidence_id.strip(),),
        ).fetchone()

    if record is None:
        return {"status": "NOT_FOUND"}

    evidence_root = (ROOT / "data" / "evidence").resolve()

    if file_path is None:
        path = (ROOT / record["stored_path"]).resolve()
    else:
        path = Path(file_path).resolve()

    if file_path is None and not path.is_relative_to(evidence_root):
        return {"status": "INVALID_PATH"}

    if not path.is_file():
        return {"status": "MISSING_FILE"}

    current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    original_hash = record["sha256"]
    matches = current_hash == original_hash

    return {
        "status": "INTEGRITY_OK" if matches else "HASH_MISMATCH",
        "evidence_id": record["evidence_id"],
        "case_id": record["case_id"],
        "registered_hash": original_hash,
        "current_hash": current_hash,
        "hash_matches": matches,
    }
