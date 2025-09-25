import os, json, asyncio
from typing import Optional
import aio_pika, httpx
from fastapi import FastAPI

app = FastAPI(title="ledger-service")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
ACCOUNT_URL = os.getenv("ACCOUNT_URL", "http://account-service:8001")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "internal-dev-token")

connection = channel = exchange = None

async def process(msg: aio_pika.IncomingMessage):
    async with msg.process():
        data = json.loads(msg.body.decode())
        if data.get("type") != "transaction.initiated":
            return

        tx_id = data["tx_id"]
        src = data["source_account_id"]
        dst = data["target_account_id"]
        amount = float(data["amount"])

        async with httpx.AsyncClient(timeout=5.0) as client:
            # try debit
            debit = {"account_id": src, "tx_id": f"{tx_id}-debit", "delta": -amount, "reason": f"transfer to {dst}"}
            r = await client.post(f"{ACCOUNT_URL}/internal/apply_ledger", json=debit, headers={"X-Internal-Token": INTERNAL_TOKEN})
            if r.status_code != 200:
                await publish("transaction.rejected", {"tx_id": tx_id, "reason": r.text})
                return
            # credit
            credit = {"account_id": dst, "tx_id": f"{tx_id}-credit", "delta": amount, "reason": f"transfer from {src}"}
            r2 = await client.post(f"{ACCOUNT_URL}/internal/apply_ledger", json=credit, headers={"X-Internal-Token": INTERNAL_TOKEN})
            if r2.status_code != 200:
                # rollback debit if credit failed (simple compensation)
                comp = {"account_id": src, "tx_id": f"{tx_id}-comp", "delta": amount, "reason": "compensate failed credit"}
                await client.post(f"{ACCOUNT_URL}/internal/apply_ledger", json=comp, headers={"X-Internal-Token": INTERNAL_TOKEN})
                await publish("transaction.rejected", {"tx_id": tx_id, "reason": r2.text})
                return

        await publish("transaction.completed", {"tx_id": tx_id, "source": src, "target": dst, "amount": amount})

async def publish(key: str, payload: dict):
    global exchange
    await exchange.publish(aio_pika.Message(body=json.dumps({"type": key, **payload}).encode()), routing_key=key)

@app.on_event("startup")
async def start():
    global connection, channel, exchange
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    exchange = await channel.declare_exchange("bank", aio_pika.ExchangeType.TOPIC)
    q = await channel.declare_queue("transactions", durable=True)
    await q.bind(exchange, routing_key="transaction.initiated")
    await q.consume(process)

@app.on_event("shutdown")
async def stop():
    if connection:
        await connection.close()
