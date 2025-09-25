import os, json, asyncio
from typing import Optional
import httpx
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from fastapi import FastAPI

app = FastAPI(title="ledger-service")

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"))
ACCOUNT_URL = os.getenv("ACCOUNT_URL", "http://account-service:8001")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "internal-dev-token")

consumer: AIOKafkaConsumer | None = None
producer: AIOKafkaProducer | None = None

async def process_record(data: dict):
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
    assert producer is not None
    await producer.send_and_wait(key, json.dumps({"type": key, **payload}).encode())

@app.on_event("startup")
async def start():
    global consumer, producer
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKERS)
    await producer.start()
    consumer = AIOKafkaConsumer(
        "transaction.initiated",
        bootstrap_servers=KAFKA_BROKERS,
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode()),
        group_id="ledger-service"
    )
    await consumer.start()
    async def _consume():
        assert consumer is not None
        async for msg in consumer:
            await process_record(msg.value)
    asyncio.create_task(_consume())

@app.on_event("shutdown")
async def stop():
    if consumer:
        await consumer.stop()
    if producer:
        await producer.stop()
