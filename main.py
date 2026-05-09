from typing import Annotated, List

from fastapi import FastAPI, Form, HTTPException, Depends
from pydantic import BaseModel
import models
from database import engine, SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

app = FastAPI()

# creates all tables and columns in postgres
models.Base.metadata.create_all(bind=engine) 


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]

class UserBase(BaseModel):
    username: str
    password: str

@app.post("/register/")
async def register(user: UserBase, db: db_dependency):
    existing_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    db_user = models.User(username=user.username,password=user.password)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {"username": f'{db_user.username} succesfully added'}
