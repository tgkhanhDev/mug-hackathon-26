from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService
from app.utils.exceptions import UnauthorizedException

security = HTTPBearer()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Dependency to extract user_id from the JWT access token.
    Raises UnauthorizedException if token is invalid or expired.
    """
    try:
        token = credentials.credentials
        payload = AuthService.verify_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Token payload missing subject (user_id)")
        return user_id
    except Exception as e:
        if isinstance(e, UnauthorizedException):
            raise e
        raise UnauthorizedException(f"Invalid authentication credentials: {str(e)}")
