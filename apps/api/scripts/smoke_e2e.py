"""Smoke test E2E para Phase 3 — Gap 2 (verificação humana).

Pré-requisitos:
- App rodando em http://localhost:8000 (uvicorn caramello_api.main:app --reload)
- .env configurado com KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID, DB_*
- Banco familia_dev com migrations aplicadas (bin/manage_db upgrade)
- Token Keycloak válido exportado como SMOKE_TOKEN

Uso:
    export SMOKE_TOKEN=$(...obter token via fluxo de password grant...)
    uv run python scripts/smoke_e2e.py

Saída: imprime PASS/FAIL para cada verificação e exit code 0 se tudo passou.
"""

from __future__ import annotations

import contextlib
import os
import sys
from typing import Any

import httpx

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://localhost:8000")
TOKEN = os.environ.get("SMOKE_TOKEN", "")


def _print_result(label: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {label}")
    if detail:
        print(f"       {detail}")


def check_unauthenticated() -> bool:
    """AUTH-01: GET /user/me sem token retorna 401 ou 403."""
    r = httpx.get(f"{BASE_URL}/user/me")
    ok = r.status_code in (401, 403)
    _print_result(
        "AUTH-01 (sem token -> 401/403)",
        ok,
        f"status={r.status_code} body={r.text[:80]}",
    )
    return ok


def check_authenticated_get_me() -> tuple[bool, dict[str, Any]]:
    """USER-01: GET /user/me com Bearer token retorna 200 + uuid/email/name."""
    if not TOKEN:
        _print_result("USER-01 (com token)", False, "SMOKE_TOKEN não definido")
        return False, {}
    r = httpx.get(
        f"{BASE_URL}/user/me",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    body: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        body = r.json()
    has_fields = r.status_code == 200 and "uuid" in body and "email" in body and "name" in body
    _print_result(
        "USER-01 (com token -> 200 + uuid/email/name)",
        has_fields,
        f"status={r.status_code} body_keys={list(body.keys()) if body else 'n/a'}",
    )
    return has_fields, body


def check_idempotent_jit() -> bool:
    """AUTH-02: segunda chamada com mesmo token NÃO altera resposta nem causa erro."""
    if not TOKEN:
        _print_result("AUTH-02 (idempotência)", False, "SMOKE_TOKEN não definido")
        return False
    r1 = httpx.get(
        f"{BASE_URL}/user/me",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    r2 = httpx.get(
        f"{BASE_URL}/user/me",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    uuids_match: str
    if r1.status_code == 200 and r2.status_code == 200:
        uuids_match = str(r1.json().get("uuid") == r2.json().get("uuid"))
    else:
        uuids_match = "n/a"
    ok = (
        r1.status_code == 200
        and r2.status_code == 200
        and r1.json().get("uuid") == r2.json().get("uuid")
    )
    _print_result(
        "AUTH-02 (idempotência: duas chamadas retornam mesmo uuid)",
        ok,
        (f"r1.status={r1.status_code} r2.status={r2.status_code} uuids_equal={uuids_match}"),
    )
    return ok


def check_crud_requires_auth() -> bool:
    """AUTH-01 D-11: endpoints CRUD sem token também rejeitam."""
    endpoints = ["/user/", "/family/", "/family_invitation/"]
    results = []
    for ep in endpoints:
        r = httpx.get(f"{BASE_URL}{ep}")
        results.append((ep, r.status_code in (401, 403), r.status_code))
    ok = all(passed for _, passed, _ in results)
    detail = "; ".join(f"{ep}->{code}" for ep, _, code in results)
    _print_result("AUTH-01 D-11 (CRUD sem token -> 401/403)", ok, detail)
    return ok


def inspect_token_audience() -> None:
    """D-02: inspecionar claim 'aud' do token para decisão sobre verify_aud."""
    if not TOKEN:
        print("[INFO] D-02 análise de 'aud' pulada — sem SMOKE_TOKEN")
        return
    try:
        import jwt

        payload = jwt.decode(TOKEN, options={"verify_signature": False})
        aud = payload.get("aud")
        iss = payload.get("iss")
        sub = payload.get("sub")
        print("[INFO] D-02 análise do token:")
        print(f"       sub={sub}")
        print(f"       iss={iss}")
        print(f"       aud={aud!r} (tipo: {type(aud).__name__})")
        client_id = os.environ.get("KEYCLOAK_CLIENT_ID", "")
        if client_id:
            if isinstance(aud, str) and aud == client_id:
                print("       RECOMENDAÇÃO: ativar verify_aud=True (aud == KEYCLOAK_CLIENT_ID)")
            elif isinstance(aud, list) and client_id in aud:
                print("       RECOMENDAÇÃO: ativar verify_aud=True (KEYCLOAK_CLIENT_ID in aud)")
            else:
                print(
                    "       RECOMENDAÇÃO: manter verify_aud=False"
                    " (aud não bate com KEYCLOAK_CLIENT_ID)"
                )
    except Exception as exc:
        print(f"[WARN] D-02 análise falhou: {exc}")


def main() -> int:
    print(f"=== Smoke E2E Phase 3 — base_url={BASE_URL} ===")
    print(f"Token presente: {bool(TOKEN)}")
    print()

    results: list[bool] = []
    results.append(check_unauthenticated())
    results.append(check_crud_requires_auth())
    ok_get_me, _body = check_authenticated_get_me()
    results.append(ok_get_me)
    results.append(check_idempotent_jit())
    print()
    inspect_token_audience()
    print()

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"=== Resultado: {passed}/{total} checks passaram ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
