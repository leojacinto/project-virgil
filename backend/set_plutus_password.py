#!/usr/bin/env python3
"""Set or reset the Plutus access password.

Generates a random 32-byte salt, hashes the password with PBKDF2-HMAC-SHA256
(200 000 iterations), and writes salt + hash to .plutus_key.

Usage:
    python set_plutus_password.py
"""

import hashlib
import os
import getpass
from pathlib import Path

KEY_PATH = Path(__file__).resolve().parent / ".plutus_key"


def main():
    print("Set Plutus access password")
    print("-" * 40)
    pw = getpass.getpass("New password: ")
    pw2 = getpass.getpass("Confirm password: ")
    if pw != pw2:
        print("Passwords do not match.")
        return
    if len(pw) < 4:
        print("Password must be at least 4 characters.")
        return

    salt = os.urandom(32)
    hashed = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    KEY_PATH.write_bytes(salt + hashed)
    print(f"Password saved to {KEY_PATH}")


if __name__ == "__main__":
    main()
