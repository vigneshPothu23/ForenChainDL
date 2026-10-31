"""ForenChain-DL UI smoke test (safe: never touches your real data).

Copies app.py, forenchain/*.py and .streamlit/config.toml into a temporary
directory, seeds a throw-away SQLite database there, replaces MVS-Net with a
small deterministic stub (so no model weights are needed), and drives the
real Streamlit app with streamlit.testing.v1.AppTest for every role.

Usage (from the repository root):
    python tools/ui_smoke_test.py            # uses the stub model
    python tools/ui_smoke_test.py --keep     # keep the temp copy for inspection

Exit code 0 = all checks passed.
"""

import argparse
import shutil
import sys
import tempfile
import types
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
PASSWORD = "SmokeTest#Password2026"
FAILURES = []


def check(condition, message):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {message}")
    if not condition:
        FAILURES.append(message)


def copy_code(target: Path):
    shutil.copy2(REPO / "app.py", target / "app.py")
    (target / "forenchain").mkdir()
    for source in (REPO / "forenchain").glob("*.py"):
        shutil.copy2(source, target / "forenchain" / source.name)
    (target / ".streamlit").mkdir()
    config = REPO / ".streamlit" / "config.toml"
    if config.exists():
        shutil.copy2(config, target / ".streamlit" / "config.toml")


def install_model_stub():
    """Replace forenchain.forensics with a stub; the real module is never imported."""
    stub = types.ModuleType("forenchain.forensics")

    class MVSSForensics:
        def analyze(self, image):
            yy, xx = np.mgrid[0:512, 0:512]
            response = np.exp(-(((xx - 300) / 70.0) ** 2 + ((yy - 260) / 55.0) ** 2))
            response = (0.05 + 0.9 * response).astype(np.float32)
            return {
                "screening_score": float(response.max()),
                "localization_map": response,
                "device": "cpu",
            }

    stub.MVSSForensics = MVSSForensics
    sys.modules["forenchain.forensics"] = stub


def png_bytes(width, height, seed):
    rng = np.random.default_rng(seed)
    base = np.zeros((height, width, 3), dtype=np.uint8)
    base[..., 0] = np.linspace(40, 200, width, dtype=np.uint8)[None, :]
    base[..., 1] = np.linspace(60, 180, height, dtype=np.uint8)[:, None]
    base[..., 2] = rng.integers(60, 120, size=(height, width), dtype=np.uint8)
    buffer = BytesIO()
    Image.fromarray(base, "RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def seed(root: Path):
    from forenchain.auth import (
        change_password, create_initial_admin, create_user,
        initialize_auth_database, authenticate_user,
    )
    from forenchain.custody import record_custody_event
    from forenchain.evidence_store import ROOT, register_evidence

    from forenchain.analysis_history import initialize_findings_database

    assert ROOT == root, f"Temp copy not isolated: {ROOT} != {root}"
    initialize_auth_database()
    # A real deployment already has these tables once an analysis has been saved.
    initialize_findings_database()
    from forenchain.custody import initialize_custody
    initialize_custody()
    create_initial_admin("platform_admin", PASSWORD)
    admin = authenticate_user("platform_admin", PASSWORD)

    accounts = {
        "evidence_registrar01": "Investigator",
        "forensic_examiner01": "Forensic Examiner",
        "custody_officer01": "Evidence Custodian",
        "custody_officer02": "Evidence Custodian",
        "judicial_reviewer01": "Judicial Authority",
        "rbac_test_user": "Investigator",
    }
    users = {"platform_admin": admin}
    for username, role in accounts.items():
        create_user(admin["user_id"], username, "Initial#Password2026", role)
        user = authenticate_user(username, "Initial#Password2026")
        change_password(user["user_id"], "Initial#Password2026", PASSWORD)
        users[username] = authenticate_user(username, PASSWORD)

    registrar = users["evidence_registrar01"]["user_id"]
    evidence = {}
    # Registered first = listed last; the newest (default selection) is a clean file.
    for name, size, seed_value in [
        ("missing", (640, 480), 4),
        ("tampered", (800, 600), 3),
        ("portrait", (600, 900), 2),
        ("landscape", (1200, 800), 1),
    ]:
        result = register_evidence(
            png_bytes(*size, seed_value), f"{name}_exhibit.png",
            "CASE-SMOKE-01", size[0], size[1],
        )
        record_custody_event(result["evidence_id"], registrar, "REGISTERED", "Evidence registered")
        evidence[name] = result

    # Byte-level tamper and a missing file, inside the TEMP copy only.
    tampered = root / evidence["tampered"]["stored_path"]
    tampered.write_bytes(tampered.read_bytes() + b"\x00")
    (root / evidence["missing"]["stored_path"]).unlink()

    officer1 = users["custody_officer01"]["user_id"]
    officer2 = users["custody_officer02"]["user_id"]
    record_custody_event(evidence["portrait"]["evidence_id"], officer1, "TRANSFERRED", "custody_officer02")
    record_custody_event(evidence["portrait"]["evidence_id"], officer2, "ACCEPTED", "Received in sealed bag")
    return users, evidence


def login(app_path, username):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(app_path), default_timeout=120)
    at.run()
    check(not at.exception, f"{username}: login page renders without exceptions")
    fields = {t.label: t for t in at.text_input}
    check("Username" in fields and "Password" in fields, f"{username}: username and password fields present")
    fields["Username"].set_value(username)
    fields["Password"].set_value(PASSWORD)
    sign_in = [b for b in at.button if "sign" in b.label.lower()]
    check(bool(sign_in), f"{username}: sign-in button present")
    sign_in[0].click()
    at.run()
    check(not at.exception, f"{username}: signed in without exceptions")
    check(at.session_state["user"]["username"] == username, f"{username}: session holds authenticated user")
    return at


