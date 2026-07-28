"""Contract between the `reason`/message codes raised in the source and the i18n catalog.

Every authentication error body is `{"reason": <code>, "message": <text>}` and the
text comes from the catalog. A code with no catalog entry degrades to the key
itself on the user's screen (`translate()` returns the key), so the tests below
sweep the source and fail before that reaches anyone.

Two call shapes are swept:
  - `_error_detail("<reason>")` in `shared/auth.py`, which prefixes `auth.`
  - `error_detail("<namespaced.key>")` / `translate("<namespaced.key>")` in the
    domains, which name the catalog key in full
"""

from __future__ import annotations

import re
from pathlib import Path

from caramello_api.i18n import DEFAULT_LOCALE, error_detail, translate

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "caramello_api"

# Namespaces whose keys are named in full at the call site.
_NAMESPACES = ("auth", "families", "finances")


def _sources() -> list[str]:
    return [path.read_text() for path in SRC_DIR.rglob("*.py")]


def _auth_reasons_raised_in_the_source() -> set[str]:
    """Extract every `_error_detail("<reason>")` present in the source."""
    pattern = re.compile(r"""_error_detail\(\s*["']([a-z_]+)["']\s*\)""")
    reasons: set[str] = set()
    for content in _sources():
        reasons.update(pattern.findall(content))
    return reasons


def _catalog_keys_referenced_in_the_source() -> set[str]:
    """Extract every fully namespaced catalog key referenced in the source."""
    namespaces = "|".join(_NAMESPACES)
    pattern = re.compile(rf"""(?:error_detail|translate)\(\s*["']((?:{namespaces})\.[a-z_]+)["']""")
    keys: set[str] = set()
    for content in _sources():
        keys.update(pattern.findall(content))
    return keys


def test_default_locale_is_pt_br():
    assert DEFAULT_LOCALE == "pt-BR"


def test_every_auth_reason_raised_has_a_catalog_entry():
    reasons = _auth_reasons_raised_in_the_source()
    # Guards against a regex that stops matching and turns the test into a no-op.
    assert {"missing_token", "invalid_token", "email_not_verified", "not_allowlisted"} <= reasons

    for reason in sorted(reasons):
        key = f"auth.{reason}"
        assert translate(key) != key, f"{key} has no message in the pt-BR catalog"


def test_every_namespaced_key_referenced_has_a_catalog_entry():
    """A domain message with no entry cannot ship: the sweep is the gate."""
    keys = _catalog_keys_referenced_in_the_source()
    # Same guard as above — the domains must actually be represented.
    assert {
        "families.user_not_found",
        "finances.account_not_found",
        "finances.parse_too_many_errors",
    } <= keys, f"the sweep found too few keys, it is probably broken: {sorted(keys)}"

    for key in sorted(keys):
        assert translate(key) != key, f"{key} has no message in the pt-BR catalog"


def test_no_domain_message_is_left_hardcoded():
    """No pt-BR literal may sit in an HTTPException detail in the domains."""
    for module in ("families/operations.py", "finances/operations.py", "finances/services.py"):
        content = (SRC_DIR / module).read_text()
        offenders = [
            line.strip()
            for line in content.splitlines()
            if 'detail="' in line or "detail='" in line
        ]
        assert not offenders, f"{module} still returns a literal detail: {offenders}"


def test_error_detail_pairs_the_code_with_the_localized_text():
    detail = error_detail("finances.account_not_found")
    assert detail["reason"] == "account_not_found", "the wire code is the key's last segment"
    assert detail["message"] == translate("finances.account_not_found")
    assert detail["message"] != "finances.account_not_found"


def test_interpolated_message_keeps_its_values():
    message = translate("finances.parse_too_many_errors", failed=3, total=4)
    assert "3/4" in message


def test_interpolation_degrades_to_the_template_when_a_param_is_missing():
    """A broken message must not break the request path it travels on."""
    assert "{line}" in translate("finances.parse_invalid_date")


def test_missing_key_degrades_to_the_key_itself():
    assert translate("nonexistent.key") == "nonexistent.key"


def test_unknown_locale_falls_back_to_the_default():
    assert translate("auth.not_allowlisted", locale="xx-XX") == translate("auth.not_allowlisted")


def test_the_not_allowlisted_message_reveals_nothing():
    """The message is generic: it does not say whether the address exists anywhere."""
    message = translate("auth.not_allowlisted").lower()
    for leak in ("allowlist", "cadastr", "não existe", "inexistente", "convite"):
        assert leak not in message
