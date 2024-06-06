from typing import Annotated

from fastapi import Header
from pydantic import BaseModel
from sqlalchemy import text

from sqlmodel import SQLModel, Field, create_engine

from env import variables


class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    username: str = Field(max_length=50, unique=True)
    email: str = Field(max_length=50, unique=True)
    hashed_password: str = Field(max_length=50)


class PostalCodes(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    insee_code: str = Field(max_length=5, default=None)
    postal_code: int = Field(default=None)
    city: str = Field(max_length=255)


class LoginRequest(BaseModel):
    email: str
    hashed_password: str


class AuthRequest(BaseModel):
    email: str
    authorization: Annotated[str | None, Header()] = None


def drop_and_create_db(database_name="franceguessr"):
    engine = create_engine(f"mariadb+pymysql://{variables['username']}:{variables['password']}"
                           f"@{variables['host']}:{variables['port']}/mysql")
    engine.connect().execute(text(f"DROP DATABASE IF EXISTS {database_name}"))
    engine.connect().execute(text(f"CREATE DATABASE {database_name}"))
    engine = create_engine(f"mariadb+pymysql://{variables['username']}:{variables['password']}"
                           f"@{variables['host']}:{variables['port']}/{database_name}")
    SQLModel.metadata.create_all(engine)
    engine.dispose()
