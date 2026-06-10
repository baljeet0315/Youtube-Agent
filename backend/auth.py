"""
auth.py — Clerk JWT verification and user extraction
"""
import httpx
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from config import get_settings
from database import get_or_create_user

settings = get_settings()
security = HTTPBearer()

# Cache Clerk's public keys
_jwks_cache = None


async def get_clerk_jwks():
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.clerk.com/v1/jwks",
                                headers={"Authorization": f"Bearer {settings.clerk_secret_key}"})
        _jwks_cache = resp.json()
    return _jwks_cache


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    Verify Clerk JWT token and return the current user from our DB.
    Automatically creates the user on first login.
    """
    token = credentials.credentials

    try:
        jwks = await get_clerk_jwks()
        # Decode without verification first to get the key ID
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        # Find matching key
        public_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                from jose.backends import RSAKey
                public_key = RSAKey(key, algorithm="RS256")
                break

        if not public_key:
            raise HTTPException(status_code=401, detail="Invalid token key")

        payload = jwt.decode(token, public_key, algorithms=["RS256"])

        clerk_id = payload.get("sub")
        email = payload.get("email", "")

        if not clerk_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

    # Get or create user in our DB
    user = get_or_create_user(
        clerk_id=clerk_id,
        email=email,
        name=payload.get("name"),
        avatar_url=payload.get("image_url"),
    )

    return user
