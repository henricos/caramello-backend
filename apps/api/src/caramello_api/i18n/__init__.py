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


def translate(key: str, locale: str = DEFAULT_LOCALE, **params: object) -> str:
    """Resolve `key` in the catalog for `locale`.

    Falls back to the default locale's catalog, and to the key itself when no
    entry exists — a missing translation must degrade to a readable code on
    the user's screen, never crash a request path.

    `params` are interpolated with `str.format`, so a catalog entry may carry
    placeholders (`"Linha {line}: ..."`). A placeholder the caller did not
    supply degrades to the raw template for the same reason: a broken message
    must not turn into a broken request. (A message may therefore not use
    `{locale}` as a placeholder name.)
    """
    catalog = _CATALOGS.get(locale) or _CATALOGS[DEFAULT_LOCALE]
    message = catalog.get(key, key)
    if not params:
        return message
    try:
        return message.format(**params)
    except (KeyError, IndexError, ValueError):
        return message


def error_detail(key: str, **params: object) -> dict[str, str]:
    """Build an error detail pairing a stable code with its localized text.

    `key` is the fully namespaced catalog key (`families.user_not_found`); the
    `reason` consumers branch on is its last segment, which keeps the wire
    contract free of the catalog's internal layout. `message` is display text
    and may change without breaking anyone.

    This mirrors `shared.auth._error_detail`, which predates it and hardcodes
    the `auth.` namespace of the only surface it serves.
    """
    return {"reason": key.rsplit(".", 1)[-1], "message": translate(key, **params)}
