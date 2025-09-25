import os, asyncio, json, uuid
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from jose import jwt
from aiokafka import AIOKafkaProducer

app = FastAPI(title="transaction-service")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"))
JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
ALGO = "HS256"

producer: AIOKafkaProducer | None = None

async def startup():
    global producer
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKERS)
    await producer.start()

@app.on_event("startup")
async def on_start():
    await startup()

@app.on_event("shutdown")
async def on_shutdown():
    if producer:
        await producer.stop()

def get_user(auth: Optional[str] = Header(default=None, alias="Authorization")) -> str:
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Missing token")
    token = auth.split(" ", 1)[1]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[ALGO])["sub"]
    except Exception:
        raise HTTPException(401, "Invalid token")

class TransferIn(BaseModel):
    source_account_id: int
    target_account_id: int
    amount: float

@app.post("/transactions/transfer")
async def transfer(body: TransferIn, user=Depends(get_user), idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
    if body.amount <= 0:
        raise HTTPException(400, "amount must be > 0")

    tx_id = idempotency_key or str(uuid.uuid4())
    message = {
        "type": "transaction.initiated",
        "tx_id": tx_id,
        "source_account_id": body.source_account_id,
        "target_account_id": body.target_account_id,
        "amount": body.amount,
        "initiated_by": user
    }
    assert producer is not None
    await producer.send_and_wait("transaction.initiated", json.dumps(message).encode())
    return {"accepted": True, "tx_id": tx_id}
