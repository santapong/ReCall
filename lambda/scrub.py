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

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_HANDLE_RE = re.compile(r"@[A-Za-z0-9_.-]+")
_NAMES_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in sorted(NAME_LIST, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def scrub(text: str) -> str:
    """Strip emails first (so their @domain part can't survive as a handle),
    then bare @handles, then roster names. Idempotent."""
    text = _EMAIL_RE.sub(REDACTED, text)
    text = _HANDLE_RE.sub(REDACTED, text)
    text = _NAMES_RE.sub(REDACTED, text)
    return text
