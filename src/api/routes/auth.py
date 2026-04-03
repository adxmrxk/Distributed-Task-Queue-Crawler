from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.api.auth import verify_password, create_access_token
from src.core.config import settings

router = APIRouter()


@router.post("/token", summary="Get a JWT access token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate with username + password (form data) and receive a Bearer JWT.

    Use the token in subsequent requests via:
        Authorization: Bearer <token>

    Alternatively, pass an API key via the X-API-Key header.
    """
    if form_data.username != settings.ADMIN_USERNAME:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
    if not verify_password(form_data.password, settings.ADMIN_PASSWORD_HASH):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")

    token = create_access_token({"sub": form_data.username})
    return {"access_token": token, "token_type": "bearer"}
