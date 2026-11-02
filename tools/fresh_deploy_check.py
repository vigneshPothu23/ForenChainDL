"""Fresh-deployment check (safe: runs on a temporary copy, never touches data/).

Simulates a brand-new Streamlit Cloud server: empty data/ folder, then every role,
the full examiner flow (screening, findings, finalization) and an app restart.

Usage, from the project folder:
    python tools/fresh_deploy_check.py .
"""
import shutil, sys, tempfile, types
from pathlib import Path
import numpy as np

repo = Path(sys.argv[1]).resolve()
tmp = Path(tempfile.mkdtemp(prefix="fresh_"))
shutil.copy2(repo / "app.py", tmp / "app.py")
shutil.copytree(repo / "forenchain", tmp / "forenchain", ignore=shutil.ignore_patterns("__pycache__"))
if (repo / ".streamlit").exists():
    shutil.copytree(repo / ".streamlit", tmp / ".streamlit")
assert not (tmp / "data").exists()
sys.path.insert(0, str(tmp))
stub = types.ModuleType("forenchain.forensics")
class MVSSForensics:
    def analyze(self, image):
        r = np.full((64, 64), 0.3, np.float32); r[20:40, 20:40] = 0.9
        return {"screening_score": 0.9, "localization_map": r, "device": "cpu"}
stub.MVSSForensics = MVSSForensics
sys.modules["forenchain.forensics"] = stub

from streamlit.testing.v1 import AppTest
PW = "FreshDeploy#Password2026"
fails = []
def check(ok, msg):
    print(("  [PASS] " if ok else "  [FAIL] ") + msg)
    if not ok: fails.append(msg)

# 1. very first page load on an empty server
at = AppTest.from_file(str(tmp / "app.py"), default_timeout=120); at.run()
check(not at.exception, "first load on empty data/: " + ("; ".join(str(e.value)[:120] for e in at.exception) if at.exception else "no exception"))

# 2. create accounts the way a fresh deployment would (admin, then users), nothing else seeded
from forenchain.auth import create_initial_admin, authenticate_user, create_user
import forenchain.auth as auth
try:
    create_initial_admin("admin01", PW, None)
except TypeError:
    create_initial_admin("admin01", PW)
admin = authenticate_user("admin01", PW)
roles = {"investigator01": "Investigator", "examiner01": "Forensic Examiner",
         "custodian01": "Evidence Custodian", "judge01": "Judicial Authority"}
for u, r in roles.items():
    create_user(admin["user_id"], u, PW, r)

import sqlite3
from forenchain.evidence_store import DATABASE_PATH
with sqlite3.connect(DATABASE_PATH) as c:   # test only: skip the forced password change screen
    c.execute("UPDATE users SET must_change_password = 0")

for user in ["admin01", *roles]:
    at = AppTest.from_file(str(tmp / "app.py"), default_timeout=120); at.run()
    f = {t.label: t for t in at.text_input}
    f["Username"].set_value(user); f["Password"].set_value(PW)
    [b for b in at.button if "sign" in b.label.lower()][0].click(); at.run()
    if at.text_input and any("new password" in t.label.lower() for t in at.text_input):
        pass  # must_change_password screen counts as rendered
    tabs = [t.label for t in at.tabs]
    for i in range(len(tabs)):
        pass
    errs = "; ".join(str(e.value)[:140] for e in at.exception)
    check(not at.exception and len(tabs) > 0, f"{user}: dashboard + tabs {tabs} render on fresh DB" + (f" -> {errs}" if errs else ""))
# 3. full examiner flow on the fresh deployment
from io import BytesIO
from PIL import Image
from forenchain.evidence_store import register_evidence
from forenchain.custody import record_custody_event
buf = BytesIO(); Image.new("RGB", (320, 240), (90, 120, 160)).save(buf, format="PNG")
inv = authenticate_user("investigator01", PW)
ev = register_evidence(buf.getvalue(), "fresh.png", "CASE-FRESH-01", 320, 240)
record_custody_event(ev["evidence_id"], inv["user_id"], "REGISTERED", "Evidence registered")

at = AppTest.from_file(str(tmp / "app.py"), default_timeout=120); at.run()
f = {t.label: t for t in at.text_input}
f["Username"].set_value("examiner01"); f["Password"].set_value(PW)
[b for b in at.button if "sign" in b.label.lower()][0].click(); at.run()
check(not at.exception, "examiner: dashboard with one evidence item")
[b for b in at.button if "run ai" in b.label.lower()][0].click(); at.run()
check(not at.exception and "ai_screening_result" in at.session_state, "examiner: AI screening run + analysis saved")
[t for t in at.text_area if "findings" in t.label.lower()][0].set_value("Fresh deployment check.")
[b for b in at.button if "save" in b.label.lower() and "findings" in b.label.lower()][0].click(); at.run()
check(not at.exception and "findings saved" in " ".join(str(m.value) for m in at.success).lower(), "examiner: findings saved")
[c for c in at.checkbox if c.key == "fcr_ack"][0].check(); at.run()
[b for b in at.button if b.key == "fcr_finalize"][0].click(); at.run()
body = " ".join(str(m.value) for m in at.markdown).lower() + " ".join(str(m.value) for m in at.success).lower()
check(not at.exception and "finalized as version 1" in body, "examiner: report finalized v1")

# 4. app restart on the same database: no duplicate init errors, records kept
import sqlite3
with sqlite3.connect(DATABASE_PATH) as c:
    before = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in
              ["users", "evidence", "custody_events", "analysis_records", "examiner_findings",
               "report_finalizations", "report_audit_log"]}
at = AppTest.from_file(str(tmp / "app.py"), default_timeout=120); at.run()
with sqlite3.connect(DATABASE_PATH) as c:
    after = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in before}
    triggers = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
check(not at.exception and before == after, f"restart keeps every record {after}")
check(len(triggers) == 4, f"append-only report triggers present: {sorted(triggers)}")

shutil.rmtree(tmp, ignore_errors=True)
print("FRESH DEPLOY: " + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED"))
sys.exit(1 if fails else 0)
