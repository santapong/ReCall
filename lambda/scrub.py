"""Blameless-write scrubber (CLAUDE.md hard rule 3).

One function: scrub(text) -> str. Strips emails, @handles, and known-name
patterns. NAME_LIST is the single source of names shared with the seed
generator (infra/seed/generate.py imports it), so the zero-survivors test is
airtight: the generator can't emit a name the scrubber doesn't know.
"""

import re

# The Orbital engineer roster — fictional. The generator never emits these; the
# scrubber removes them anyway (defense in depth for the write-back path, AC5).
NAME_LIST = (
    "Alice Nakamura",
    "Ben Ortiz",
    "Chidi Okafor",
    "Dana Petrov",
    "Elena Vasquez",
    "Farid Haddad",
    "Grace Lindqvist",
    "Hiro Tanaka",
    "Ingrid Sørensen",
    "Jonas Weber",
    "Kavya Raman",
    "Liam Doyle",
    "Mai Pham",
    "Noor Rahimi",
    "Otis Brennan",
    "Priya Shah",
    # first names alone are also scrubbed
    "Alice",
    "Ben",
    "Chidi",
    "Dana",
    "Elena",
    "Farid",
    "Grace",
    "Hiro",
    "Ingrid",
    "Jonas",
    "Kavya",
    "Liam",
    "Mai",
    "Noor",
    "Otis",
    "Priya",
)

REDACTED = "[redacted]"

# Operational vocabulary that collides with a roster first name. Matching is
# IGNORECASE and must stay that way — the adversarial set requires bare lowercase
# "handoff from mai to noor" and "jonas said the cache was cold" to scrub, so
# case-sensitivity would trade a false positive for a real PII leak. Instead these
# exact phrases are protected before the name pass and restored after.
#
# This matters beyond tidiness: both committed corpora are name-free, so no existing
# test catches it, but the write-back path (AC5) scrubs a *human-typed* resolution
# and then embeds the result. "Token grace period expired" becoming "Token
# [redacted] period expired" corrupts the vector that the close→retrieve shot
# depends on matching against.
SAFE_PHRASES = (
    "grace period",
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_HANDLE_RE = re.compile(r"@[A-Za-z0-9_.-]+")
_NAMES_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in sorted(NAME_LIST, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_SAFE_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in sorted(SAFE_PHRASES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# Chosen so no realistic input contains it and the name/email/handle passes cannot
# match any part of it: no @, no letters from the roster, balanced and unambiguous.
_GUARD = "\x00{}\x00"
_GUARD_RE = re.compile(r"\x00(\d+)\x00")


def scrub(text: str) -> str:
    """Strip emails first (so their @domain part can't survive as a handle),
    then bare @handles, then roster names. Idempotent.

    Protected operational phrases (SAFE_PHRASES) are swapped for placeholders around
    the name pass, so vocabulary that happens to share a first name survives intact.
    """
    protected: list[str] = []

    def _hide(match: re.Match) -> str:
        protected.append(match.group(0))
        return _GUARD.format(len(protected) - 1)

    text = _SAFE_RE.sub(_hide, text)
    text = _EMAIL_RE.sub(REDACTED, text)
    text = _HANDLE_RE.sub(REDACTED, text)
    text = _NAMES_RE.sub(REDACTED, text)
    return _GUARD_RE.sub(lambda m: protected[int(m.group(1))], text)
