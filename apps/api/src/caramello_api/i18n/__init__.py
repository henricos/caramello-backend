"""Minimal i18n layer — the structural guarantee of the project's language policy.

The repository is English-only and the product is multilanguage with pt-BR as
the implemented locale (see the root `AGENTS.md`). Every human-readable string
this service returns to END USERS lives in a locale catalog and is resolved
through `translate()` — never hardcoded at the call site. Error responses keep
the machine-readable `reason` code as the contract; `message` is the
localized, displayable companion.

A dependency-free catalog was a deliberate choice over a framework: with a
single locale there is no negotiation or plural logic to buy, and adding a
locale later is adding a module to `_CATALOGS`.
"""

from caramello_api.i18n.pt_br import MESSAGES as _PT_BR_MESSAGES

DEFAULT_LOCALE = "pt-BR"

_CATALOGS: dict[str, dict[str, str]] = {
    "pt-BR": _PT_BR_MESSAGES,
}


def translate(key: str, locale: str = DEFAULT_LOCALE) -> str:
    """Resolve `key` in the catalog for `locale`.

    Falls back to the default locale's catalog, and to the key itself when no
    entry exists — a missing translation must degrade to a readable code on
    the user's screen, never crash a request path.
    """
    catalog = _CATALOGS.get(locale) or _CATALOGS[DEFAULT_LOCALE]
    return catalog.get(key, key)