def texts(at):
    out = []
    for kind in ("markdown", "caption", "success", "error", "warning", "info"):
        for element in at.get(kind):
            out.append(str(getattr(element, "value", "")))
    return "\n".join(out)


def find_button(at, words, exclude_key=None):
    for button in at.button:
        if all(word in button.label.lower() for word in words) and (exclude_key is None or button.key != exclude_key):
            return button
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    temp = Path(tempfile.mkdtemp(prefix="forenchain_ui_smoke_"))
    print(f"Temporary copy: {temp}")
    try:
        copy_code(temp)
        sys.path.insert(0, str(temp))
        install_model_stub()
        users, evidence = seed(temp)
        app_path = temp / "app.py"

        # ---- wrong password is rejected
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(app_path), default_timeout=120)
        at.run()
        fields = {t.label: t for t in at.text_input}
        fields["Username"].set_value("forensic_examiner01")
        fields["Password"].set_value("wrong-password-123")
        [b for b in at.button if "sign" in b.label.lower()][0].click()
        at.run()
        check(at.session_state["user"] is None if "user" in at.session_state else True,
              "wrong password: no session created")
        check(any("invalid" in str(e.value).lower() for e in at.error), "wrong password: error shown")

        # ---- every role renders all of its tabs
        for username in users:
            if username == "rbac_test_user":
                continue
            print(f"\nRole check: {username}")
            at = login(app_path, username)
            tab_labels = [tab.label for tab in at.tabs]
            print(f"  tabs: {tab_labels}")
            check(len(tab_labels) > 0, f"{username}: tabs rendered")

        # ---- administrator: rbac_test_user hidden from the list, still in DB
        print("\nAccounts")
        at = login(app_path, "platform_admin")
        frames = at.dataframe
        shown = " ".join(str(frame.value) for frame in frames)
        check("rbac_test_user" not in shown, "rbac_test_user hidden from account list")
        from forenchain.auth import authenticate_user
        check(authenticate_user("rbac_test_user", PASSWORD) is not None, "rbac_test_user still exists in database")

        # ---- integrity: ok / mismatch / missing
        print("\nIntegrity")
        at = login(app_path, "evidence_registrar01")
        for name, expected in [("landscape", "verified"), ("tampered", "mismatch"), ("missing", "missing")]:
            box = [t for t in at.text_input if "evidence id" in t.label.lower()][0]
            box.set_value(evidence[name]["evidence_id"])
            find_button(at, ["verify", "integrity"], exclude_key="verify_ai_evidence").click()
            at.run()
            check(not at.exception, f"integrity {name}: no exception")
            check(expected in texts(at).lower(), f"integrity {name}: result shows '{expected}'")

        # ---- custody: global chain verification
        print("\nCustody")
        at = login(app_path, "custody_officer01")
        find_button(at, ["verify", "chain"]).click()
        at.run()
        check(not at.exception, "global chain verification: no exception")
        check("verified" in texts(at).lower(), "global chain verification: chain verified")

        # ---- examiner: AI screening, four modes, findings, PDF
        print("\nAI screening")
        at = login(app_path, "forensic_examiner01")
        find_button(at, ["run", "ai"]).click()
        at.run()
        check(not at.exception, "AI screening run: no exception")
        check("ai_screening_result" in at.session_state, "AI screening result stored in session")
        modes = ["Reveal Comparison", "Side-by-Side", "Heatmap Overlay", "Heatmap Only"]
        widget = None
        for kind in ("radio", "selectbox"):
            try:
                widget = getattr(at, kind)(key="forensics_comparison_view")
                break
            except KeyError:
                continue
        check(widget is not None and list(widget.options) == modes, "all four comparison modes offered, in order")
        for mode in modes:
            widget = None
            for kind in ("radio", "selectbox"):
                try:
                    widget = getattr(at, kind)(key="forensics_comparison_view")
                    break
                except KeyError:
                    continue
            widget.set_value(mode)
            at.run()
            check(not at.exception, f"mode '{mode}': renders without exception")
            check("unable to generate forensic report" not in texts(at).lower(), f"mode '{mode}': PDF builds")

        notes = [t for t in at.text_area if "findings" in t.label.lower()][0]
        notes.set_value("Smoke-test observation.")
        find_button(at, ["save", "findings"]).click()
        at.run()
        check(not at.exception, "save examiner findings: no exception")
        check("findings saved" in texts(at).lower(), "save examiner findings: confirmation shown")

        from forenchain.forensic_report import build_forensic_report_pdf
        pdf = build_forensic_report_pdf(
            {"evidence_id": "EV-TEST", "case_id": "CASE-SMOKE-01"},
            Image.new("RGB", (64, 48)), Image.new("RGB", (64, 48)),
        )
        check(pdf[:4] == b"%PDF", "forensic report PDF generator returns a PDF")
    finally:
        if args.keep:
            print(f"\nKept temporary copy at {temp}")
        else:
            shutil.rmtree(temp, ignore_errors=True)

    print(f"\n{'ALL CHECKS PASSED' if not FAILURES else str(len(FAILURES)) + ' CHECK(S) FAILED'}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
