from datetime import datetime, timedelta, timezone
import os
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from pydantic import BaseModel, EmailStr
import models
from database import engine, SessionLocal
from sqlalchemy import or_
from sqlalchemy.orm import Session

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-before-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

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
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None = None


class GameCreate(BaseModel):
    title: str
    platform: str | None = None
    genre: str | None = None
    release_year: int | None = None
    status: Literal["playing", "completed", "dropped"] = "playing"


class GameStatusUpdate(BaseModel):
    status: Literal["playing", "completed", "dropped"]


class GameResponse(BaseModel):
    id: int
    title: str
    platform: str | None = None
    genre: str | None = None
    release_year: int | None = None
    status: str
    owner_id: int


def verify_password(plain_password: str, hashed_password: str):
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except UnknownHashError:
        return False


def get_password_hash(password: str):
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str, db: Session):
    user = db.query(models.User).filter(models.User.username == username).first()

    if not user or not verify_password(password, user.password):
        return None

    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: db_dependency,
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception

    return user


current_user_dependency = Annotated[models.User, Depends(get_current_user)]


@app.post("/register/")
async def register(user: UserBase, db: db_dependency):
    existing_user = db.query(models.User).filter(
        or_(
            models.User.username == user.username,
            models.User.email == user.email,
        )
    ).first()

    if existing_user:
        detail = "Username already exists"
        if existing_user.email == user.email:
            detail = "Email already exists"

        raise HTTPException(
            status_code=400,
            detail=detail
        )

    db_user = models.User(
        username=user.username,
        email=user.email,
        password=get_password_hash(user.password),
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {"username": f'{db_user.username} succesfully added'}


@app.post("/login/", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: db_dependency,
):
    user = authenticate_user(form_data.username, form_data.password, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me/", response_model=UserResponse)
async def read_current_user(current_user: current_user_dependency):
    return current_user


@app.get("/")
async def home():
    return FileResponse("static/index.html")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/login/")
async def login_page():
    return FileResponse("static/login.html")


@app.get("/register/")
async def register_page():
    return FileResponse("static/register.html")


@app.post("/games/", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
async def add_game(
    game: GameCreate,
    current_user: current_user_dependency,
    db: db_dependency,
):
    db_game = models.Game(
        title=game.title,
        platform=game.platform,
        genre=game.genre,
        release_year=game.release_year,
        status=game.status,
        owner_id=current_user.id,
    )

    db.add(db_game)
    db.commit()
    db.refresh(db_game)

    return db_game


@app.get("/games/", response_model=list[GameResponse])
async def read_games(
    current_user: current_user_dependency,
    db: db_dependency,
):
    return db.query(models.Game).filter(
        models.Game.owner_id == current_user.id,
    ).order_by(models.Game.id.desc()).all()


@app.put("/games/{game_id}/status", response_model=GameResponse)
async def update_game_status(
    game_id: int,
    status_update: GameStatusUpdate,
    current_user: current_user_dependency,
    db: db_dependency,
):
    db_game = db.query(models.Game).filter(
        models.Game.id == game_id,
        models.Game.owner_id == current_user.id,
    ).first()

    if db_game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )

    db_game.status = status_update.status
    db.commit()
    db.refresh(db_game)

    return db_game


@app.delete("/games/{game_id}")
async def delete_game(
    game_id: int,
    current_user: current_user_dependency,
    db: db_dependency,
):
    db_game = db.query(models.Game).filter(
        models.Game.id == game_id,
        models.Game.owner_id == current_user.id,
    ).first()

    if db_game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )

    db.delete(db_game)
    db.commit()

    return {"detail": "Game deleted"}
