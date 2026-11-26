"""
auth.py - User authentication (procedural, no classes)

Uses salted PBKDF2 password hashing from the standard library.
Depends on db.py (execute, fetch_one).

NOTE: password_hash must be at least VARCHAR(255). Run once:
    ALTER TABLE users MODIFY password_hash VARCHAR(255) NOT NULL;
"""
import os
import re
import hashlib
import hmac
import getpass

import mysql.connector
from db import execute, fetch_one

ITERATIONS = 100_000
MIN_PASSWORD_LEN = 6


# ---------------------------------------------------------------- hashing
def hash_password(password, salt=None):
    """Return 'salt$hash' (both hex). Generates a new salt if none given."""
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return salt.hex() + "$" + digest.hex()


def verify_password(password, stored):
    """Check a plain password against a stored 'salt$hash' string."""
    try:
        salt_hex, _ = stored.split("$")
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, stored)


# ------------------------------------------------------------- validation
def validate_username(username):
    """Return (ok, message). 3-30 chars: letters, digits, underscore."""
    if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
        return False, "Username must be 3-30 characters (letters, digits, underscore)."
    return True, ""


def validate_password(password):
    """Return (ok, message)."""
    if len(password) < MIN_PASSWORD_LEN:
        return False, f"Password must be at least {MIN_PASSWORD_LEN} characters."
    if password.isalpha() or password.isdigit():
        return False, "Password must mix letters and digits (or symbols)."
    return True, ""


# --------------------------------------------------------------- accounts
def register_user(username, password):
    """Create a new account. Returns (success, message)."""
    username = username.strip()
    ok, msg = validate_username(username)
    if not ok:
        return False, msg
    ok, msg = validate_password(password)
    if not ok:
        return False, msg

    try:
        execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (username, hash_password(password)),
        )
    except mysql.connector.IntegrityError:
        return False, "That username is already taken."
    return True, "Account created successfully."


def login_user(username, password):
    """Return the user dict {'user_id', 'username'} on success, else None."""
    row = fetch_one(
        "SELECT user_id, username, password_hash FROM users WHERE username = %s",
        (username.strip(),),
    )
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return {"user_id": row["user_id"], "username": row["username"]}


def get_user(user_id):
    """Fetch basic info about a user (or None)."""
    return fetch_one(
        "SELECT user_id, username, created_at FROM users WHERE user_id = %s",
        (user_id,),
    )


def change_password(user_id, old_password, new_password):
    """Returns (success, message)."""
    row = fetch_one("SELECT password_hash FROM users WHERE user_id = %s", (user_id,))
    if row is None or not verify_password(old_password, row["password_hash"]):
        return False, "Current password is incorrect."
    ok, msg = validate_password(new_password)
    if not ok:
        return False, msg
    execute(
        "UPDATE users SET password_hash = %s WHERE user_id = %s",
        (hash_password(new_password), user_id),
    )
    return True, "Password changed."


def delete_account(user_id, password):
    """Delete the account and (via ON DELETE CASCADE) all its projects/files."""
    row = fetch_one("SELECT password_hash FROM users WHERE user_id = %s", (user_id,))
    if row is None or not verify_password(password, row["password_hash"]):
        return False, "Password is incorrect."
    execute("DELETE FROM users WHERE user_id = %s", (user_id,))
    return True, "Account deleted."


# ------------------------------------------------------- console interface
def register_screen():
    print("\n--- Register ---")
    username = input("Choose a username: ")
    password = getpass.getpass("Choose a password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        return
    ok, msg = register_user(username, password)
    print(msg)


def login_screen():
    print("\n--- Login ---")
    username = input("Username: ")
    password = getpass.getpass("Password: ")
    user = login_user(username, password)
    if user is None:
        print("Invalid username or password.")
    else:
        print(f"Welcome back, {user['username']}!")
    return user


def auth_menu():
    """Loop until the user logs in. Returns the user dict, or None if they quit."""
    while True:
        print("\n=== AUDIO STUDIO ===")
        print("1. Login")
        print("2. Register")
        print("3. Exit")
        choice = input("Choose: ").strip()
        if choice == "1":
            user = login_screen()
            if user:
                return user
        elif choice == "2":
            register_screen()
        elif choice == "3":
            return None
        else:
            print("Please enter 1, 2 or 3.")


if __name__ == "__main__":
    current_user = auth_menu()
    print("Logged in as:", current_user)