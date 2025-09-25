import os, json
from fastapi import FastAPI
from aiokafka import AIOKafkaConsumer

app = FastAPI(title="notification-service")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"))

consumer: AIOKafkaConsumer | None = None

async def process_record(data: dict):
    print("[NOTIFY]", data, flush=True)

@app.on_event("startup")
async def start():
    global consumer
    consumer = AIOKafkaConsumer(
        "transaction.completed",
        "transaction.rejected",
        bootstrap_servers=KAFKA_BROKERS,
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode()),
        group_id="notification-service"
    )
    await consumer.start()
    async def _consume():
        assert consumer is not None
        async for msg in consumer:
            await process_record(msg.value)
    import asyncio
    asyncio.create_task(_consume())

@app.on_event("shutdown")
async def stop():
    if consumer:
        await consumer.stop()
