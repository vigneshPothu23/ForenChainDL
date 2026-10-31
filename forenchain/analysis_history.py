import sqlite3
from datetime import datetime, timezone

from forenchain.evidence_store import DATABASE_PATH, initialize_database


def initialize_analysis_database():
    """Create a separate table without altering existing tables."""
    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS analysis_records (
                analysis_id TEXT PRIMARY KEY,
                evidence_id TEXT NOT NULL,
                examiner_user_id INTEGER NOT NULL,
                model_name TEXT NOT NULL,
                model_response_score REAL NOT NULL,
                inference_device TEXT NOT NULL,
                registered_sha256 TEXT NOT NULL,
                analyzed_sha256 TEXT NOT NULL,
                analyzed_at TEXT NOT NULL,
                FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id),
                FOREIGN KEY (examiner_user_id) REFERENCES users(user_id)
            )
        """)


def save_analysis(
    analysis_id,
    evidence_id,
    examiner_user_id,
    model_name,
    score,
    device,
    registered_sha256,
    analyzed_sha256,
):
    """Append one analysis record; never modify original evidence."""
    initialize_analysis_database()

    if registered_sha256 != analyzed_sha256:
        raise ValueError("Evidence hash mismatch; analysis cannot be recorded.")

    analyzed_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            INSERT INTO analysis_records (
                analysis_id, evidence_id, examiner_user_id,
                model_name, model_response_score, inference_device,
                registered_sha256, analyzed_sha256, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id, evidence_id, examiner_user_id,
                model_name, float(score), device,
                registered_sha256, analyzed_sha256, analyzed_at,
            ),
        )

    return analyzed_at


def get_analysis_history(evidence_id):
    initialize_analysis_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT analysis_id, evidence_id, examiner_user_id,
                   model_name, model_response_score, inference_device,
                   registered_sha256, analyzed_sha256, analyzed_at
            FROM analysis_records
            WHERE evidence_id = ?
            ORDER BY analyzed_at DESC
            """,
            (evidence_id,),
        ).fetchall()

    return [dict(row) for row in rows]

def initialize_findings_database():
    """Create a separate table for examiner findings."""
    initialize_analysis_database()
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS examiner_findings (
                finding_id TEXT PRIMARY KEY,
                evidence_id TEXT NOT NULL,
                examiner_user_id INTEGER NOT NULL,
                analysis_id TEXT,
                conclusion TEXT NOT NULL,
                notes TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id),
                FOREIGN KEY (examiner_user_id) REFERENCES users(user_id)
            )
        """)


def save_examiner_finding(
    finding_id, evidence_id, examiner_user_id,
    analysis_id, conclusion, notes,
):
    """Append an examiner finding without changing original evidence."""
    from forenchain.auth import has_permission

    initialize_findings_database()
    conclusion = conclusion.strip()
    notes = notes.strip()

    if not conclusion or not notes:
        raise ValueError("Conclusion and notes are required.")

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        actor = connection.execute(
            "SELECT role, active FROM users WHERE user_id = ?",
            (examiner_user_id,),
        ).fetchone()
        if (actor is None or actor["active"] != 1
                or not has_permission(actor["role"], "record_findings")):
            raise PermissionError("Your role cannot record examiner findings.")

        recorded_at = datetime.now(timezone.utc).isoformat()
        connection.execute("""
            INSERT INTO examiner_findings (
                finding_id, evidence_id, examiner_user_id,
                analysis_id, conclusion, notes, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            finding_id, evidence_id, examiner_user_id,
            analysis_id, conclusion, notes, recorded_at,
        ))
    return recorded_at

