"""Redaction helpers for values that must never reach logs or API responses.

Credentials are frequently embedded in clone URLs (``https://<token>@host/...``).
These helpers strip that userinfo so a source URL can be logged or surfaced in an
error without leaking the secret.
"""

from __future__ import annotations

import re

# Matches the userinfo of a URL ("scheme://user[:secret]@") in any text, so it
# works on full URLs and on error strings (e.g. git output) that contain one.
_URL_USERINFO = re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://)[^/@\s]+@")


def redact_url_credentials(text: str) -> str:
    """Replace any ``scheme://user:secret@`` userinfo with ``scheme://***@``."""
    return _URL_USERINFO.sub(r"\g<scheme>***@", text)
