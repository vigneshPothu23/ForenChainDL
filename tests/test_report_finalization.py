"""
Tests for forenchain/report_finalization.py.

Run from the project folder:
    python -m unittest tests.test_report_finalization -v

Each test copies the forenchain package into a temporary folder, so the real
database and evidence files are never touched.
"""
import hashlib
import importlib
import shutil
import sqlite3
import sys
import tempfile
import unittest
import uuid
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
PASSWORD = "UnitTest#Password2026"


def _png(width, height, seed):
    rng = np.random.default_rng(seed)
    data = rng.integers(0, 255, size=(height, width, 3), dtype=np.uint8)
    buffer = BytesIO()
    Image.fromarray(data, "RGB").save(buffer, format="PNG")
    return buffer.getvalue()


class FinalizationTestCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="fc_finalize_"))
        shutil.copytree(REPO / "forenchain", self.root / "forenchain",
                        ignore=shutil.ignore_patterns("__pycache__"))
        for name in list(sys.modules):
            if name == "forenchain" or name.startswith("forenchain."):
                del sys.modules[name]
        sys.path.insert(0, str(self.root))
        self.m = importlib.import_module("forenchain.report_finalization")
        self.auth = importlib.import_module("forenchain.auth")
        self.store = importlib.import_module("forenchain.evidence_store")
        self.custody = importlib.import_module("forenchain.custody")
        self.history = importlib.import_module("forenchain.analysis_history")
        self.assertEqual(self.store.ROOT, self.root, "test copy is not isolated")
        self._seed()

    def tearDown(self):
        sys.path.remove(str(self.root))
        for name in list(sys.modules):
            if name == "forenchain" or name.startswith("forenchain."):
                del sys.modules[name]
        shutil.rmtree(self.root, ignore_errors=True)

    # ------------------------------------------------------------------ fixtures
    def _seed(self):
        a = self.auth
        a.initialize_auth_database()
        self.history.initialize_findings_database()
        self.custody.initialize_custody()
        a.create_initial_admin("admin01", PASSWORD)
        admin = a.authenticate_user("admin01", PASSWORD)
        self.users = {"admin": admin}
        for username, role in [
            ("examiner01", "Forensic Examiner"),
            ("examiner02", "Forensic Examiner"),
            ("investigator01", "Investigator"),
            ("custodian01", "Evidence Custodian"),
            ("judge01", "Judicial Authority"),
        ]:
            a.create_user(admin["user_id"], username, PASSWORD, role)
            self.users[username] = a.authenticate_user(username, PASSWORD)

        result = self.store.register_evidence(_png(320, 240, 1), "exhibit.png", "CASE-UT-01", 320, 240)
        self.evidence_id = result["evidence_id"]
        self.stored_path = self.root / result["stored_path"]
        self.sha256 = hashlib.sha256(self.stored_path.read_bytes()).hexdigest()
        self.custody.record_custody_event(
            self.evidence_id, self.users["investigator01"]["user_id"], "REGISTERED", "Evidence registered"
        )
        self.heatmap = Image.new("RGB", (320, 240), (30, 60, 200))

    def uid(self, name):
        return self.users[name]["user_id"]

    def analyse(self, examiner="examiner01", score=0.42):
        analysis_id = "AN-" + uuid.uuid4().hex.upper()
        self.history.save_analysis(
            analysis_id=analysis_id, evidence_id=self.evidence_id,
            examiner_user_id=self.uid(examiner), model_name="MVSS-Net / mvssnet_casia.pt",
            score=score, device="cpu", registered_sha256=self.sha256, analyzed_sha256=self.sha256,
        )
        return analysis_id

    def find(self, analysis_id, conclusion="Potential signs of manipulation",
             notes="Localized response near the subject.", examiner="examiner01"):
        finding_id = "FN-" + uuid.uuid4().hex[:16].upper()
        self.history.save_examiner_finding(
            finding_id=finding_id, evidence_id=self.evidence_id,
            examiner_user_id=self.uid(examiner), analysis_id=analysis_id,
            conclusion=conclusion, notes=notes,
        )
        return finding_id

    def finalize(self, user="examiner01", analysis_id=None, **kwargs):
        return self.m.finalize_report(self.uid(user), self.evidence_id, analysis_id, self.heatmap, **kwargs)

    def count(self, table):
        with sqlite3.connect(self.store.DATABASE_PATH) as c:
            return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def audit(self):
        return self.m.get_report_audit_log(self.evidence_id)

    # ------------------------------------------------------------------ tests
    def test_authorized_examiner_finalizes_complete_workflow(self):
        analysis_id = self.analyse()
        finding_id = self.find(analysis_id)
        record, created = self.finalize(analysis_id=analysis_id)
        self.assertTrue(created)
        self.assertEqual(record["version"], 1)
        self.assertEqual(record["finding_id"], finding_id)
        self.assertEqual(record["integrity_status"], "INTEGRITY_OK")
        self.assertEqual(record["verified_sha256"], self.sha256)
        self.assertTrue(record["custody_chain_valid"])
        self.assertEqual(record["custody_event_count"], 1)
        self.assertEqual(record["peer_review_status"], "NOT_RECORDED")
        self.assertNotIn("report_pdf", record)
        pdf, stored = self.m.get_finalized_report_pdf(self.uid("examiner01"), record["finalization_id"])
        self.assertEqual(pdf[:4], b"%PDF")
        self.assertEqual(hashlib.sha256(pdf).hexdigest(), stored["report_sha256"])
        self.assertEqual(self.audit()[-1]["outcome"], "SUCCESS")

    def test_unauthorized_roles_cannot_finalize(self):
        analysis_id = self.analyse()
        self.find(analysis_id)
        for user in ("investigator01", "custodian01", "judge01", "admin"):
            with self.subTest(user=user):
                with self.assertRaises(PermissionError):
                    self.finalize(user=user, analysis_id=analysis_id)
        self.assertEqual(self.count("report_finalizations"), 0)
        outcomes = [row["outcome"] for row in self.audit()]
        self.assertEqual(outcomes.count("DENIED"), 4)

    def test_inactive_examiner_is_denied(self):
        analysis_id = self.analyse()
        self.find(analysis_id)
        with sqlite3.connect(self.store.DATABASE_PATH) as c:
            c.execute("UPDATE users SET active = 0 WHERE user_id = ?", (self.uid("examiner01"),))
        with self.assertRaises(PermissionError):
            self.finalize(analysis_id=analysis_id)
        self.assertEqual(self.count("report_finalizations"), 0)

    def test_examiner_cannot_finalize_another_examiners_work(self):
        analysis_id = self.analyse(examiner="examiner01")
        self.find(analysis_id, examiner="examiner01")
        with self.assertRaises(self.m.FinalizationError):
            self.finalize(user="examiner02", analysis_id=analysis_id)
        self.assertEqual(self.count("report_finalizations"), 0)

    def test_incomplete_workflows_are_rejected(self):
        with self.assertRaises(self.m.FinalizationError) as ctx:
            self.finalize(analysis_id=None)
        self.assertEqual(ctx.exception.code, "INCOMPLETE")

        analysis_id = self.analyse()
        with self.assertRaises(self.m.FinalizationError) as ctx:
            self.finalize(analysis_id=analysis_id)            # no findings yet
        self.assertEqual(ctx.exception.code, "INCOMPLETE")

        self.find(analysis_id)
        newer = self.analyse()                                # findings refer to the older analysis
        with self.assertRaises(self.m.FinalizationError) as ctx:
            self.finalize(analysis_id=newer)
        self.assertEqual(ctx.exception.code, "INCOMPLETE")
        self.assertEqual(self.count("report_finalizations"), 0)

    def test_tampered_or_missing_evidence_blocks_finalization(self):
        analysis_id = self.analyse()
        self.find(analysis_id)
        original = self.stored_path.read_bytes()
        self.stored_path.write_bytes(original + b"\x00")
        with self.assertRaises(self.m.FinalizationError) as ctx:
            self.finalize(analysis_id=analysis_id)
        self.assertEqual(ctx.exception.code, "INTEGRITY_FAILURE")
        self.stored_path.unlink()
        with self.assertRaises(self.m.FinalizationError) as ctx:
            self.finalize(analysis_id=analysis_id)
        self.assertEqual(ctx.exception.code, "INTEGRITY_FAILURE")
        self.assertEqual(self.count("report_finalizations"), 0)

    def test_broken_custody_chain_blocks_finalization(self):
        analysis_id = self.analyse()
        self.find(analysis_id)
        with sqlite3.connect(self.store.DATABASE_PATH) as c:
            c.execute("UPDATE custody_events SET details = 'edited' WHERE evidence_id = ?", (self.evidence_id,))
        with self.assertRaises(self.m.FinalizationError) as ctx:
            self.finalize(analysis_id=analysis_id)
        self.assertEqual(ctx.exception.code, "CUSTODY_FAILURE")

    def test_requires_further_examination_needs_acknowledgment(self):
        analysis_id = self.analyse()
        self.find(analysis_id, conclusion="Requires further examination")
        with self.assertRaises(self.m.FinalizationError) as ctx:
            self.finalize(analysis_id=analysis_id)
        self.assertEqual(ctx.exception.code, "ACKNOWLEDGMENT_REQUIRED")
        record, created = self.finalize(analysis_id=analysis_id, acknowledge_qualified=True)
        self.assertTrue(created)
        self.assertTrue(record["qualified_conclusion"])
        self.assertTrue(record["qualification_acknowledged"])
        self.assertEqual(record["conclusion"], "Requires further examination")

    def test_report_download_authorization(self):
        analysis_id = self.analyse()
        self.find(analysis_id)
        record, _ = self.finalize(analysis_id=analysis_id)
        fid = record["finalization_id"]
        for user in ("examiner01", "examiner02", "judge01"):
            with self.subTest(allowed=user):
                pdf, _ = self.m.get_finalized_report_pdf(self.uid(user), fid)
                self.assertEqual(pdf[:4], b"%PDF")
        for user in ("investigator01", "custodian01", "admin"):
            with self.subTest(denied=user):
                with self.assertRaises(PermissionError):
                    self.m.get_finalized_report_pdf(self.uid(user), fid)
        self.m.record_report_download(self.uid("judge01"), fid)
        downloads = [r for r in self.m.get_report_audit_log() if r["action"] == "DOWNLOAD"]
        self.assertEqual(downloads[-1]["outcome"], "SUCCESS")
        self.assertEqual(downloads[-1]["actor_username"], "judge01")

    def test_repeated_finalization_is_idempotent(self):
        analysis_id = self.analyse()
        self.find(analysis_id)
        first, created_first = self.finalize(analysis_id=analysis_id)
        second, created_second = self.finalize(analysis_id=analysis_id)
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first["finalization_id"], second["finalization_id"])
        self.assertEqual(first["report_sha256"], second["report_sha256"])
        self.assertEqual(self.count("report_finalizations"), 1)
        self.assertEqual(self.audit()[-1]["outcome"], "ALREADY_FINALIZED")

    def test_amended_report_needs_reason_and_keeps_original(self):
        analysis_id = self.analyse()
        self.find(analysis_id)
        v1, _ = self.finalize(analysis_id=analysis_id)
        self.find(analysis_id, conclusion="No obvious signs of manipulation detected", notes="Revised after review.")
        with self.assertRaises(self.m.FinalizationError) as ctx:
            self.finalize(analysis_id=analysis_id)
        self.assertEqual(ctx.exception.code, "AMENDMENT_REASON_REQUIRED")
        v2, created = self.finalize(analysis_id=analysis_id, amendment_reason="Conclusion revised after peer review.")
        self.assertTrue(created)
        self.assertEqual(v2["version"], 2)
        self.assertEqual(v2["supersedes_id"], v1["finalization_id"])
        pdf_v1, rec_v1 = self.m.get_finalized_report_pdf(self.uid("examiner01"), v1["finalization_id"])
        self.assertEqual(rec_v1["report_sha256"], v1["report_sha256"])
        self.assertEqual(self.count("report_finalizations"), 2)

    def test_finalized_report_and_audit_log_are_append_only(self):
        analysis_id = self.analyse()
        self.find(analysis_id)
        record, _ = self.finalize(analysis_id=analysis_id)
        with sqlite3.connect(self.store.DATABASE_PATH) as c:
            with self.assertRaises(sqlite3.DatabaseError):
                c.execute("UPDATE report_finalizations SET conclusion = 'edited'")
            with self.assertRaises(sqlite3.DatabaseError):
                c.execute("DELETE FROM report_finalizations")
            with self.assertRaises(sqlite3.DatabaseError):
                c.execute("UPDATE report_audit_log SET outcome = 'edited'")
            with self.assertRaises(sqlite3.DatabaseError):
                c.execute("DELETE FROM report_audit_log")

    def test_tampered_stored_pdf_is_not_released(self):
        analysis_id = self.analyse()
        self.find(analysis_id)
        record, _ = self.finalize(analysis_id=analysis_id)
        with sqlite3.connect(self.store.DATABASE_PATH) as c:
            # Simulate tampering by someone with direct file access who bypasses the triggers.
            c.execute("DROP TRIGGER report_finalizations_no_update")
            c.execute("UPDATE report_finalizations SET report_pdf = ? WHERE finalization_id = ?",
                      (b"%PDF-forged", record["finalization_id"]))
        with self.assertRaises(self.m.FinalizationError) as ctx:
            self.m.get_finalized_report_pdf(self.uid("examiner01"), record["finalization_id"])
        self.assertEqual(ctx.exception.code, "INTEGRITY_FAILURE")

    def test_audit_log_records_attempts_and_hash_chain_detects_edits(self):
        analysis_id = self.analyse()
        with self.assertRaises(self.m.FinalizationError):
            self.finalize(analysis_id=analysis_id)                 # no findings: rejected
        with self.assertRaises(PermissionError):
            self.finalize(user="judge01", analysis_id=analysis_id)  # denied
        self.find(analysis_id)
        record, _ = self.finalize(analysis_id=analysis_id)           # success
        self.finalize(analysis_id=analysis_id)                       # repeat
        outcomes = [(r["action"], r["outcome"]) for r in self.audit()]
        self.assertEqual(outcomes, [
            ("FINALIZE", "INCOMPLETE"),
            ("FINALIZE", "DENIED"),
            ("FINALIZE", "SUCCESS"),
            ("FINALIZE", "ALREADY_FINALIZED"),
        ])
        success = self.audit()[2]
        self.assertEqual(success["finalization_id"], record["finalization_id"])
        self.assertTrue(self.m.verify_report_audit_chain()["valid"])
        with sqlite3.connect(self.store.DATABASE_PATH) as c:
            c.execute("DROP TRIGGER report_audit_no_update")
            c.execute("UPDATE report_audit_log SET outcome = 'SUCCESS' WHERE entry_id = 2")
        self.assertFalse(self.m.verify_report_audit_chain()["valid"])

    def test_readiness_preview_does_not_write(self):
        analysis_id = self.analyse()
        self.find(analysis_id, conclusion="No conclusion reached")
        before = self.count("report_audit_log") if self._table_exists("report_audit_log") else 0
        ready = self.m.finalization_readiness(self.uid("examiner01"), self.evidence_id, analysis_id)
        self.assertTrue(ready["ready"])
        self.assertTrue(ready["qualified"])
        denied = self.m.finalization_readiness(self.uid("investigator01"), self.evidence_id, analysis_id)
        self.assertFalse(denied["ready"])
        self.assertEqual(self.count("report_audit_log"), before)
        self.assertEqual(self.count("report_finalizations"), 0)

    def _table_exists(self, name):
        with sqlite3.connect(self.store.DATABASE_PATH) as c:
            return c.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (name,)).fetchone() is not None


if __name__ == "__main__":
    unittest.main(verbosity=2)
