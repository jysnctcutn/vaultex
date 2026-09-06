"""Resolves the server's mode: basic or professional.

VAULTEX_MODE wins when set; otherwise a configured taxonomy implies
professional. Lives here rather than core/config.py so that module stays
taxonomy-unaware and there's no import cycle.
"""

from .config import VAULTEX_MODE, logger
from .taxonomy import custom_categories, roles

BASIC = "basic"
PROFESSIONAL = "professional"

if VAULTEX_MODE is not None and VAULTEX_MODE not in {BASIC, PROFESSIONAL}:
    raise SystemExit(
        f"VAULTEX_MODE must be '{BASIC}' or '{PROFESSIONAL}', got: {VAULTEX_MODE!r}"
    )

_HAS_TAXONOMY = any(roles.values()) or bool(custom_categories)

MODE = VAULTEX_MODE or (PROFESSIONAL if _HAS_TAXONOMY else BASIC)

if MODE == PROFESSIONAL and not _HAS_TAXONOMY:
    # Otherwise every structured tool registers and then fails at call time.
    logger.warning(
        "Professional mode with no taxonomy configured -- structured tools will "
        "report 'not configured'. Run `python3 onboard.py`, or set VAULTEX_MODE=basic."
    )
