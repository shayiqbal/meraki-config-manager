"""Profile store — encrypted per-user credential management.

Profiles are stored in:
  Windows:  %APPDATA%\\GrayBar Meraki Manager\\profiles.json
  macOS:    ~/Library/Application Support/GrayBar Meraki Manager/profiles.json
  Linux:    ~/.local/share/GrayBar Meraki Manager/profiles.json

Each profile entry:
  {
    "username":       "<plain text>",
    "password_hash":  "<hex — PBKDF2-HMAC-SHA256 with unique salt>",
    "salt":           "<hex — 32 random bytes used for both hash and key derivation>",
    "api_key_enc":    "<base64 — Fernet-AES128-CBC encrypted API key>"
  }

Security properties:
  - Passwords are never stored in plaintext.
  - The encryption key for the API key is derived from the user's password
    via PBKDF2 (310,000 iterations, SHA-256).  Without the correct password
    the API key cannot be decrypted.
  - Even full read access to profiles.json reveals nothing usable.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import secrets


# ── Storage path ───────────────────────────────────────────────────────────────

_APP_DIR_NAME = "GrayBar Meraki Manager"


def _app_data_dir() -> Path:
    """Return the platform-appropriate application data directory."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / _APP_DIR_NAME


def _profiles_path() -> Path:
    d = _app_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "profiles.json"


# ── Internal helpers ───────────────────────────────────────────────────────────

def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte Fernet key from password + salt via PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=310_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def _hash_password(password: str, salt: bytes) -> str:
    """Return hex-encoded PBKDF2 hash of the password."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations=310_000,
    )
    return dk.hex()


def _load_profiles() -> list[dict]:
    path = _profiles_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_profiles(profiles: list[dict]) -> None:
    with _profiles_path().open("w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)


# ── Public API ─────────────────────────────────────────────────────────────────

def list_usernames() -> list[str]:
    """Return all registered usernames (case-preserving)."""
    return [p["username"] for p in _load_profiles()]


def username_exists(username: str) -> bool:
    return any(
        p["username"].lower() == username.strip().lower()
        for p in _load_profiles()
    )


def create_profile(username: str, password: str, api_key: str) -> None:
    """Create a new profile.  Raises ValueError if username already taken."""
    username = username.strip()
    if not username:
        raise ValueError("Username cannot be empty.")
    if not password:
        raise ValueError("Password cannot be empty.")
    if not api_key.strip():
        raise ValueError("API key cannot be empty.")
    if username_exists(username):
        raise ValueError(f"Username '{username}' is already taken.")

    salt = secrets.token_bytes(32)
    password_hash = _hash_password(password, salt)
    key = _derive_key(password, salt)
    fernet = Fernet(key)
    api_key_enc = fernet.encrypt(api_key.strip().encode("utf-8")).decode("utf-8")

    profiles = _load_profiles()
    profiles.append({
        "username":      username,
        "password_hash": password_hash,
        "salt":          salt.hex(),
        "api_key_enc":   api_key_enc,
    })
    _save_profiles(profiles)


def authenticate(username: str, password: str) -> str:
    """Verify credentials and return the decrypted API key.

    Raises:
        ValueError: if username not found or password is wrong.
    """
    username = username.strip()
    profiles = _load_profiles()
    profile = next(
        (p for p in profiles if p["username"].lower() == username.lower()),
        None,
    )
    if profile is None:
        raise ValueError(
            f"No profile found for '{username}'.\n"
            "Please go back and create a new profile first."
        )

    salt = bytes.fromhex(profile["salt"])
    expected_hash = _hash_password(password, salt)
    if not secrets.compare_digest(expected_hash, profile["password_hash"]):
        raise ValueError("Incorrect password. Please try again.")

    key = _derive_key(password, salt)
    fernet = Fernet(key)
    try:
        api_key = fernet.decrypt(profile["api_key_enc"].encode("utf-8")).decode("utf-8")
    except Exception:
        raise ValueError("Failed to decrypt API key. The profile may be corrupted.")

    return api_key


def delete_profile(username: str) -> bool:
    """Delete a profile by username (no password required — user confirmed forgetting).

    Returns True if deleted, False if username was not found.
    """
    username = username.strip()
    profiles = _load_profiles()
    new_profiles = [
        p for p in profiles
        if p["username"].lower() != username.lower()
    ]
    if len(new_profiles) == len(profiles):
        return False
    _save_profiles(new_profiles)
    return True
