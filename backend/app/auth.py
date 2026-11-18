"""Server-side verified Cognito access tokens and explicit demo-only identities."""
import jwt
from fastapi import Header, HTTPException
from app.config import APP_ENV, REGION, USER_POOL_ID, CLIENT_ID
import os

def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Bearer access token required")
    token = authorization.split(" ", 1)[1]
    if APP_ENV == "local" and os.getenv("ALLOW_DEV_AUTH", "false").lower() == "true":
        if token in ("dev-claimant", "dev-assessor"):
            role = token.removeprefix("dev-")
            return {"sub": role + "-demo", "role": role}
    if not USER_POOL_ID or not CLIENT_ID:
        raise HTTPException(503, "Cognito not configured")
    issuer = "https://cognito-idp." + REGION + ".amazonaws.com/" + USER_POOL_ID
    try:
        key = jwt.PyJWKClient(issuer + "/.well-known/jwks.json").get_signing_key_from_jwt(token)
        claims = jwt.decode(token, key.key, algorithms=["RS256"], issuer=issuer, options={"verify_aud": False}, leeway=30)
    except (jwt.PyJWTError, jwt.PyJWKClientError, ValueError):
        raise HTTPException(401, "Invalid or expired access token")
    if claims.get("token_use") != "access" or claims.get("client_id") != CLIENT_ID:
        raise HTTPException(401, "Wrong token type or application")
    groups = claims.get("cognito:groups", [])
    role = "assessor" if "assessor" in groups else "claimant" if "claimant" in groups else None
    if role is None:
        raise HTTPException(403, "User must be assigned to claimant or assessor group")
    return {"sub": claims["sub"], "role": role}

def assessor(user):
    if user["role"] != "assessor":
        raise HTTPException(403, "Assessor role required")
