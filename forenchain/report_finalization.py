"""
Forensic report finalization ("sealing") for ForenChain-DL.

What finalization means here
----------------------------
Finalizing locks one examiner's forensic report for one evidence item, one
analysis and one recorded finding. The exact PDF bytes are stored together
with their SHA-256 and the validation results observed at that moment.

Finalization is NOT:
  * evidence custody sealing: the custody chain stays open and unchanged;
  * legal case closure: that decision sits outside this application;
  * a statement that the image is authentic or manipulated: the report
    carries the examiner's qualified conclusion, nothing more.

Rules enforced here (not only in the UI)
----------------------------------------
  * Only an active account with the ``finalize_report`` permission may
    finalize, and only for findings that the same examiner recorded.
  * Evidence integrity is recomputed now and must match the registered hash.
  * The global custody chain must validate and the evidence item must have
    at least one custody event.
  * The analysis must belong to this evidence and examiner, with matching
    registered and analyzed hashes.
  * The latest finding by this examiner must reference that analysis and
    contain a conclusion and notes.
  * Qualified conclusions ("Requires further examination", "No conclusion
    reached") need an explicit acknowledgment.
  * Finalizing the same evidence/analysis/finding twice returns the existing
    record (idempotent). A different analysis or finding produces a new
    version that references the previous one and requires a reason
    (amended report).
  * Finalized reports and audit entries cannot be updated or deleted through
    SQLite (triggers), and every stored PDF is re-hashed before release.
  * Every attempt (success, denial, rejection, repeat, download) is written
    to a hash-linked audit log.
"""

import hashlib
import io
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from forenchain.auth import has_permission
from forenchain.custody import verify_custody_chain
from forenchain.evidence_store import DATABASE_PATH, ROOT, initialize_database
from forenchain.integrity import verify_evidence


FINALIZE_PERMISSION = "finalize_report"
VIEW_PERMISSION = "view_reports"
MODEL_NAME = "MVSS-Net / mvssnet_casia.pt"
GENESIS_HASH = "0" * 64

DEFINITIVE_CONCLUSIONS = {
    "Potential signs of manipulation",
    "No obvious signs of manipulation detected",
}
QUALIFIED_CONCLUSIONS = {
    "Requires further examination",
    "No conclusion reached",
}
ALLOWED_CONCLUSIONS = DEFINITIVE_CONCLUSIONS | QUALIFIED_CONCLUSIONS


class FinalizationError(ValueError):
    """Raised when the workflow is incomplete or a validation check fails."""

    def __init__(self, message, code="REJECTED", checks=None):
        super().__init__(message)
        self.code = code
        self.checks = checks or {}


