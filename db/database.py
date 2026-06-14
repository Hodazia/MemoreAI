'''
Basically here i will be making the DB as well as models which are gonna be used 

'''

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


Base.metadata.create_all(bind=engine)