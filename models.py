from sqlalchemy import Column, ForeignKey, Integer, String
from database import Base

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String, index=True)


class Game(Base):
    __tablename__ = 'games'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    platform = Column(String, nullable=True)
    genre = Column(String, nullable=True)
    release_year = Column(Integer, nullable=True)
    status = Column(String, default="playing", index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True)