def _now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect():
    """Open a connection, commit on success, roll back on error, always close."""
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_report_finalization():
    """Create append-only tables. Existing tables are not altered."""
    initialize_database()
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS report_finalizations (
                finalization_id       TEXT PRIMARY KEY,
                evidence_id           TEXT NOT NULL,
                case_id               TEXT NOT NULL,
                analysis_id           TEXT NOT NULL,
                finding_id            TEXT NOT NULL,
                examiner_user_id      INTEGER NOT NULL,
                examiner_username     TEXT NOT NULL,
                examiner_role         TEXT NOT NULL,
                conclusion            TEXT NOT NULL,
                qualified_conclusion  INTEGER NOT NULL,
                qualification_acknowledged INTEGER NOT NULL,
                version               INTEGER NOT NULL,
                supersedes_id         TEXT,
                amendment_reason      TEXT,
                registered_sha256     TEXT NOT NULL,
                verified_sha256       TEXT NOT NULL,
                integrity_status      TEXT NOT NULL,
                integrity_checked_at  TEXT NOT NULL,
                custody_chain_valid   INTEGER NOT NULL,
                custody_event_count   INTEGER NOT NULL,
                custody_last_event_hash TEXT NOT NULL,
                peer_review_status    TEXT NOT NULL,
                report_sha256         TEXT NOT NULL,
                report_pdf            BLOB NOT NULL,
                finalized_at          TEXT NOT NULL,
                UNIQUE (evidence_id, analysis_id, finding_id),
                UNIQUE (evidence_id, examiner_user_id, version)
            );

            CREATE TABLE IF NOT EXISTS report_audit_log (
                entry_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_time        TEXT NOT NULL,
                actor_user_id     INTEGER,
                actor_username    TEXT,
                action            TEXT NOT NULL,
                outcome           TEXT NOT NULL,
                evidence_id       TEXT,
                finalization_id   TEXT,
                details           TEXT NOT NULL,
                previous_hash     TEXT NOT NULL,
                entry_hash        TEXT NOT NULL UNIQUE
            );

            CREATE TRIGGER IF NOT EXISTS report_finalizations_no_update
            BEFORE UPDATE ON report_finalizations
            BEGIN SELECT RAISE(ABORT, 'Finalized reports are append-only.'); END;

            CREATE TRIGGER IF NOT EXISTS report_finalizations_no_delete
            BEFORE DELETE ON report_finalizations
            BEGIN SELECT RAISE(ABORT, 'Finalized reports are append-only.'); END;

            CREATE TRIGGER IF NOT EXISTS report_audit_no_update
            BEFORE UPDATE ON report_audit_log
            BEGIN SELECT RAISE(ABORT, 'Report audit log is append-only.'); END;

            CREATE TRIGGER IF NOT EXISTS report_audit_no_delete
            BEFORE DELETE ON report_audit_log
            BEGIN SELECT RAISE(ABORT, 'Report audit log is append-only.'); END;
            """
        )


# --------------------------------------------------------------------------- audit

def _entry_hash(payload):
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _append_audit(connection, actor, action, outcome, evidence_id=None,
                  finalization_id=None, details=None):
    previous = connection.execute(
        "SELECT entry_hash FROM report_audit_log ORDER BY entry_id DESC LIMIT 1"
    ).fetchone()
    previous_hash = previous[0] if previous else GENESIS_HASH
    payload = {
        "event_time": _now(),
        "actor_user_id": actor.get("user_id") if actor else None,
        "actor_username": actor.get("username") if actor else None,
        "action": action,
        "outcome": outcome,
        "evidence_id": evidence_id,
        "finalization_id": finalization_id,
        "details": json.dumps(details or {}, sort_keys=True, default=str),
        "previous_hash": previous_hash,
    }
    payload["entry_hash"] = _entry_hash(payload)
    connection.execute(
        """
        INSERT INTO report_audit_log (
            event_time, actor_user_id, actor_username, action, outcome,
            evidence_id, finalization_id, details, previous_hash, entry_hash
        ) VALUES (:event_time, :actor_user_id, :actor_username, :action, :outcome,
                  :evidence_id, :finalization_id, :details, :previous_hash, :entry_hash)
        """,
        payload,
    )


def _audit_separately(actor, action, outcome, evidence_id=None, finalization_id=None, details=None):
    """Record an audit entry in its own transaction (used after a rollback)."""
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _append_audit(connection, actor, action, outcome, evidence_id, finalization_id, details)


def verify_report_audit_chain():
    """Recompute every audit entry hash and predecessor link."""
    initialize_report_finalization()
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM report_audit_log ORDER BY entry_id ASC"
        ).fetchall()
    expected_previous = GENESIS_HASH
    for row in rows:
        payload = {key: row[key] for key in (
            "event_time", "actor_user_id", "actor_username", "action", "outcome",
            "evidence_id", "finalization_id", "details", "previous_hash",
        )}
        if row["previous_hash"] != expected_previous or _entry_hash(payload) != row["entry_hash"]:
            return {"valid": False, "entry_count": len(rows), "broken_at": row["entry_id"]}
        expected_previous = row["entry_hash"]
    return {"valid": True, "entry_count": len(rows), "broken_at": None}


def get_report_audit_log(evidence_id=None):
    initialize_report_finalization()
    with _connect() as connection:
        if evidence_id:
            rows = connection.execute(
                "SELECT entry_id, event_time, actor_username, action, outcome, finalization_id, details "
                "FROM report_audit_log WHERE evidence_id = ? ORDER BY entry_id",
                (evidence_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT entry_id, event_time, actor_username, action, outcome, evidence_id, "
                "finalization_id, details FROM report_audit_log ORDER BY entry_id"
            ).fetchall()
    return [dict(row) for row in rows]


# --------------------------------------------------------------------------- helpers

def _active_actor(connection, user_id):
    row = connection.execute(
        "SELECT user_id, username, role, active FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None or row["active"] != 1:
        return None
    return dict(row)


def _short(value, head=4, tail=8):
    text = str(value or "")
    prefix, sep, rest = text.partition("-")
    if sep and len(rest) > head + tail + 1:
        return f"{prefix}-{rest[:head]}…{rest[-tail:]}"
    return text


def _public_record(row):
    """A finalization record without the PDF bytes."""
    if row is None:
        return None
    record = dict(row)
    record.pop("report_pdf", None)
    record["qualified_conclusion"] = bool(record["qualified_conclusion"])
    record["qualification_acknowledged"] = bool(record["qualification_acknowledged"])
    record["custody_chain_valid"] = bool(record["custody_chain_valid"])
    return record


def latest_finalization(evidence_id, examiner_user_id):
    """Latest finalized report for this evidence by this examiner (no PDF bytes)."""
    initialize_report_finalization()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM report_finalizations
            WHERE evidence_id = ? AND examiner_user_id = ?
            ORDER BY version DESC LIMIT 1
            """,
            (evidence_id, int(examiner_user_id)),
        ).fetchone()
    return _public_record(row)


