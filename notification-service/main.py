import os, json, aio_pika
from fastapi import FastAPI

app = FastAPI(title="notification-service")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

connection = channel = exchange = None

async def process(msg: aio_pika.IncomingMessage):
    async with msg.process():
        data = json.loads(msg.body.decode())
        print("[NOTIFY]", data, flush=True)

@app.on_event("startup")
async def start():
    global connection, channel, exchange
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    exchange = await channel.declare_exchange("bank", aio_pika.ExchangeType.TOPIC)
    for key in ["transaction.completed", "transaction.rejected"]:
        q = await channel.declare_queue(key, durable=True)
        await q.bind(exchange, routing_key=key)
        await q.consume(process)

@app.on_event("shutdown")
async def stop():
    if connection:
        await connection.close()
