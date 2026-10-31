
import hashlib
import sqlite3
import uuid

from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"
DATABASE_PATH = DATA_DIR / "forenchain.db"

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp",
    ".tif", ".tiff", ".webp",
}


def initialize_database():
    """Create the database and evidence table if needed."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                image_width INTEGER NOT NULL,
                image_height INTEGER NOT NULL,
                registered_at TEXT NOT NULL
            )
        """)


def find_duplicate_evidence(image_hash: str):
    """
    Find existing records with the same SHA-256 hash.
    Searches across all cases without modifying records.
    """

    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT evidence_id, case_id, original_filename,
                   stored_path, sha256, size_bytes,
                   image_width, image_height, registered_at
            FROM evidence
            WHERE sha256 = ?
            ORDER BY registered_at DESC
            """,
            (image_hash,),
        ).fetchall()

    return [dict(row) for row in rows]


def register_evidence(
    file_bytes: bytes,
    filename: str,
    case_id: str,
    image_width: int,
    image_height: int,
    confirm_duplicate: bool = False,
):
    """
    Preserve uploaded image bytes and register metadata.

    Existing matching hashes require explicit confirmation
    before another registration can be created.
    """

    initialize_database()

    case_id = case_id.strip()
    filename = Path(filename).name
    extension = Path(filename).suffix.lower()

    if not case_id:
        raise ValueError("Case ID cannot be empty.")

    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported image filename or format.")

    if not file_bytes:
        raise ValueError("The uploaded file is empty.")

    if len(file_bytes) > 25 * 1024 * 1024:
        raise ValueError("Image exceeds the 2 MB upload limit.")

    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions are invalid.")

    image_hash = hashlib.sha256(file_bytes).hexdigest()
    duplicates = find_duplicate_evidence(image_hash)

    if duplicates and not confirm_duplicate:
        return {
            "status": "DUPLICATE_FOUND",
            "sha256": image_hash,
            "matches": duplicates,
        }

    evidence_id = "EV-" + uuid.uuid4().hex.upper()
    stored_file = EVIDENCE_DIR / f"{evidence_id}{extension}"
    registered_at = datetime.now(timezone.utc).isoformat()

    # Save exact uploaded bytes; do not re-encode the image.
    with stored_file.open("xb") as file:
        file.write(file_bytes)

    try:
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.execute(
                """
                INSERT INTO evidence (
                    evidence_id,
                    case_id,
                    original_filename,
                    stored_path,
                    sha256,
                    size_bytes,
                    image_width,
                    image_height,
                    registered_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    case_id,
                    filename,
                    str(stored_file.relative_to(ROOT)),
                    image_hash,
                    len(file_bytes),
                    image_width,
                    image_height,
                    registered_at,
                ),
            )
    except Exception:
        stored_file.unlink(missing_ok=True)
        raise

    return {
        "status": "REGISTERED",
        "evidence_id": evidence_id,
        "case_id": case_id,
        "filename": filename,
        "sha256": image_hash,
        "size_bytes": len(file_bytes),
        "stored_path": str(stored_file.relative_to(ROOT)),
        "registered_at": registered_at,
        "duplicate_confirmed": bool(duplicates),
        "previous_matches": duplicates,
    }

