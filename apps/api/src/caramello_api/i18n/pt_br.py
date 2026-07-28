"""pt-BR message catalog — the single locale the product ships today.

Keys are namespaced by surface: `auth.*` mirrors the `reason` codes raised in
`shared/auth.py`, `families.*` and `finances.*` the ones raised in each
domain's `operations.py` / `services.py`. Values are end-user-facing text and
therefore pt-BR, per the language policy in the root `AGENTS.md`.

A value may carry `str.format` placeholders; `translate(key, **params)`
interpolates them (see `i18n/__init__.py`).
"""

MESSAGES: dict[str, str] = {
    # -----------------------------------------------------------------------
    # Authentication and authorization — reasons raised in `shared/auth.py`
    # and by the role guards in `families/operations.py`.
    # -----------------------------------------------------------------------
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
    # Both membership messages are raised from two places — `shared/auth.py`
    # (`require_family_access`) and the `families` role guards — and are
    # deliberately catalogued once: same text, same meaning, one entry.
    "auth.not_family_member": "Você não é membro desta família",
    "auth.not_owner": "Apenas owner pode realizar esta operação",
    # -----------------------------------------------------------------------
    # crud — the generated CRUD routers (`{domain}/router.py`).
    #
    # Owned by the generator, which emits `crud.<table_name>_not_found` for
    # every entity that opts into a router. Adding an entity with
    # `generate_router: true` therefore means adding a key here — the contract
    # test in `tests/test_i18n.py` fails otherwise. The text duplicates some
    # `families.*`/`finances.*` entries on purpose: these are a distinct,
    # generator-owned surface, and collapsing them would couple hand-written
    # operations to whatever the generator happens to emit next.
    # -----------------------------------------------------------------------
    "crud.user_not_found": "Usuário não encontrado",
    "crud.family_not_found": "Família não encontrada",
    # -----------------------------------------------------------------------
    # families — `families/operations.py`
    # -----------------------------------------------------------------------
    "families.user_not_found": "Usuário não encontrado",
    "families.user_not_family_member": "Usuário não é membro desta família",
    # -----------------------------------------------------------------------
    # finances — `finances/operations.py`
    # -----------------------------------------------------------------------
    "finances.family_not_found": "Família não encontrada",
    "finances.account_not_found": "Conta não encontrada",
    "finances.category_not_found": "Categoria não encontrada",
    "finances.subcategory_not_found": "Subcategoria não encontrada",
    "finances.movement_not_found": "Movimentação não encontrada",
    "finances.entry_not_found": "Lançamento não encontrado",
    "finances.movement_already_exists": "Movimentação já existe",
    "finances.movement_already_reconciled": "Movimentação já possui lançamento financeiro",
    "finances.responsible_user_not_found": "Usuário responsável não encontrado",
    "finances.responsible_not_family_member": "Responsável não é membro desta família",
    # -----------------------------------------------------------------------
    # finances — statement parsing (`finances/services.py`). These reach the
    # user as `error_lines[].reason` in the import review screen, so they are
    # display text just like an HTTP error message.
    # -----------------------------------------------------------------------
    "finances.parse_invalid_date": "Linha {line}: data inválida {value!r}",
    "finances.parse_missing_date": "Linha {line}: data ausente",
    "finances.parse_invalid_amount": "amount inválido: {value!r}",
    "finances.parse_insufficient_columns": "Linha com colunas insuficientes",
    "finances.parse_missing_column": "Coluna obrigatória ausente: {detail}",
    "finances.parse_transaction_missing_date": "Transação {index}: data ausente",
    "finances.parse_too_many_errors": (
        "Mais de 50% das linhas falharam ({failed}/{total}). Verificar formato do arquivo."
    ),
    "finances.unsupported_import_format": "Formato não suportado: {format!r}",
    # Row grouping every entry with no responsible member (D-REP-02): it is a
    # label on a report, not an error.
    "finances.unassigned_member": "Não atribuído",
}
