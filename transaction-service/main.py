import os, asyncio, json, uuid
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from jose import jwt
import aio_pika

app = FastAPI(title="transaction-service")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
ALGO = "HS256"

connection: aio_pika.RobustConnection = None
channel: aio_pika.abc.AbstractChannel = None
exchange: aio_pika.Exchange = None

async def startup():
    global connection, channel, exchange
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    exchange = await channel.declare_exchange("bank", aio_pika.ExchangeType.TOPIC)
    # Ensure queues exist (ledger, notifications)
    q = await channel.declare_queue("transactions", durable=True)
    await q.bind(exchange, routing_key="transaction.initiated")

@app.on_event("startup")
async def on_start():
    await startup()

@app.on_event("shutdown")
async def on_shutdown():
    if connection:
        await connection.close()

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
    await exchange.publish(
        aio_pika.Message(body=json.dumps(message).encode(), content_type="application/json", delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key="transaction.initiated"
    )
    return {"accepted": True, "tx_id": tx_id}
