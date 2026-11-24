"""Single-use backup recovery codes, generated when a user enables their
first MFA factor. 10 codes, XXXX-XXXX-XXXX (60+ bits entropy), shown once,
stored individually as salted Argon2id hashes."""

import secrets
import string

from sonavault.core.security.passwords import hash_password, verify_password

CODE_COUNT = 10
GROUP_LEN = 4
GROUPS = 3
ALPHABET = string.ascii_uppercase + string.digits
LOW_BALANCE_WARNING_THRESHOLD = 3


def _generate_one() -> str:
    groups = ["".join(secrets.choice(ALPHABET) for _ in range(GROUP_LEN)) for _ in range(GROUPS)]
    return "-".join(groups)


def generate_codes() -> list[str]:
    return [_generate_one() for _ in range(CODE_COUNT)]


def hash_code(code: str) -> str:
    return hash_password(code.upper().strip())


def verify_code(code: str, code_hash: str) -> bool:
    return verify_password(code.upper().strip(), code_hash)
