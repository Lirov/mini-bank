import os
from sqlmodel import create_engine, SQLModel, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./accounts.db")
engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    from models import Account, LedgerEntry  # noqa
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as s:
        yield s
