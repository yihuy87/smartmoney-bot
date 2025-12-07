# smartmoney/schemas.py
from pydantic import BaseModel
from typing import Optional

class SpotContext(BaseModel):
    present: bool = False
    bias: int = 0
    chain_id: Optional[str] = None
    token_symbol: Optional[str] = None
    token_address: Optional[str] = None
    price: Optional[float] = None
    size_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None

class PerpContext(BaseModel):
    present: bool = False
    bias: int = 0
    platform: Optional[str] = None
    pair: Optional[str] = None
    entry_price_wallet: Optional[float] = None
    size_usd: Optional[float] = None
    leverage: Optional[float] = None

class Setup(BaseModel):
    mode: str               # LONG / SHORT / NONE
    market: str             # SPOT / PERP
    entry_min: float
    entry_max: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    suggested_risk_per_trade: float

class AlertSchema(BaseModel):
    id: str
    alert_type: str
    signal_strength: str
    wallet_address: str
    wallet_score: float
    spot: SpotContext
    perp: PerpContext
    setup: Setup
