import os
from fastapi import Request, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.api_key import APIKeyHeader
import jwt
from jwt import PyJWKClient
import hmac
import hashlib
from slowapi import Limiter
from slowapi.util import get_remote_address


SUPABASE_URL = os.environ["SUPABASE_URL"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
jwks_client = PyJWKClient(jwks_url)

security_bearer = HTTPBearer()
limiter = Limiter(key_func=get_remote_address)


async def verify_jwt(
    credentials: HTTPAuthorizationCredentials = Security(security_bearer),
):
    """Validate a bearer JWT issued by Supabase and return its payload.

    Args:
        credentials: The bearer token credentials provided in the Authorization header.

    Raises:
        HTTPException: If the token is missing, malformed, expired, or cannot be validated.
        HTTPException: If the token payload does not include a subject claim.

    Returns:
        dict: The decoded JWT payload for the authenticated user.
    """
    token = credentials.credentials
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["HS256", "ES256", "RS256"],
            options={"verify_aud": False},
        )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=401, detail="Invalid token: missing subject"
            )

        return payload

    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Error validating token.")


async def verify_webhook_signature(request: Request):
    """Validate the incoming webhook signature for the Slancio payload.
    ...
    """
    signature_header = request.headers.get("X-Slancio-Signature")

    if not signature_header:
        raise HTTPException(status_code=401, detail="Webhook signature missing")

    raw_body = await request.body()

    expected_sig = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, signature_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return True


API_KEY_NAME = "X-API-Key"
MASTER_API_KEY = os.environ["API_KEY"]

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """Validate the master API key sent in the configured custom header.

    Args:
        api_key: API key value received from the X-API-Key header.

    Raises:
        HTTPException: If the provided API key does not match the configured master key.

    Returns:
        str: The validated API key when authorization succeeds.
    """
    if api_key == MASTER_API_KEY:
        return api_key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key.",
    )
