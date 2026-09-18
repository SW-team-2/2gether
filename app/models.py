from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Url(Base):
    __tablename__ = "urls"
    id = Column(Integer, primary_key=True)
    code = Column(String(10), unique=True, nullable=False)
    original_url = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class Click(Base):
    __tablename__ = "clicks"
    id = Column(Integer, primary_key=True)
    url_id = Column(Integer, ForeignKey("urls.id"), nullable=False)
    clicked_at = Column(TIMESTAMP, default=datetime.utcnow)
    referrer = Column(Text, nullable=True)
    device = Column(String(20), nullable=True)

