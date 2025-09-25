import os
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header
from sqlmodel import select, SQLModel, Session
from pydantic import BaseModel
from jose import jwt

from .db import init_db, get_session
from .models import Account, LedgerEntry

app = FastAPI(title="account-service")
init_db()

JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
ALGO = "HS256"
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "internal-dev-token")

def get_user(sub_header: Optional[str] = Header(default=None, alias="Authorization")) -> str:
    if not sub_header or not sub_header.lower().startswith("bearer "):
        raise HTTPException(401, "Missing token")
    token = sub_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGO])
        return payload["sub"]
    except Exception:
        raise HTTPException(401, "Invalid token")

class CreateAccountIn(BaseModel):
    owner_id: Optional[str] = None

class ApplyLedgerIn(BaseModel):
    account_id: int
    tx_id: str
    delta: float
    reason: str

@app.post("/accounts")
def create_account(body: CreateAccountIn, user=Depends(get_user), session: Session = Depends(get_session)):
    owner = body.owner_id or user
    acc = Account(owner_id=owner, balance=0.0)
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return {"id": acc.id, "owner_id": acc.owner_id, "balance": acc.balance}

@app.get("/accounts/{acc_id}")
def get_account(acc_id: int, user=Depends(get_user), session: Session = Depends(get_session)):
    acc = session.get(Account, acc_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    # you might restrict to owner == user; for demo we allow read
    return {"id": acc.id, "owner_id": acc.owner_id, "balance": acc.balance}

# Internal endpoint: protected by INTERNAL_TOKEN header
@app.post("/internal/apply_ledger")
def apply_ledger(
    body: ApplyLedgerIn,
    session: Session = Depends(get_session),
    internal: Optional[str] = Header(default=None, alias="X-Internal-Token")
):
    if internal != INTERNAL_TOKEN:
        raise HTTPException(401, "Unauthorized internal call")

    # Idempotency: if tx_id already exists, return OK (no-op)
    exists = session.exec(select(LedgerEntry).where(LedgerEntry.tx_id == body.tx_id)).first()
    if exists:
        return {"status": "idempotent_ok"}

    acc = session.get(Account, body.account_id)
    if not acc:
        raise HTTPException(404, "Account not found")

    # Business rule: cannot go negative on debit
    if body.delta < 0 and acc.balance + body.delta < 0:
        raise HTTPException(409, "Insufficient funds")

    acc.balance += body.delta
    le = LedgerEntry(account_id=acc.id, tx_id=body.tx_id, delta=body.delta, reason=body.reason)
    session.add(le)
    session.add(acc)
    session.commit()
    return {"status": "applied", "new_balance": acc.balance}
