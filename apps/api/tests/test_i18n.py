"""Contrato entre os códigos `reason` de autenticação e o catálogo i18n.

O corpo de todo erro de autenticação é `{"reason": <código>, "message": <texto>}`
e o texto vem do catálogo. Um `reason` sem entrada no catálogo degrada para a
própria chave na tela do usuário (`translate()` devolve a chave) — o teste
abaixo varre o código-fonte e falha antes de isso chegar a alguém.
"""

from __future__ import annotations

import re
from pathlib import Path

from caramello_api.i18n import DEFAULT_LOCALE, translate

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "caramello_api"


def _reasons_raised_in_the_source() -> set[str]:
    """Extrai todo `_error_detail("<reason>")` presente no código."""
    pattern = re.compile(r"""_error_detail\(\s*["']([a-z_]+)["']\s*\)""")
    reasons: set[str] = set()
    for path in SRC_DIR.rglob("*.py"):
        reasons.update(pattern.findall(path.read_text()))
    return reasons


def test_default_locale_is_pt_br():
    assert DEFAULT_LOCALE == "pt-BR"


def test_every_auth_reason_raised_has_a_catalog_entry():
    reasons = _reasons_raised_in_the_source()
    # Guarda contra um regex que pare de casar e transforme o teste em no-op.
    assert {"missing_token", "invalid_token", "email_not_verified", "not_allowlisted"} <= reasons

    for reason in sorted(reasons):
        key = f"auth.{reason}"
        assert translate(key) != key, f"{key} não tem mensagem no catálogo pt-BR"


def test_missing_key_degrades_to_the_key_itself():
    assert translate("nonexistent.key") == "nonexistent.key"


def test_unknown_locale_falls_back_to_the_default():
    assert translate("auth.not_allowlisted", locale="xx-XX") == translate("auth.not_allowlisted")


def test_the_not_allowlisted_message_reveals_nothing():
    """A mensagem é genérica: não diz se o endereço existe em lugar algum."""
    message = translate("auth.not_allowlisted").lower()
    for leak in ("allowlist", "cadastr", "não existe", "inexistente", "convite"):
        assert leak not in message
