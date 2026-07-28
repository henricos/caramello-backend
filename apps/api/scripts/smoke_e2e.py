"""E2E smoke check for Phase 3 — Gap 2 (human verification).

Prerequisites:
- The app running on http://localhost:8000 (uvicorn caramello_api.main:app --reload)
- The environment configured with AUTH_OIDC_ISSUER, AUTH_OIDC_AUDIENCE, DATABASE_URL
- The caramello_dev database migrated (bin/manage_db upgrade)
- A valid access token exported as SMOKE_TOKEN

Usage:
    export SMOKE_TOKEN=$(...obtain a token through the password grant...)
    uv run python scripts/smoke_e2e.py

Output: prints PASS/FAIL per check and exits 0 when everything passed.

The business paths carry the `/api/v1` prefix; `GET /health` and the
`.well-known` documents deliberately do not (see `main.py`).
"""

from __future__ import annotations

import contextlib
import os
import sys
from typing import Any

import httpx

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://localhost:8000")
TOKEN = os.environ.get("SMOKE_TOKEN", "")

API_V1 = "/api/v1"


def _print_result(label: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {label}")
    if detail:
        print(f"       {detail}")


def check_unauthenticated() -> bool:
    """AUTH-01: GET /users/me with no token answers 401 or 403."""
    r = httpx.get(f"{BASE_URL}{API_V1}/users/me")
    ok = r.status_code in (401, 403)
    _print_result(
        "AUTH-01 (no token -> 401/403)",
        ok,
        f"status={r.status_code} body={r.text[:80]}",
    )
    return ok


def check_authenticated_get_me() -> tuple[bool, dict[str, Any]]:
    """USER-01: GET /users/me with a Bearer token answers 200 + uuid/email/name."""
    if not TOKEN:
        _print_result("USER-01 (with a token)", False, "SMOKE_TOKEN is not set")
        return False, {}
    r = httpx.get(
        f"{BASE_URL}{API_V1}/users/me",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    body: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        body = r.json()
    has_fields = r.status_code == 200 and "uuid" in body and "email" in body and "name" in body
    _print_result(
        "USER-01 (with a token -> 200 + uuid/email/name)",
        has_fields,
        f"status={r.status_code} body_keys={list(body.keys()) if body else 'n/a'}",
    )
    return has_fields, body


def check_idempotent_jit() -> bool:
    """AUTH-02: a second call with the same token changes neither the answer nor the state."""
    if not TOKEN:
        _print_result("AUTH-02 (idempotency)", False, "SMOKE_TOKEN is not set")
        return False
    r1 = httpx.get(
        f"{BASE_URL}{API_V1}/users/me",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    r2 = httpx.get(
        f"{BASE_URL}{API_V1}/users/me",
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
        "AUTH-02 (idempotency: two calls answer the same uuid)",
        ok,
        (f"r1.status={r1.status_code} r2.status={r2.status_code} uuids_equal={uuids_match}"),
    )
    return ok


def check_crud_requires_auth() -> bool:
    """AUTH-01 D-11: the generated CRUD endpoints reject an anonymous caller too."""
    endpoints = [f"{API_V1}/users/user/", f"{API_V1}/families/family/"]
    results = []
    for ep in endpoints:
        r = httpx.get(f"{BASE_URL}{ep}")
        results.append((ep, r.status_code in (401, 403), r.status_code))
    ok = all(passed for _, passed, _ in results)
    detail = "; ".join(f"{ep}->{code}" for ep, _, code in results)
    _print_result("AUTH-01 D-11 (CRUD with no token -> 401/403)", ok, detail)
    return ok


def check_health_is_unversioned() -> bool:
    """The probe answers on `/health`, with no version prefix and no token."""
    r = httpx.get(f"{BASE_URL}/health")
    versioned = httpx.get(f"{BASE_URL}{API_V1}/health")
    ok = r.status_code == 200 and versioned.status_code == 404
    _print_result(
        "HEALTH (unversioned 200, versioned 404)",
        ok,
        f"/health->{r.status_code} {API_V1}/health->{versioned.status_code}",
    )
    return ok


def inspect_token_audience() -> None:
    """D-02: inspect the token's 'aud' claim, to decide about verify_aud."""
    if not TOKEN:
        print("[INFO] D-02 'aud' analysis skipped — no SMOKE_TOKEN")
        return
    try:
        import jwt

        payload = jwt.decode(TOKEN, options={"verify_signature": False})
        aud = payload.get("aud")
        iss = payload.get("iss")
        sub = payload.get("sub")
        print("[INFO] D-02 token analysis:")
        print(f"       sub={sub}")
        print(f"       iss={iss}")
        print(f"       aud={aud!r} (type: {type(aud).__name__})")
        audience = os.environ.get("AUTH_OIDC_AUDIENCE", "")
        if audience:
            if isinstance(aud, str) and aud == audience:
                print("       RECOMMENDATION: keep verify_aud=True (aud == AUTH_OIDC_AUDIENCE)")
            elif isinstance(aud, list) and audience in aud:
                print("       RECOMMENDATION: keep verify_aud=True (AUTH_OIDC_AUDIENCE in aud)")
            else:
                print(
                    "       WARNING: aud does not match AUTH_OIDC_AUDIENCE —"
                    " this token will be rejected"
                )
    except Exception as exc:  # noqa: BLE001 — a diagnostic must never abort the run
        print(f"[WARN] D-02 analysis failed: {exc}")


def main() -> int:
    print(f"=== E2E smoke, Phase 3 — base_url={BASE_URL} ===")
    print(f"Token present: {bool(TOKEN)}")
    print()

    results: list[bool] = []
    results.append(check_health_is_unversioned())
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
    print(f"=== Result: {passed}/{total} checks passed ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
