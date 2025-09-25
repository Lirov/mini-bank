## Mini Bank - Microservices Skeleton

Minimal microservices demo using FastAPI, Kafka, and Docker Compose.

### Services

- auth-service (port 8000): issues JWT tokens for demo users.
- account-service (port 8001): manages accounts and ledger, stores data in SQLite.
- transaction-service (port 8002): accepts transfer requests, publishes events to Kafka.
- ledger-service (port 8003): processes transfers, updates accounts, emits outcomes.
- notification-service (port 8004 host / 8003 container): prints transaction outcomes.

### Prerequisites

- Docker and Docker Compose

### Quick Start

1) Start infra and services
   docker compose up -d

2) Get a token
   curl -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d '{"username":"u1","password":"p1"}'

3) Create an account
   curl -X POST http://localhost:8001/accounts -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" -d '{"owner_id":"u1"}'

4) Transfer funds (example)
   curl -X POST http://localhost:8002/transactions/transfer -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" -d '{"source_account_id":1,"target_account_id":2,"amount":10}'

### Environment Variables (common)

- JWT_SECRET: secret for signing JWTs (default: devsecret)
- KAFKA_BROKERS: Kafka bootstrap servers (default: kafka:9092)
- INTERNAL_TOKEN: internal call token for account-service (default: internal-dev-token)
- account-service DATABASE_URL: default sqlite:////data/accounts.db

### Notes

- Kafka/Zookeeper are configured in docker-compose and expose localhost:29092 for host access.
- SQLite data persists in the named volume `account_data`.
