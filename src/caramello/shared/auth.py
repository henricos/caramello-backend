"""Camada de autenticação Keycloak para o Caramello.

Provê:
  - fetch_jwks(): chamada no FastAPI lifespan para popular o cache JWKS
  - get_current_user(): dependency FastAPI que valida JWT + JIT provisioning
  - http_bearer: instância HTTPBearer usada como extrator do header Authorization

Padrão de uso em routers:
    from caramello.shared.auth import get_current_user
    @router.get("/me")
    async def me(user: User = Depends(get_current_user)) -> User:
        return user

Ver:
  - .planning/phases/03-estrutura-por-dom-nios-e-autentica-o/03-RESEARCH.md
    (Pattern 1, 2, 3 e Common Pitfalls 1, 2, 5)
  - .planning/phases/03-estrutura-por-dom-nios-e-autentica-o/03-CONTEXT.md
    (D-01 a D-05, D-12)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.core.config import settings
from caramello.shared.database import get_session

if TYPE_CHECKING:
    from caramello.users.models import User

# ----------------------------------------------------------------------
# Estado de módulo — análogo ao `engine` singleton em shared/database.py
# ----------------------------------------------------------------------

# Cache JWKS em memória: kid -> chave pública RSA (objeto opaco do pyjwt).
# Populado em fetch_jwks() no startup; re-populado em get_current_user
# quando um kid desconhecido aparece (key rotation).
_jwks_cache: dict[str, Any] = {}

# Extrator de Bearer token: auto_error=True levanta 403 quando header ausente.
# Mantemos esse comportamento (HTTPBearer já é coerente com AUTH-01).
http_bearer = HTTPBearer()


# ----------------------------------------------------------------------
# fetch_jwks — chamada no lifespan da FastAPI
# ----------------------------------------------------------------------


async def fetch_jwks() -> None:
    """Busca as chaves JWKS do Keycloak e popula _jwks_cache.

    Chamada no startup (lifespan) e re-chamada por get_current_user quando
    um kid desconhecido aparece (rotação de chaves).

    Pitfall #1 (research): o client nativo do PyJWT usa urllib síncrono e
    bloquearia o event loop. Por isso usamos httpx.AsyncClient.
    """
    jwks_url = (
        f"{settings.KEYCLOAK_URL.rstrip('/')}"
        f"/realms/{settings.KEYCLOAK_REALM}"
        "/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        jwks = response.json()

    new_cache: dict[str, Any] = {}
    for key_data in jwks.get("keys", []):
        kid = key_data.get("kid")
        if not kid:
            continue
        # RSAAlgorithm.from_jwk aceita dict ou JSON string
        new_cache[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)

    # Atualização atômica do cache (evita estado intermediário sob concorrência)
    _jwks_cache.clear()
    _jwks_cache.update(new_cache)


# ----------------------------------------------------------------------
# get_current_user — dependency injetada em todos os endpoints protegidos
# ----------------------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Valida o Bearer token e retorna o User (JIT provisioning incluído).

    Fluxo (D-12):
      1. Extrair kid do JWT header (sem verificar assinatura).
      2. Lookup no _jwks_cache; re-busca JWKS uma vez se kid desconhecido.
      3. jwt.decode com algorithms=['RS256'] (bloqueia downgrade explicitamente).
      4. Extrair claims (sub, email, name | preferred_username) — D-03.
      5. INSERT ON CONFLICT DO NOTHING — operação atômica (D-12, AUTH-02).
      6. SELECT do User para retornar (ON CONFLICT DO NOTHING não retorna
         a linha — pitfall #5).
      7. AUTO-JOIN (Phase 4 D-02): busca FamilyInvitation pendente por email;
         se existe, cria FamilyMember(role="member") + atualiza invitation.status.

    Aud claim: D-02 manda iniciar com verify_aud=False; uma task de
    inspeção de token real (Plan 05) decide quando ativar.
    """
    # Import lazy do User para evitar import circular
    # (TYPE_CHECKING resolve estaticamente)
    from caramello.users.models import User

    token = credentials.credentials

    # 1. Extrair kid do header sem validar (necessário para lookup no cache)
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.DecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        ) from exc

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sem 'kid' no header",
        )

    # 2. Buscar chave do cache; re-buscar JWKS se kid desconhecido (rotação)
    public_key = _jwks_cache.get(kid)
    if public_key is None:
        await fetch_jwks()
        public_key = _jwks_cache.get(kid)
        if public_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="kid não reconhecido",
            )

    # 3. Validar JWT — algorithms explícito para bloquear downgrade (T-3-03)
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            # D-02: começar com verify_aud=False; ativar após inspecionar token real
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        ) from exc

    # 4. Extrair claims (D-03)
    idp_sub_value = payload.get("sub")
    if not idp_sub_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sem claim 'sub'",
        )
    idp_sub: str = str(idp_sub_value)
    email: str = str(payload.get("email") or "")
    name: str = str(payload.get("name") or payload.get("preferred_username") or "")

    # 5. JIT provisioning com ON CONFLICT DO NOTHING (D-12, AUTH-02)
    # Race-condition-safe: requests concorrentes do mesmo usuário não criam duplicatas.
    insert_stmt = (
        pg_insert(User.__table__)  # type: ignore[attr-defined]
        .values(idp_sub=idp_sub, email=email, name=name)
        .on_conflict_do_nothing(index_elements=["idp_sub"])
    )
    await session.execute(insert_stmt)
    await session.commit()

    # 6. SELECT — ON CONFLICT DO NOTHING não retorna a linha (pitfall #5)
    result = await session.exec(select(User).where(User.idp_sub == idp_sub))
    user = result.first()
    if user is None:
        # Estado inesperado: insert aconteceu mas select falhou — caso raro de race
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao provisionar usuário",
        )

    # 7. AUTO-JOIN (Phase 4 D-02): se existe FamilyInvitation pendente com este email,
    # adicionar o usuário automaticamente como FamilyMember(role="member").
    # Import lazy para evitar ciclo entre shared/ e families/ (pitfall #3 RESEARCH.md).
    from caramello.families.models import (  # noqa: PLC0415
        FamilyInvitation,
        FamilyMember,
    )

    inv_result = await session.exec(
        select(FamilyInvitation).where(
            FamilyInvitation.email == email,
            FamilyInvitation.status == "pending_login",
        )
    )
    pending_inv = inv_result.first()
    if pending_inv is not None:
        new_member = FamilyMember(
            user_id=user.id,
            family_id=pending_inv.family_id,
            role="member",
        )
        session.add(new_member)
        pending_inv.status = "joined"
        session.add(pending_inv)
        await session.commit()

    return user
