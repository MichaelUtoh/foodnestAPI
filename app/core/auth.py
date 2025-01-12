from datetime import datetime, timedelta

import jwt
from decouple import config
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

from app.core import settings


class AuthHandler:
    security = HTTPBearer()
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    secret = settings.SECRET_KEY

    def get_password_hash(self, password):
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)

    def encode_token(self, user_id):
        payload = {
            "exp": datetime.now()
            + timedelta(days=0, minutes=int(settings.ACCESS_TOKEN_EXPIRE_MINUTES)),
            "iat": datetime.now(),
            "sub": user_id,
        }
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def encode_refresh_token(self, user_id):
        payload = {
            "exp": datetime.now()
            + timedelta(days=int(settings.REFRESH_TOKEN_EXPIRE_DAYS), minutes=0),
            "iat": datetime.now(),
            "sub": user_id,
        }
        return jwt.encode(payload, self.secret, algorithm="HS512")

    def decode_token(self, token):
        try:
            payload = jwt.decode(token, self.secret, algorithms=["HS256"])
            return payload["sub"]
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Signature has expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail="Invalid token")

    def auth_wrapper(self, auth: HTTPAuthorizationCredentials = Security(security)):
        return self.decode_token(auth.credentials)
