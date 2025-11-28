from fastapi import Request, HTTPException
from app.utils.auth import decode_access_token

def get_current_user(request: Request):
    token = None

    if "token" in request.cookies:
        token = request.cookies.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    data = decode_access_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid token")

    return data  # { user_id: 1, role: "admin" }
