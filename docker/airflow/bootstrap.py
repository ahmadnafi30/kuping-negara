"""Create ignored local Docker secrets without printing their contents."""

import base64
import os
import secrets
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent / "secrets"
    root.mkdir(mode=0o700, exist_ok=True)
    values = {
        "postgres_password": secrets.token_hex(24),
        "jwt_secret": secrets.token_hex(32),
        "fernet_key": base64.urlsafe_b64encode(os.urandom(32)).decode(),
        "admin_password": secrets.token_urlsafe(24),
        "x_auth_token": "",  # User fills this locally; never request it in chat.
    }
    for name, value in values.items():
        target = root / name
        try:
            with target.open("x", encoding="utf-8") as file:
                file.write(value)
            # Compose file secrets are bind mounts; uid/mode remapping is not
            # supported. Non-root containers need read access to the inode.
            # The enclosing host directory is private (0700 on Linux).
            target.chmod(0o644)
        except FileExistsError:
            pass  # Running bootstrap again must preserve all configured secrets.
    print(
        "Local secrets ready. Fill docker/airflow/secrets/x_auth_token before collection."
    )


if __name__ == "__main__":
    main()
