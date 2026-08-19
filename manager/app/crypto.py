import os

from cryptography.fernet import Fernet

# Encrypts BOINC account keys at rest for the saved-credential repository
# (manager/app/api/credentials.py). Deliberately separate from ADMIN_PASSWORD
# (auth.py): that gates *access* to the API, this protects *data already
# stored* in grid.db -- a real secret, not a login check, so it needs its
# own env var rather than being derived from the admin password. Read fresh
# from the environment each call (no caching) so tests can monkeypatch/set
# it per-test the same way auth.get_admin_password() does.
SECRET_KEY_ENV = "GRIDKEEPER_SECRET_KEY"


class SecretKeyNotConfigured(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = os.environ.get(SECRET_KEY_ENV)
    if not key:
        raise SecretKeyNotConfigured(
            f"set {SECRET_KEY_ENV} to use saved credentials -- generate one with: "
            'python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as e:
        raise SecretKeyNotConfigured(f"{SECRET_KEY_ENV} is not a valid Fernet key") from e


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
