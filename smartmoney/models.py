# smartmoney/models.py
from sqlalchemy.orm import declarative_base
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, JSON
)
import datetime as dt

Base = declarative_base()

class Wallet(Base):
    __tablename__ = "wallets"

    address = Column(String, primary_key=True)

    # skor & tier internal bot
    smart_score = Column(Float, default=0.0)
    tier = Column(String, default="ignore")  # S, A, B, ignore

    # --- data leaderboard / statistik agregat ---
    # total equity/account value (USDC)
    account_value_usd = Column(Float, default=0.0)
    # total PnL sepanjang waktu (USDC)
    pnl_all_usd = Column(Float, default=0.0)
    # total ROI sepanjang waktu (dalam fraksi, 0.5 = 50%)
    roi_all = Column(Float, default=0.0)

    # --- field lama (boleh dibiarkan, walau belum terisi benar) ---
    winrate_30d = Column(Float, default=0.0)
    pnl_30d_usd = Column(Float, default=0.0)
    max_drawdown_30d = Column(Float, default=0.0)
    avg_leverage_30d = Column(Float, default=0.0)
    rugpull_ratio_30d = Column(Float, default=0.0)
    avg_trade_size_ratio = Column(Float, default=0.0)
    chains_traded_spot = Column(JSON, default=list)
    perp_platforms_used = Column(JSON, default=list)
    last_updated_at = Column(DateTime, default=dt.datetime.utcnow)

class SpotTrade(Base):
    __tablename__ = "wallet_trades_spot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_address = Column(String, index=True)
    chain_id = Column(String)
    dex = Column(String)
    tx_hash = Column(String, index=True, unique=True)
    timestamp = Column(DateTime, index=True)
    token_address = Column(String)
    token_symbol = Column(String)
    side = Column(String)  # BUY / SELL
    amount_usd = Column(Float)
    price = Column(Float)
    liquidity_usd = Column(Float)
    is_rugpull = Column(Boolean, default=False)

class PerpPosition(Base):
    __tablename__ = "wallet_positions_perp"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_address = Column(String, index=True)
    platform = Column(String)
    platform_type = Column(String)   # evm / appchain / other
    chain_id = Column(String, nullable=True)
    pair = Column(String)
    direction = Column(String)       # LONG / SHORT
    entry_price = Column(Float)
    size_usd = Column(Float)
    leverage = Column(Float)
    liq_price = Column(Float, nullable=True)
    opened_at = Column(DateTime)
    updated_at = Column(DateTime)
    status = Column(String, default="OPEN")  # OPEN / CLOSED

class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_type = Column(String)
    wallet_address = Column(String, index=True)
    wallet_score = Column(Float)
    wallet_tier = Column(String)
    chain_id_spot = Column(String, nullable=True)
    perp_platform = Column(String, nullable=True)
    token_symbol = Column(String, nullable=True)
    token_address = Column(String, nullable=True)
    pair_perp = Column(String, nullable=True)
    price = Column(Float)
    size_usd = Column(Float)
    liquidity_usd = Column(Float, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    processed = Column(Boolean, default=False)

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String)
    signal_strength = Column(String)
    wallet_address = Column(String)
    wallet_score = Column(Float)
    chain_id_spot = Column(String, nullable=True)
    perp_platform = Column(String, nullable=True)
    token_symbol = Column(String, nullable=True)
    pair_perp = Column(String, nullable=True)
    spot_bias = Column(Integer, default=0)   # -1/0/1
    perp_bias = Column(Integer, default=0)
    entry_min = Column(Float)
    entry_max = Column(Float)
    stop_loss = Column(Float)
    tp1 = Column(Float)
    tp2 = Column(Float)
    tp3 = Column(Float)
    raw_payload = Column(JSON)
    sent_to = Column(String, nullable=True)
    sent_at = Column(DateTime, nullable=True)
