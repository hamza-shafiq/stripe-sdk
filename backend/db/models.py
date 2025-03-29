import datetime
import uuid
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from backend.utils.mysql_uuid import GUID

Base = declarative_base()


class User(Base):
    """
    Data model for users
    """
    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    email = Column(String(64), nullable=False, unique=True)
    password = Column(String(124), nullable=False)
    first_name = Column(String(64))
    last_name = Column(String(64))
    profile_picture_url = Column(String(255), nullable=True)
    stage = Column(String(100), default="0")
    target_score = Column(Integer)
    role = Column(Integer)
    is_subscribed = Column(Boolean, default=False)

    def __repr__(self):
        return f"<User {self.email}>"

    def as_dict(self):
        return {
            "email": self.email,
            "name": f"{self.first_name} {self.last_name}",
            "role": self.role_name,
            "is_subscribed": self.is_subscribed,
            "stage": self.stage,
            "access": self.access
        }

    @property
    def role_name(self):
        role_mapping = {1: "admin", 2: "user"}
        return role_mapping.get(self.role, "unknown")


class RejectedToken(Base):
    """
    Data model for rejected Tokens
    """
    __tablename__ = "rejected_tokens"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    token = Column(String(1024), nullable=False)

    def __repr__(self):
        return f"<Token {self.token}>"


class Subscription(Base):
    """
    Subscription Table
    """
    __tablename__ = "subscription"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    price_id = Column(String, nullable=False)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    active = Column(Boolean, default=True)
    last_four_card = Column(String, nullable=True)
    auto_renew_date = Column(String, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
