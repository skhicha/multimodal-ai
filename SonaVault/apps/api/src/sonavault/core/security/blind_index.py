"""Domain-separated HMAC-SHA256 blind indexing.

Lets SonaVault look up encrypted fields (vessel_mmsi, observer_badge,
radio_callsign, ...) by exact match without ever storing or logging plaintext
in SQL. Uses a key independent from the AES master KEK
(SV_BLIND_INDEX_KEY_B64) so compromising one does not compromise the other.
"""

import base64
import hashlib
import hmac

from sonavault.config import get_settings


def _key() -> bytes:
    settings = get_settings()
    if not settings.blind_index_key_b64:
        raise RuntimeError("SV_BLIND_INDEX_KEY_B64 is not configured.")
    return base64.b64decode(settings.blind_index_key_b64)


def blind_index(value: str, *, domain: str) -> str:
    """domain namespaces the index, e.g. 'vessel_mmsi' vs 'observer_badge',
    so the same raw value in different fields hashes differently."""
    normalized = value.strip().lower()
    mac = hmac.new(_key(), f"{domain}:{normalized}".encode(), hashlib.sha256)
    return mac.hexdigest()
