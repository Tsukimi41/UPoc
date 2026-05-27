from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from .db import Base


class Cap(Base):
    __tablename__ = "caps"

    id = Column(Integer, primary_key=True, index=True)
    index = Column(Integer, unique=True, index=True)
    x = Column(Integer)
    y = Column(Integer)
    color_name = Column(String(20))
    color_label = Column(String(20))
    color_hex = Column(String(7))
    color_palette = Column(String(7))
    nickname = Column(String(40))
    source = Column(String(20))
    user_id = Column(String(40), nullable=True)
    checkin_token = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Theme(Base):
    __tablename__ = "themes"

    id = Column(String(50), primary_key=True)
    title = Column(String(100))
    description = Column(String(200))
    votes = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


class Event(Base):
    __tablename__ = "events"

    id = Column(String(50), primary_key=True)
    title = Column(String(100))
    status = Column(String(20))
    total_pixels = Column(Integer)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)


class Checkin(Base):
    __tablename__ = "checkins"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, index=True)
    nickname = Column(String(40))
    user_id = Column(String(40), nullable=True)
    source = Column(String(20))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    used_at = Column(DateTime(timezone=True), nullable=True)


class NotificationSubscription(Base):
    __tablename__ = "notification_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String(20))
    contact = Column(String(200))
    user_id = Column(String(40), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