def _collect(connection, actor, evidence_id, analysis_id):
    """Gather and validate every input. Returns (context, checks)."""
    checks = {}

    evidence = connection.execute(
        "SELECT evidence_id, case_id, original_filename, stored_path, sha256 FROM evidence WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    checks["evidence_record"] = evidence is not None
    if evidence is None:
        raise FinalizationError("Evidence record not found.", "INCOMPLETE", checks)

    integrity = verify_evidence(evidence_id)
    integrity_ok = integrity.get("status") == "INTEGRITY_OK"
    checks["integrity"] = integrity.get("status", "UNKNOWN")
    if not integrity_ok:
        raise FinalizationError(
            f"Integrity verification failed ({checks['integrity']}). Finalization blocked.",
            "INTEGRITY_FAILURE", checks,
        )

    chain = verify_custody_chain()
    events = connection.execute(
        "SELECT event_id, action, event_hash FROM custody_events WHERE evidence_id = ? ORDER BY event_id",
        (evidence_id,),
    ).fetchall()
    checks["custody_chain_valid"] = bool(chain.get("valid"))
    checks["custody_event_count"] = len(events)
    if not chain.get("valid"):
        raise FinalizationError(
            f"Custody chain validation failed: {chain.get('message', 'invalid chain')}",
            "CUSTODY_FAILURE", checks,
        )
    if not events:
        raise FinalizationError("No custody events recorded for this evidence.", "INCOMPLETE", checks)

    analysis = None
    if analysis_id:
        analysis = connection.execute(
            "SELECT * FROM analysis_records WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
    checks["analysis"] = analysis is not None
    if analysis is None:
        raise FinalizationError("No AI screening analysis is available to finalize.", "INCOMPLETE", checks)
    if analysis["evidence_id"] != evidence_id or int(analysis["examiner_user_id"]) != int(actor["user_id"]):
        checks["analysis"] = False
        raise FinalizationError(
            "The analysis does not belong to this evidence and examiner.", "REJECTED", checks
        )
    hashes_match = (
        analysis["registered_sha256"] == evidence["sha256"]
        and analysis["analyzed_sha256"] == evidence["sha256"]
        and integrity.get("current_hash") == evidence["sha256"]
    )
    checks["analysis_hash_match"] = hashes_match
    if not hashes_match:
        raise FinalizationError(
            "Analysis hashes do not match the registered evidence hash.", "INTEGRITY_FAILURE", checks
        )

    finding = connection.execute(
        """
        SELECT * FROM examiner_findings
        WHERE evidence_id = ? AND examiner_user_id = ?
        ORDER BY recorded_at DESC LIMIT 1
        """,
        (evidence_id, int(actor["user_id"])),
    ).fetchone()
    checks["findings"] = finding is not None
    if finding is None:
        raise FinalizationError("Examiner findings have not been recorded.", "INCOMPLETE", checks)
    if finding["analysis_id"] != analysis_id:
        checks["findings"] = False
        raise FinalizationError(
            "The latest findings refer to a different analysis. Record findings for this analysis first.",
            "INCOMPLETE", checks,
        )
    if finding["conclusion"] not in ALLOWED_CONCLUSIONS or not str(finding["notes"]).strip():
        checks["findings"] = False
        raise FinalizationError("Findings need a recognised conclusion and notes.", "INCOMPLETE", checks)

    return {
        "evidence": dict(evidence),
        "integrity": integrity,
        "chain": chain,
        "events": [dict(e) for e in events],
        "analysis": dict(analysis),
        "finding": dict(finding),
    }, checks


def finalization_readiness(user_id, evidence_id, analysis_id):
    """Read-only preview of the checks, for display. Never writes."""
    initialize_report_finalization()
    with _connect() as connection:
        actor = _active_actor(connection, user_id)
        if actor is None or not has_permission(actor["role"], FINALIZE_PERMISSION):
            return {"ready": False, "reason": "Your role cannot finalize forensic reports.", "checks": {}}
        try:
            context, checks = _collect(connection, actor, evidence_id, analysis_id)
        except FinalizationError as exc:
            return {"ready": False, "reason": str(exc), "code": exc.code, "checks": exc.checks}
    conclusion = context["finding"]["conclusion"]
    return {
        "ready": True,
        "reason": "",
        "checks": checks,
        "conclusion": conclusion,
        "qualified": conclusion in QUALIFIED_CONCLUSIONS,
        "finding_id": context["finding"]["finding_id"],
    }


def build_report_metadata(context, actor, integrity_checked_at):
    """The same fields the AI screening screen already passes to the PDF builder."""
    analysis, finding, evidence = context["analysis"], context["finding"], context["evidence"]
    return {
        "case_id": evidence["case_id"],
        "evidence_id": evidence["evidence_id"],
        "original_filename": evidence["original_filename"],
        "registered_sha256": evidence["sha256"],
        "analyzed_sha256": analysis["analyzed_sha256"],
        "integrity_status": context["integrity"]["status"],
        "integrity_checked_at": integrity_checked_at,
        "examiner_username": actor["username"],
        "examiner_user_id": actor["user_id"],
        "model_name": analysis["model_name"],
        "model_response_score": f"{float(analysis['model_response_score']):.6f}",
        "inference_device": analysis["inference_device"],
        "analysis_id": analysis["analysis_id"],
        "analyzed_at": analysis["analyzed_at"],
        "examiner_conclusion": finding["conclusion"],
        "examiner_notes": finding["notes"],
    }


# --------------------------------------------------------------------------- finalize

def finalize_report(
    user_id,
    evidence_id,
    analysis_id,
    heatmap_image,
    acknowledge_qualified=False,
    amendment_reason="",
    pdf_builder=None,
):
    """
    Finalize the forensic report. Returns (record, created) where ``created``
    is False when the same report was already finalized.

    ``heatmap_image`` is the display heatmap of this analysis (the localization
    map is not persisted by the application). The original image is read from
    the verified evidence file, and all other report fields come from the
    database, never from the caller.
    """
    from PIL import Image

    if pdf_builder is None:
        from forenchain.forensic_report import build_forensic_report_pdf as pdf_builder

    initialize_report_finalization()
    evidence_id = (evidence_id or "").strip()
    actor_for_audit = {"user_id": user_id, "username": None}

    try:
        with _connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            actor = _active_actor(connection, user_id)
            if actor is None:
                raise PermissionError("An active authenticated account is required.")
            actor_for_audit = actor
            if not has_permission(actor["role"], FINALIZE_PERMISSION):
                raise PermissionError(f"Role '{actor['role']}' cannot finalize forensic reports.")

            context, checks = _collect(connection, actor, evidence_id, analysis_id)
            finding = context["finding"]

            existing = connection.execute(
                "SELECT * FROM report_finalizations WHERE evidence_id = ? AND analysis_id = ? AND finding_id = ?",
                (evidence_id, analysis_id, finding["finding_id"]),
            ).fetchone()
            if existing is not None:
                _append_audit(connection, actor, "FINALIZE", "ALREADY_FINALIZED", evidence_id,
                              existing["finalization_id"], {"version": existing["version"]})
                return _public_record(existing), False

            qualified = finding["conclusion"] in QUALIFIED_CONCLUSIONS
            if qualified and not acknowledge_qualified:
                raise FinalizationError(
                    "This conclusion is qualified. Confirm that the report will state that "
                    "further examination is required or that no conclusion was reached.",
                    "ACKNOWLEDGMENT_REQUIRED", checks,
                )

            previous = connection.execute(
                """
                SELECT finalization_id, version FROM report_finalizations
                WHERE evidence_id = ? AND examiner_user_id = ?
                ORDER BY version DESC LIMIT 1
                """,
                (evidence_id, int(actor["user_id"])),
            ).fetchone()
            amendment_reason = (amendment_reason or "").strip()
            if previous is not None and not amendment_reason:
                raise FinalizationError(
                    f"Version {previous['version']} is already finalized. An amended report needs a reason.",
                    "AMENDMENT_REASON_REQUIRED", checks,
                )
            version = (previous["version"] + 1) if previous else 1

            evidence_path = (ROOT / context["evidence"]["stored_path"]).resolve()
            file_bytes = evidence_path.read_bytes()
            if hashlib.sha256(file_bytes).hexdigest() != context["evidence"]["sha256"]:
                raise FinalizationError("Evidence changed during finalization.", "INTEGRITY_FAILURE", checks)
            original = Image.open(io.BytesIO(file_bytes)).convert("RGB")

            integrity_checked_at = _now()
            metadata = build_report_metadata(context, actor, integrity_checked_at)
            pdf_bytes = pdf_builder(metadata, original, heatmap_image)
            if not pdf_bytes or bytes(pdf_bytes[:4]) != b"%PDF":
                raise FinalizationError("The PDF report could not be generated.", "REJECTED", checks)
            pdf_bytes = bytes(pdf_bytes)

            finalization_id = "RF-" + uuid.uuid4().hex.upper()
            record = {
                "finalization_id": finalization_id,
                "evidence_id": evidence_id,
                "case_id": context["evidence"]["case_id"],
                "analysis_id": analysis_id,
                "finding_id": finding["finding_id"],
                "examiner_user_id": int(actor["user_id"]),
                "examiner_username": actor["username"],
                "examiner_role": actor["role"],
                "conclusion": finding["conclusion"],
                "qualified_conclusion": int(qualified),
                "qualification_acknowledged": int(bool(qualified and acknowledge_qualified)),
                "version": version,
                "supersedes_id": previous["finalization_id"] if previous else None,
                "amendment_reason": amendment_reason or None,
                "registered_sha256": context["evidence"]["sha256"],
                "verified_sha256": context["integrity"]["current_hash"],
                "integrity_status": context["integrity"]["status"],
                "integrity_checked_at": integrity_checked_at,
                "custody_chain_valid": 1,
                "custody_event_count": len(context["events"]),
                "custody_last_event_hash": context["events"][-1]["event_hash"],
                "peer_review_status": "NOT_RECORDED",
                "report_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                "report_pdf": pdf_bytes,
                "finalized_at": _now(),
            }
            connection.execute(
                f"INSERT INTO report_finalizations ({', '.join(record)}) "
                f"VALUES ({', '.join(':' + key for key in record)})",
                record,
            )
            _append_audit(connection, actor, "FINALIZE", "SUCCESS", evidence_id, finalization_id, {
                "version": version,
                "supersedes_id": record["supersedes_id"],
                "analysis_id": analysis_id,
                "finding_id": finding["finding_id"],
                "conclusion": finding["conclusion"],
                "qualified": bool(qualified),
                "report_sha256": record["report_sha256"],
                "checks": checks,
            })
            return _public_record(record), True

    except PermissionError as exc:
        _audit_separately(actor_for_audit, "FINALIZE", "DENIED", evidence_id, None, {"reason": str(exc)})
        raise
    except FinalizationError as exc:
        _audit_separately(actor_for_audit, "FINALIZE", exc.code, evidence_id, None,
                          {"reason": str(exc), "checks": exc.checks})
        raise
    except sqlite3.IntegrityError as exc:
        # Another session finalized the same inputs between our check and insert.
        _audit_separately(actor_for_audit, "FINALIZE", "CONFLICT", evidence_id, None, {"reason": str(exc)})
        raise FinalizationError("This report was finalized by another session. Reload the page.", "CONFLICT")


# --------------------------------------------------------------------------- release

def get_finalized_report_pdf(user_id, finalization_id):
    """Return (pdf_bytes, record) for an authorized user after re-verifying the stored hash."""
    initialize_report_finalization()
    with _connect() as connection:
        actor = _active_actor(connection, user_id)
        if actor is None or not has_permission(actor["role"], VIEW_PERMISSION):
            role = actor["role"] if actor else "inactive or unknown account"
            _audit_separately(actor or {"user_id": user_id, "username": None}, "ACCESS", "DENIED",
                              None, finalization_id, {"reason": f"{role} lacks {VIEW_PERMISSION}"})
            raise PermissionError("Your role cannot access finalized forensic reports.")
        row = connection.execute(
            "SELECT * FROM report_finalizations WHERE finalization_id = ?", (finalization_id,)
        ).fetchone()
    if row is None:
        raise FinalizationError("Finalized report not found.", "NOT_FOUND")
    pdf_bytes = bytes(row["report_pdf"])
    if hashlib.sha256(pdf_bytes).hexdigest() != row["report_sha256"]:
        _audit_separately(actor, "ACCESS", "INTEGRITY_FAILURE", row["evidence_id"], finalization_id,
                          {"reason": "stored PDF hash mismatch"})
        raise FinalizationError("Stored report failed its integrity check. Release blocked.", "INTEGRITY_FAILURE")
    return pdf_bytes, _public_record(row)


def record_report_download(user_id, finalization_id):
    """Audit a completed download of a finalized report (called from the download button)."""
    initialize_report_finalization()
    with _connect() as connection:
        actor = _active_actor(connection, user_id)
        row = connection.execute(
            "SELECT evidence_id, report_sha256 FROM report_finalizations WHERE finalization_id = ?",
            (finalization_id,),
        ).fetchone()
    allowed = actor is not None and has_permission(actor["role"], VIEW_PERMISSION) and row is not None
    _audit_separately(actor or {"user_id": user_id, "username": None}, "DOWNLOAD",
                      "SUCCESS" if allowed else "DENIED",
                      row["evidence_id"] if row else None, finalization_id,
                      {"report_sha256": row["report_sha256"] if row else None})
