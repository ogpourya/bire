"""RFC 5322 Section 3.4.1 full addr-spec email validator powered by bire."""

from __future__ import annotations

import re
from typing import Any

import bire

# 1. Dot-atom text characters (atext)
ATEXT = r"[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]"
ATOM = rf"{ATEXT}+"

# 2. Quoted-string (ASCII printable and whitespace excluding " and \, or quoted pairs)
QCONTENT = r"(?:[^\x00-\x08\x0a-\x1f\x7f\"\\]|\\[\x20-\x7e])"
QUOTED_STRING = rf'"{QCONTENT}*"'

# 3. Local-part = word *("." word)
WORD = rf"(?:{ATOM}|{QUOTED_STRING})"
LOCAL_PART = rf"{WORD}(?:\.{WORD})*"

# 4. Domain = dot-atom / domain-literal
SUB_DOMAIN = r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?"
DOMAIN_NAME = rf"{SUB_DOMAIN}(?:\.{SUB_DOMAIN})*"
DCONTENT = r"(?:[^\x00-\x08\x0a-\x1f\x7f\[\]\\]|\\[\x20-\x7e])"
DOMAIN_LITERAL = rf"\[{DCONTENT}*\]"
DOMAIN = rf"(?:{DOMAIN_NAME}|{DOMAIN_LITERAL})"

# 5. Full standard RFC 5322 email regex with named captures
RFC5322_EMAIL_REGEX = rf"^(?P<local>{LOCAL_PART})@(?P<domain>{DOMAIN})$"

RFC5322_EMAIL_DSL = bire.to_human(RFC5322_EMAIL_REGEX)
EMAIL_MATCHER: re.Pattern[Any] = bire.compile_human(RFC5322_EMAIL_DSL)


def validate_email(email: str) -> tuple[bool, str | None, str | None]:
    """Validate email against RFC 5322 specification.

    Returns (is_valid, local_part, domain).
    """
    m = EMAIL_MATCHER.fullmatch(email)
    if m:
        return True, m.group("local"), m.group("domain")
    return False, None, None
