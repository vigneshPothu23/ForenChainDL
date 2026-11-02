"""Create the first administrator from the command line (local use).

Usage, from the project folder with the virtual environment active:
    python create_admin.py

If FORENCHAIN_SETUP_TOKEN is set, you are asked for it as well.
"""
import os
from getpass import getpass

from forenchain.auth import SETUP_TOKEN_ENV, create_initial_admin, initial_admin_required

if not initial_admin_required():
    raise SystemExit("An administrator already exists. Sign in to the app to manage users.")

token = getpass("Setup token: ") if os.environ.get(SETUP_TOKEN_ENV, "").strip() else None
username = input("Choose administrator username: ").strip()
password = getpass("Choose administrator password (12+ characters): ")
confirm = getpass("Confirm administrator password: ")

if password != confirm:
    raise SystemExit("Passwords do not match.")

try:
    create_initial_admin(username, password, token)
    print("Initial administrator account created successfully.")
except (ValueError, PermissionError) as exc:
    raise SystemExit(f"Account creation failed: {exc}")
