
import hashlib
import json
import sqlite3

from datetime import datetime, timezone

from forenchain.auth import has_permission
from forenchain.evidence_store import (
    DATABASE_PATH,
    initialize_database,
)


GENESIS_HASH = "0" * 64

CUSTODY_ACTIONS = {
    "REGISTERED",
    "TRANSFERRED",
    "ACCEPTED",
    "NOTE_ADDED",
}


def initialize_custody():
    """Create the custody event table without deleting existing records."""
    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS custody_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                event_time TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_custody_evidence_event
            ON custody_events (evidence_id, event_id)
        """)


def calculate_event_hash(event):
    """Calculate deterministic SHA-256 for a custody event."""
    payload = json.dumps(
        event,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def _get_active_actor(connection, actor_user_id, permission):
    """Resolve the actor from the authenticated database user."""
    connection.row_factory = sqlite3.Row

    actor = connection.execute(
        """
        SELECT user_id, username, role, active
        FROM users
        WHERE user_id = ?
        """,
        (actor_user_id,),
    ).fetchone()

    if actor is None or actor["active"] != 1:
        raise PermissionError("An active authenticated user is required.")

    if not has_permission(actor["role"], permission):
        raise PermissionError(
            f"Role '{actor['role']}' lacks permission '{permission}'."
        )

    return actor


def _get_evidence(connection, evidence_id):
    evidence = connection.execute(
        """
        SELECT evidence_id, case_id
        FROM evidence
        WHERE evidence_id = ?
        """,
        (evidence_id.strip(),),
    ).fetchone()

    if evidence is None:
        raise ValueError("Evidence ID does not exist.")

    return evidence


def _append_event(
    connection,
    evidence_id,
    case_id,
    actor,
    action,
    details,
):
    """Append an event using the latest global chain head."""
    previous = connection.execute(
        """
        SELECT event_hash
        FROM custody_events
        ORDER BY event_id DESC
        LIMIT 1
        """
    ).fetchone()

    previous_hash = previous[0] if previous else GENESIS_HASH

    event = {
        "evidence_id": evidence_id,
        "case_id": case_id,
        "actor": actor,
        "action": action,
        "details": details,
        "event_time": datetime.now(timezone.utc).isoformat(),
        "previous_hash": previous_hash,
    }

    event_hash = calculate_event_hash(event)

    cursor = connection.execute(
        """
        INSERT INTO custody_events (
            evidence_id, case_id, actor, action, details,
            event_time, previous_hash, event_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["evidence_id"],
            event["case_id"],
            event["actor"],
            event["action"],
            event["details"],
            event["event_time"],
            event["previous_hash"],
            event_hash,
        ),
    )

    return {
        "event_id": cursor.lastrowid,
        **event,
        "event_hash": event_hash,
    }


def record_custody_event(
    evidence_id: str,
    actor_user_id: int,
    action: str,
    details: str = "",
):
    """
    Append an authenticated custody event.

    Actor identity is read from the users table, never accepted as a
    freely typed username. This function requires a logged-in user's ID.
    """
    initialize_custody()

    evidence_id = evidence_id.strip()
    action = action.strip().upper()
    details = details.strip()

    if not evidence_id:
        raise ValueError("Evidence ID is required.")

    if action not in CUSTODY_ACTIONS:
        raise ValueError(
            f"Unsupported action. Choose one of: {', '.join(sorted(CUSTODY_ACTIONS))}."
        )

    if action == "TRANSFERRED":
        permission = "transfer_custody"
    elif action == "ACCEPTED":
        permission = "accept_custody"
    elif action == "REGISTERED":
        permission = "register_evidence"
    else:
        permission = "view_audit"

    with sqlite3.connect(DATABASE_PATH, timeout=30) as connection:
        connection.execute("BEGIN IMMEDIATE")

        actor = _get_active_actor(
            connection,
            actor_user_id,
            permission,
        )
        evidence = _get_evidence(connection, evidence_id)

        if action == "TRANSFERRED":
            if not details:
                raise ValueError(
                    "For a transfer, details must identify the intended recipient."
                )

            latest = connection.execute(
                """
                SELECT action, actor, details
                FROM custody_events
                WHERE evidence_id = ?
                ORDER BY event_id DESC
                LIMIT 1
                """,
                (evidence_id,),
            ).fetchone()

            if latest and latest[0] == "TRANSFERRED":
                raise ValueError(
                    "This evidence already has a pending transfer. "
                    "Record ACCEPTED before another transfer."
                )

        elif action == "ACCEPTED":
            latest = connection.execute(
                """
                SELECT action, details
                FROM custody_events
                WHERE evidence_id = ?
                ORDER BY event_id DESC
                LIMIT 1
                """,
                (evidence_id,),
            ).fetchone()

            if latest is None or latest[0] != "TRANSFERRED":
                raise ValueError(
                    "There is no pending transfer to accept."
                )

            intended_recipient = latest[1].strip().casefold()

            if intended_recipient != actor["username"].strip().casefold():
                raise PermissionError(
                    "Only the named recipient can accept this transfer."
                )

        return _append_event(
            connection=connection,
            evidence_id=evidence["evidence_id"],
            case_id=evidence["case_id"],
            actor=actor["username"],
            action=action,
            details=details,
        )


def get_custody_history(evidence_id: str):
    """Retrieve custody events for one evidence item."""
    initialize_custody()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT event_id, evidence_id, case_id, actor, action,
                   details, event_time, previous_hash, event_hash
            FROM custody_events
            WHERE evidence_id = ?
            ORDER BY event_id ASC
            """,
            (evidence_id.strip(),),
        ).fetchall()

    return [dict(row) for row in rows]


def verify_custody_chain():
    """
    Verify every event in the global chain in event order.

    Checks predecessor links, event hashes, and unique chain sequence.
    """
    initialize_custody()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT event_id, evidence_id, case_id, actor, action,
                   details, event_time, previous_hash, event_hash
            FROM custody_events
            ORDER BY event_id ASC
            """
        ).fetchall()

    expected_previous = GENESIS_HASH

    for event in rows:
        payload = {
            "evidence_id": event["evidence_id"],
            "case_id": event["case_id"],
            "actor": event["actor"],
            "action": event["action"],
            "details": event["details"],
            "event_time": event["event_time"],
            "previous_hash": event["previous_hash"],
        }

        if event["previous_hash"] != expected_previous:
            return {
                "valid": False,
                "message": (
                    f"Broken global chain link at event {event['event_id']}."
                ),
                "event_count": len(rows),
            }

        calculated_hash = calculate_event_hash(payload)

        if event["event_hash"] != calculated_hash:
            return {
                "valid": False,
                "message": (
                    f"Event hash mismatch at event {event['event_id']}."
                ),
                "event_count": len(rows),
            }

        expected_previous = event["event_hash"]

    return {
        "valid": True,
        "message": "Global custody hash chain verified.",
        "event_count": len(rows),
    }


def verify_custody_history(evidence_id: str):
    """
    Compatibility wrapper.

    Verifies the complete global chain, not only one evidence item's events.
    """
    initialize_custody()

    with sqlite3.connect(DATABASE_PATH) as connection:
        exists = connection.execute(
            "SELECT 1 FROM evidence WHERE evidence_id = ?",
            (evidence_id.strip(),),
        ).fetchone()

    if exists is None:
        return {
            "valid": False,
            "message": "Evidence ID does not exist.",
            "event_count": 0,
        }

    result = verify_custody_chain()
    result["evidence_id"] = evidence_id.strip()
    return result
