from getpass import getpass
from forenchain.auth import create_user

username = input("Choose administrator username: ").strip()
password = getpass("Choose administrator password (12+ characters): ")
confirm = getpass("Confirm administrator password: ")

if password != confirm:
    raise SystemExit("Passwords do not match.")

try:
    create_user(username, password, "System Administrator")
    print("Initial administrator account created successfully.")
except ValueError as exc:
    print("Account creation failed:", exc)
