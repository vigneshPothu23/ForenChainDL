"""UI test for report finalization (safe: runs on a temporary copy).

Reuses the smoke-test harness (temporary copy, seeded database, stubbed model)
and drives the real Streamlit app with AppTest.

Usage (from the repository root):
    python tools/report_finalization_ui_test.py
Exit code 0 = all checks passed.
"""
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_smoke_test as h  # noqa: E402


def text_of(at):
    return h.texts(at)


def button(at, words, key=None):
    for b in at.button:
        if key is not None and b.key == key:
            return b
        if key is None and all(w in b.label.lower() for w in words):
            return b
    return None


def finalized_rows(root):
    db = root / "data" / "forenchain.db"
    with sqlite3.connect(db) as c:
        exists = c.execute("SELECT 1 FROM sqlite_master WHERE name='report_finalizations'").fetchone()
        return c.execute("SELECT COUNT(*) FROM report_finalizations").fetchone()[0] if exists else 0


def main():
    temp = Path(tempfile.mkdtemp(prefix="forenchain_finalize_ui_"))
    try:
        h.copy_code(temp)
        sys.path.insert(0, str(temp))
        h.install_model_stub()
        users, evidence = h.seed(temp)
        app_path = temp / "app.py"
        check = h.check

        print("\nUnauthorized roles never see the finalize screen")
        for username in ("evidence_registrar01", "custody_officer01", "judicial_reviewer01", "platform_admin"):
            at = h.login(app_path, username)
            labels = [t.label for t in at.tabs]
            check("AI Screening" not in labels, f"{username}: no AI Screening tab")
            check(button(at, [], key="fcr_finalize") is None, f"{username}: no finalize button")

        print("\nExaminer: incomplete workflow cannot be finalized")
        at = h.login(app_path, "forensic_examiner01")
        check(button(at, [], key="fcr_finalize") is None, "before AI screening: no finalize button")
        h.find_button(at, ["run", "ai"]).click()
        at.run()
        check(not at.exception, "AI screening run: no exception")
        check(button(at, [], key="fcr_finalize") is None, "before findings: no finalize button")
        check("report locked" in text_of(at).lower(), "before findings: report shown as locked")

        print("\nExaminer: 'Requires further examination' needs acknowledgment")
        notes = [t for t in at.text_area if "findings" in t.label.lower()][0]
        notes.set_value("Response is weak; corroborate with metadata before any conclusion.")
        h.find_button(at, ["save", "findings"]).click()
        at.run()
        check(not at.exception, "save findings: no exception")
        check("findings saved" in text_of(at).lower(), "save findings: confirmation shown")
        fin = button(at, [], key="fcr_finalize")
        check(fin is not None, "after findings: finalize button present")
        check(any(cb.key == "fcr_ack" for cb in at.checkbox), "qualified conclusion: acknowledgment checkbox present")
        fin.click()
        at.run()
        check("qualified" in text_of(at).lower(), "finalize without acknowledgment: rejected with reason")
        check("report v1" not in text_of(at).lower() and "finalized as version" not in text_of(at).lower(),
              "finalize without acknowledgment: not shown as finalized")
        check(finalized_rows(temp) == 0, "finalize without acknowledgment: nothing stored")

        [cb for cb in at.checkbox if cb.key == "fcr_ack"][0].check()
        at.run()
        button(at, [], key="fcr_finalize").click()
        at.run()
        check(not at.exception, "finalize with acknowledgment: no exception")
        body = text_of(at).lower()
        check("report finalized as version 1" in body, "finalize: success message after backend confirmation")
        check("finalized." in body and "report v1" in body, "finalize: page-6 panel shows version 1")
        check("requires further examination" in body, "finalize: qualified conclusion shown")
        check(finalized_rows(temp) == 1, "finalize: exactly one record stored")
        check(button(at, [], key="fcr_finalize") is None, "after finalize: finalize button gone")
        check(any(b.key == "fcr_back_cc" for b in at.button), "after finalize: Back to command center present")

        print("\nRepeated and amended finalization")
        at.run()
        check(finalized_rows(temp) == 1, "rerun: no duplicate record")
        from forenchain.report_finalization import finalize_report, FinalizationError, get_report_audit_log
        from PIL import Image
        saved = at.session_state["ai_screening_result"]
        examiner_id = users["forensic_examiner01"]["user_id"]
        record, created = finalize_report(examiner_id, saved["evidence_id"], saved["analysis_id"],
                                          Image.new("RGB", (64, 48)), acknowledge_qualified=True)
        check(created is False and record["version"] == 1, "direct repeat call: idempotent, returns v1")
        check(finalized_rows(temp) == 1, "direct repeat call: still one record")
        judge_id = users["judicial_reviewer01"]["user_id"]
        try:
            finalize_report(judge_id, saved["evidence_id"], saved["analysis_id"], Image.new("RGB", (64, 48)))
            check(False, "Judicial Authority blocked in backend")
        except PermissionError:
            check(True, "Judicial Authority blocked in backend")
        outcomes = [(r["action"], r["outcome"]) for r in get_report_audit_log(saved["evidence_id"])]
        check(("FINALIZE", "SUCCESS") in outcomes, "audit: success recorded")
        check(("FINALIZE", "ACKNOWLEDGMENT_REQUIRED") in outcomes, "audit: rejected attempt recorded")
        check(("FINALIZE", "ALREADY_FINALIZED") in outcomes, "audit: repeat recorded")
        check(("FINALIZE", "DENIED") in outcomes, "audit: denied attempt recorded")
    finally:
        shutil.rmtree(temp, ignore_errors=True)

    print(f"\n{'ALL CHECKS PASSED' if not h.FAILURES else str(len(h.FAILURES)) + ' CHECK(S) FAILED'}")
    return 1 if h.FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
