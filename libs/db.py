from decimal import Decimal

from sqlalchemy import Boolean, Column, Float, Integer, Numeric, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from libs.config import settings

Base = declarative_base()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
Session = sessionmaker(engine, expire_on_commit=False)


class Asset(Base):
    __tablename__ = "assets"
    id = Column(String(100), primary_key=True)
    market = Column(String(10), nullable=False, index=True)
    symbol = Column(String(60), nullable=False, index=True)
    name = Column(String(250), nullable=False)
    currency = Column(String(30), nullable=False)
    source = Column(String(80), nullable=False)
    active = Column(Boolean, default=True)


class Watch(Base):
    __tablename__ = "watchlist"
    asset_id = Column(String(100), primary_key=True)
    added = Column(Float, nullable=False)


class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(String(100), primary_key=True)
    cash = Column(Numeric(30, 10), default=Decimal("100000"))
    initial = Column(Numeric(30, 10), default=Decimal("100000"))
    realized = Column(Numeric(30, 10), default=Decimal("0"))


class Position(Base):
    __tablename__ = "positions"
    id = Column(String(150), primary_key=True)
    wallet_id = Column(String(100), nullable=False)
    asset_id = Column(String(100), nullable=False)
    quantity = Column(Numeric(30, 10), default=Decimal("0"))
    average = Column(Numeric(30, 10), default=Decimal("0"))


class Trade(Base):
    __tablename__ = "trades"
    id = Column(String(64), primary_key=True)
    asset_id = Column(String(100), nullable=False)
    wallet_id = Column(String(100), nullable=False)
    side = Column(String(4), nullable=False)
    quantity = Column(Numeric(30, 10), nullable=False)
    price = Column(Numeric(30, 10), nullable=False)
    fee = Column(Numeric(30, 10), nullable=False)
    timestamp = Column(Float, nullable=False)
    source = Column(String(80), nullable=False)


class Decision(Base):
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(String(100), nullable=False, index=True)
    action = Column(String(4), nullable=False)
    reason = Column(String(300), nullable=False)
    timestamp = Column(Float, nullable=False)


class Control(Base):
    __tablename__ = "controls"
    id = Column(String(30), primary_key=True)
    value = Column(String(100), nullable=False)


def initialize():
    Base.metadata.create_all(engine)
    with Session.begin() as db:
        if not db.get(Control, "kill_switch"):
            db.add(Control(id="kill_switch", value="false"))
        if not db.get(Control, "autopaper"):
            db.add(Control(id="autopaper", value="false"))


def serialize(row):
    return {
        c.name: str(v) if isinstance(v := getattr(row, c.name), Decimal) else v for c in row.__table__.columns
    }
