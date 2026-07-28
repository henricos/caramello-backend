"""pt-BR message catalog — the single locale the product ships today.

Keys are namespaced by surface (`auth.*` mirrors the `reason` codes raised in
`shared/auth.py`). Values are end-user-facing text and therefore pt-BR, per
the language policy in the root `AGENTS.md`.

Only the authentication surface is catalogued so far; the pt-BR strings still
hardcoded in `families/` and `finances/` operations move here in a later
phase.
"""

MESSAGES: dict[str, str] = {
    # The call site used to return the English literal "Not authenticated";
    # an end-user-facing string in a pt-BR catalog must be pt-BR, so this is
    # the one message whose text changed while moving here. The `reason` code
    # was later renamed from `not_authenticated` to `missing_token`, aligning
    # with the portfolio template and with the `POST /auth/verify` contract the
    # web module codes against.
    "auth.missing_token": "Credencial de acesso ausente. Faça login novamente.",
    "auth.invalid_token": "Token inválido",
    "auth.expired_token": "Token expirado",
    "auth.missing_kid": "Token sem 'kid' no header",
    "auth.unknown_kid": "kid não reconhecido",
    "auth.missing_sub": "Token sem claim 'sub'",
    "auth.email_not_verified": "Seu e-mail ainda não foi verificado no provedor de login.",
    # Deliberately generic: the text must not reveal whether the address is on
    # the allowlist, known to the system, or unknown anywhere.
    "auth.not_allowlisted": "Sua conta não tem permissão para acessar este sistema.",
    "auth.provisioning_failed": "Falha ao provisionar usuário",
    "auth.not_family_member": "Você não é membro desta família",
    "auth.not_owner": "Apenas owner pode realizar esta operação",
}
