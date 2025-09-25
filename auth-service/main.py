from datetime import datetime, timedelta
from typing import Optional, Dict
import os

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

app = FastAPI(title="auth-service")

JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
ACCESS_MIN = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
ALGO = "HS256"

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
# DEMO: in-memory users; swap to DB later if you want
users: Dict[str, str] = {}  # username -> password_hash

class RegisterIn(BaseModel):
    username: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

def create_token(sub: str) -> str:
    exp = datetime.utcnow() + timedelta(minutes=ACCESS_MIN)
    return jwt.encode({"sub": sub, "exp": exp}, JWT_SECRET, algorithm=ALGO)

@app.post("/auth/register", response_model=TokenOut)
def register(body: RegisterIn):
    if body.username in users:
        raise HTTPException(409, "User exists")
    users[body.username] = pwd.hash(body.password)
    return TokenOut(access_token=create_token(body.username))

@app.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends()):
    username = form.username
    if username not in users or not pwd.verify(form.password, users[username]):
        raise HTTPException(401, "Invalid credentials")
    return TokenOut(access_token=create_token(username))
