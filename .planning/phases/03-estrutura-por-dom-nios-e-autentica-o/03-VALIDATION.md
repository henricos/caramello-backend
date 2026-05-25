---
phase: 3
slug: estrutura-por-dom-nios-e-autentica-o
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 3 — Validation Strategy

> Contrato de validação por fase para amostragem de feedback durante a execução.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.1 |
| **Config file** | nenhum — sem `[tool.pytest.ini_options]` em pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run ruff check src/ && uv run mypy src/`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| STRUCT-01 | — | — | STRUCT-01 | — | `grep -r "models/" src/` retorna vazio | Smoke (shell) | `grep -r "models/" src/ && exit 1 \|\| exit 0` | N/A | ⬜ pending |
| STRUCT-02 | — | — | STRUCT-02 | — | Generator produz `user/models.py` com campo `domain` | Unit | `uv run pytest tests/test_generator.py -x` | ❌ W0 | ⬜ pending |
| AUTH-01 | — | — | AUTH-01 | T-3-01 | `GET /user/me` sem token retorna 401 | Integration | `uv run pytest tests/test_auth.py::test_me_unauthenticated -x` | ❌ W0 | ⬜ pending |
| AUTH-02 | — | — | AUTH-02 | T-3-02 | Primeira request com token válido cria user no banco | Integration | `uv run pytest tests/test_auth.py::test_jit_provisioning -x` | ❌ W0 | ⬜ pending |
| AUTH-03 | — | — | AUTH-03 | — | `get_current_user` importável de `shared.auth` | Unit | `uv run pytest tests/test_auth.py::test_auth_module -x` | ❌ W0 | ⬜ pending |
| USER-01 | — | — | USER-01 | — | `GET /user/me` com token válido retorna `id`, `email`, `name` | Integration | `uv run pytest tests/test_user_operations.py::test_get_me -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_generator.py` — stubs para STRUCT-02 (generator com campo domain)
- [ ] `tests/test_auth.py` — stubs para AUTH-01, AUTH-02, AUTH-03 (usando `dependency_overrides` para mock de token)
- [ ] `tests/test_user_operations.py` — stubs para USER-01

**Nota sobre isolamento de banco:** Phase 5 implementa banco isolado (TEST-01). Nesta fase, testes de auth podem usar `dependency_overrides` para mockar `get_current_user` e evitar dependência de Keycloak real. Testes que precisam de banco real devem ser marcados como `@pytest.mark.integration` e excluídos da suite padrão até Phase 5.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `GET /user/me` com Bearer token Keycloak real retorna 200 | USER-01 | Requer Keycloak real — banco isolado vem na Phase 5 | 1. Obter token via Keycloak dev; 2. `curl -H "Authorization: Bearer {token}" http://localhost:8000/user/me`; 3. Verificar `id`, `email`, `name` no JSON |
| Claim `aud` do token real | AUTH-02 (D-02) | Valor real do `aud` depende da configuração do Keycloak existente | 1. Decodificar token JWT sem verificação; 2. Inspecionar claim `aud`; 3. Confirmar configuração da validação de audience em `shared/auth.py` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
