import logging
import os
import time

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

import jwt
from sqlmodel import Session, create_engine, select
from model import drop_and_create_db, PostalCodes, User, LoginRequest, AuthRequest
from env import variables

from fastapi import FastAPI, HTTPException, Header

engine = create_engine(f"mariadb+pymysql://{variables['username']}:{variables['password']}"
                       f"@{variables['host']}:{variables['port']}/{variables['database']}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    drop_and_create_db(variables['database'])
    script_dir = os.path.dirname(__file__)
    data_dir = os.path.join(script_dir, "data")

    with Session(engine) as session:
        for filename in os.listdir(data_dir):
            if (filename.endswith(".csv")):
                with open(os.path.join(data_dir, filename), "r") as file:
                    start_time = time.time()
                    for line in file:
                        insee_code, city_name, postal_code, label, line_5 = line.strip().split(";")
                        new_entry = PostalCodes(insee_code=insee_code, postal_code=postal_code, city=city_name)
                        session.add(new_entry)

                    end_time = time.time()
                    print(f"Time to process file: {round((end_time - start_time), 2)}s")
        session.commit()
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/api/v1/city/{insee_code}", response_model=PostalCodes)
async def get_city(insee_code: int):
    with Session(engine) as session:
        statement = select(PostalCodes).where(PostalCodes.insee_code == insee_code)
        results = session.exec(statement).first()
        return results


@app.get("/api/v1/cities/{insee_region_code}")
async def get_cities_from_region(insee_region_code: str):
    with Session(engine) as session:
        statement = select(PostalCodes).where(PostalCodes.insee_code.startswith(insee_region_code))
        results = session.exec(statement).all()
        return results


@app.post("/api/v1/register", response_model=User,
          openapi_extra={
              "requestBody": {
                  "content": {
                      "application/json": {
                          "schema": {
                              "type": "object",
                              "properties": {
                                  "username": {
                                      "type": "string",
                                      "example": "username"
                                  },
                                  "email": {
                                      "type": "string",
                                      "example": "email@mail.com"
                                  },
                                  "hashed_password": {
                                      "type": "string",
                                      "example": "hashed_password"
                                  }
                              }
                          }
                      }
                  }
              }
          })
async def register_user(user: User):
    with Session(engine) as session:
        try:
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
        except Exception as e:
            logging.error(f"Error while registering user: {user.username} - {e}")
            error = {
                "error": f"Error while registering user: {user.username} - {e}",
                "time": time.time()
            }
            raise HTTPException(status_code=409, detail=error)


@app.post("/api/v1/login",
          openapi_extra={
              "requestBody": {
                  "content": {
                      "application/json": {
                          "schema": {
                              "type": "object",
                              "properties": {
                                  "email": {
                                      "type": "string",
                                      "example": "email@mail.com"
                                  },
                                  "hashed_password": {
                                      "type": "string",
                                      "example": "hashed_password"
                                  }
                              }
                          }
                      }
                  }
              },
              "responses": {
                  "401": {
                      "description": "Invalid credentials",
                      "content": {
                          "application/json": {
                              "example": {
                                  "error": "Invalid credentials",
                                  "time": datetime.now()
                              }
                          }
                      }
                  },
                  "200": {
                      "description": "Connected user",
                      "content": {
                          "application/json": {
                              "example": {
                                  "user": "username",
                                  "token": "token"
                              }
                          }
                      }
                  }
              }
          },
          response_model=dict)
def login_user(request: LoginRequest):
    with Session(engine) as session:
        statement = select(User).where(User.email == request.email)
        user = session.exec(statement).first()
        if user is None:
            error = {
                "error": "Invalid credentials or user does not exist"
            }
            raise HTTPException(status_code=401, detail=error)
        if user.hashed_password == request.hashed_password and user.email == request.email:
            encoded_jwt = jwt.encode({"email": user.email, "hashed_password": user.hashed_password},
                                     variables['secret'], algorithm="HS256")
            connected_user = {
                "user": user.username,
                "token": encoded_jwt
            }
            return connected_user
        else:
            error = {
                "error": "Invalid credentials",
                "time": datetime.now()
            }
            raise HTTPException(status_code=401, detail=error)


@app.delete("/api/v1/delete", response_model=dict)
async def delete_user(request: AuthRequest):
    with Session(engine) as session:
        if request.authorization is None:
            error = {
                "error": "No token provided",
                "time": datetime.now()
            }
            raise HTTPException(status_code=401, detail=error)
        print("Authorization token : " + request.authorization)
        auth2 = request.authorization.encode("utf-8")
        auth = jwt.decode(auth2, variables['secret'], algorithms=["HS256"])
        if auth["email"] != request.email:
            error = {
                "error": "Invalid credentials",
                "time": datetime.now()
            }
            raise HTTPException(status_code=401, detail=error)
        statement = select(User).where(User.email == request.email)
        user = session.exec(statement).first()
        session.delete(user)
        session.commit()
        return {"message": f"User {user.username} deleted"}
