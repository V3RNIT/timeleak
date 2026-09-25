"""
Reset and reseed the demo-app SQLite database with 20 fake users.

Usage:
    python seed.py
"""
import os
import sqlite3

import bcrypt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")

BCRYPT_ROUNDS = 10

# All seeded users share this password so the detector's "valid username"
# test case is predictable. It is only ever used against a local demo DB.
SEED_PASSWORD = "Password123!"

USERNAMES = [
    "alice", "bob", "carol", "dave", "erin", "frank", "grace", "heidi",
    "ivan", "judy", "mallory", "niaj", "olivia", "peggy", "quentin",
    "rupert", "sybil", "trent", "uma", "victor",
]


def reset_schema(conn):
    conn.execute("DROP TABLE IF EXISTS users")
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )
    conn.commit()


def seed_users(conn):
    password_hash = bcrypt.hashpw(SEED_PASSWORD.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)).decode("utf-8")
    rows = [
        (username, f"{username}@example.com", password_hash)
        for username in USERNAMES
    ]
    conn.executemany(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        reset_schema(conn)
        seed_users(conn)
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        print(f"Seeded {count} users into {DB_PATH}")
        print(f"All seeded users share the password: {SEED_PASSWORD}")
        print("Known-valid username for testing: alice")
        print("Known-invalid username for testing: notauser")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
