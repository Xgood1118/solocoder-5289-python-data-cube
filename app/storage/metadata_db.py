from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()


class CubeMetadata(Base):
    __tablename__ = "cube_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    fact_table = Column(String(255), nullable=False)
    dimensions = Column(Text, nullable=False)
    measures = Column(Text, nullable=False)
    dimension_tables = Column(Text, nullable=True)
    last_refreshed = Column(DateTime, nullable=True)
    row_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    source_type = Column(String(50), nullable=False)
    config = Column(Text, nullable=False)
    last_sync = Column(DateTime, nullable=True)
    last_modified_field = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PermissionRule(Base):
    __tablename__ = "permission_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String(50), nullable=False, index=True)
    cube_name = Column(String(255), nullable=False, index=True)
    dimension = Column(String(255), nullable=False)
    condition_type = Column(String(50), nullable=False)
    condition_value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cube_name = Column(String(255), nullable=False, index=True)
    query_hash = Column(String(64), nullable=True, index=True)
    query_json = Column(Text, nullable=False)
    duration_ms = Column(Integer, nullable=False)
    row_count = Column(Integer, default=0)
    from_cache = Column(Integer, default=0)
    user_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        db_url = settings.database_url
        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            import os

            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        _engine = create_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
        )
        Base.metadata.create_all(_engine)
    return _engine


def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=get_engine()
        )
    return _SessionLocal()


def init_db():
    get_engine()
