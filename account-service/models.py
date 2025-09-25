from typing import Optional
from sqlmodel import Field, SQLModel, Column, String

class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: str = Field(index=True)
    balance: float = 0.0

class LedgerEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)
    tx_id: str = Field(sa_column=Column(String, unique=True))
    delta: float
    reason: str
