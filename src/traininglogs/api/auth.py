"""Who is asking: the Supabase sign-in pass on each request, checked, and mapped to a user.

The app signs in with Supabase and sends its pass (a JWT) as `Authorization: Bearer <pass>`. The
server checks the signature against Supabase's published public keys, that the pass was issued by
this environment's project for signed-in users, and that it hasn't expired. The person is the
pass's `sub`, Supabase's account id; it maps to users.id, the id the data uses, and a user is added
on their first request. Sign-up is closed in Supabase, so a valid pass means an invited person.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Header, HTTPException

SIGNED_OUT = "You're signed out. Sign in again."


@lru_cache(maxsize=1)
def _keys() -> jwt.PyJWKClient:
    """Supabase's public signing keys, fetched once and cached; fetched again when a pass names a
    key not seen yet (Supabase rotated its keys)."""
    return jwt.PyJWKClient(f"{os.environ['SUPABASE_URL']}/auth/v1/.well-known/jwks.json")


def _signing_key(token: str):
    return _keys().get_signing_key_from_jwt(token).key


def verify(token: str) -> dict:
    """The pass's claims, or 401 if it isn't a valid, current pass from this project."""
    try:
        return jwt.decode(
            token,
            _signing_key(token),
            algorithms=["ES256"],
            audience="authenticated",
            issuer=f"{os.environ['SUPABASE_URL']}/auth/v1",
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except (jwt.PyJWTError, KeyError) as exc:
        raise HTTPException(status_code=401, detail=SIGNED_OUT) from exc


def user_for(conn, claims: dict) -> str:
    """users.id for the pass's account, adding the user on their first request. Two first requests
    at once still make one user: the second insert does nothing and both read the same row."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE auth_id = %s", (claims["sub"],))
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "INSERT INTO users (auth_id, email) VALUES (%s, %s) ON CONFLICT (auth_id) DO NOTHING",
                (claims["sub"], claims.get("email")),
            )
            conn.commit()
            cur.execute("SELECT id FROM users WHERE auth_id = %s", (claims["sub"],))
            row = cur.fetchone()
    return str(row[0])


def bearer(authorization: Annotated[str, Header()] = "") -> str:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail=SIGNED_OUT)
    return token
