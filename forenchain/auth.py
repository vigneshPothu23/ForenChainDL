
import hashlib
import hmac
import secrets
import sqlite3

from forenchain.evidence_store import DATABASE_PATH, initialize_database


ROLES = {
    "System Administrator",
    "Investigator",
    "Forensic Examiner",
    "Evidence Custodian",
    "Judicial Authority",
}

ROLE_PERMISSIONS = {
    "System Administrator": {"manage_users", "view_audit"},
    "Investigator": {
        "register_evidence", "view_evidence",
        "verify_integrity", "view_audit",
    },
    "Forensic Examiner": {
        "view_evidence", "verify_integrity",
        "analyze_image", "record_findings", "view_reports", "view_audit",
        "finalize_report",
    },
    "Evidence Custodian": {
        "view_evidence", "transfer_custody",
        "accept_custody", "view_audit",
    },
    "Judicial Authority": {
        "view_evidence", "verify_integrity",
        "view_reports", "view_audit",
    },
}

PASSWORD_ITERATIONS = 600_000
MIN_PASSWORD_LENGTH = 12


def initialize_auth_database():
    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(users)")
        }

        if "must_change_password" not in columns:
            connection.execute("""
                ALTER TABLE users
                ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0
            """)


def hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    ).hex()


def _validate_password(password: str):
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must contain at least {MIN_PASSWORD_LENGTH} characters."
        )


def _insert_user(connection, username, password, role, must_change_password):
    username = username.strip()

    if not username:
        raise ValueError("Username cannot be empty.")

    if role not in ROLES:
        raise ValueError("Invalid role.")

    _validate_password(password)

    salt = secrets.token_bytes(16)
    password_hash = hash_password(password, salt)

    try:
        connection.execute(
            """
            INSERT INTO users (
                username, password_salt, password_hash,
                role, must_change_password
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username,
                salt.hex(),
                password_hash,
                role,
                int(must_change_password),
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Username already exists.") from exc


def initial_admin_required() -> bool:
    initialize_auth_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM users WHERE role = ?",
            ("System Administrator",),
        ).fetchone()[0]

    return count == 0


def create_initial_admin(username: str, password: str):
    """Create the first administrator only when no administrator exists."""

    initialize_auth_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            "SELECT 1 FROM users WHERE role = ? LIMIT 1",
            ("System Administrator",),
        ).fetchone()

        if existing:
            raise ValueError(
                "An administrator already exists. Initial setup is closed."
            )

        _insert_user(
            connection,
            username,
            password,
            "System Administrator",
            must_change_password=False,
        )


def create_user(
    actor_user_id: int,
    username: str,
    password: str,
    role: str,
):
    """Create a non-administrator account for an authenticated administrator."""

    initialize_auth_database()

    if role == "System Administrator":
        raise ValueError(
            "Additional administrator creation is disabled in this prototype."
        )

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE")

        actor = connection.execute(
            """
            SELECT role, active
            FROM users
            WHERE user_id = ?
            """,
            (actor_user_id,),
        ).fetchone()

        if (
            actor is None
            or actor["active"] != 1
            or not has_permission(actor["role"], "manage_users")
        ):
            raise PermissionError(
                "Only an active administrator can create users."
            )

        _insert_user(
            connection,
            username,
            password,
            role,
            must_change_password=True,
        )


def authenticate_user(username: str, password: str):
    initialize_auth_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        user = connection.execute(
            """
            SELECT user_id, username, password_salt,
                   password_hash, role, active, must_change_password
            FROM users
            WHERE username = ?
            """,
            (username.strip(),),
        ).fetchone()

    if user is None or user["active"] != 1:
        return None

    salt = bytes.fromhex(user["password_salt"])
    candidate = hash_password(password, salt)

    if not hmac.compare_digest(candidate, user["password_hash"]):
        return None

    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
        "must_change_password": bool(user["must_change_password"]),
    }


def change_password(
    user_id: int,
    current_password: str,
    new_password: str,
):
    """Change a user's own password after verifying the current password."""

    initialize_auth_database()
    _validate_password(new_password)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE")

        user = connection.execute(
            """
            SELECT password_salt, password_hash, active
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if user is None or user["active"] != 1:
            raise ValueError("Active account not found.")

        current_hash = hash_password(
            current_password,
            bytes.fromhex(user["password_salt"]),
        )

        if not hmac.compare_digest(current_hash, user["password_hash"]):
            raise ValueError("Current password is incorrect.")

        if hmac.compare_digest(
            hash_password(new_password, bytes.fromhex(user["password_salt"])),
            user["password_hash"],
        ):
            raise ValueError("Choose a password different from the current one.")

        new_salt = secrets.token_bytes(16)
        new_hash = hash_password(new_password, new_salt)

        connection.execute(
            """
            UPDATE users
            SET password_salt = ?,
                password_hash = ?,
                must_change_password = 0
            WHERE user_id = ?
            """,
            (new_salt.hex(), new_hash, user_id),
        )


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
