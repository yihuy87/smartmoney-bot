# smartmoney/engine/signals.py
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import datetime as dt
from loguru import logger

from ..models import Signal, Wallet
from .events import group_events_by_wallet_and_asset

def create_signals_from_events(
    db: Session,
    spot_events: List[Dict[str, Any]],
    perp_events: List[Dict[str, Any]],
    min_spot_size_usd: float,
    min_perp_size_usd: float,
) -> List[Signal]:
    contexts = group_events_by_wallet_and_asset(spot_events, perp_events)
    created_signals: List[Signal] = []

    for (wallet_address, token_symbol), ctx in contexts.items():
        wallet: Wallet = db.query(Wallet).get(wallet_address)
        if not wallet or wallet.tier not in ("S", "A"):
            continue

        for e in ctx["spot"]:
            if e["amount_usd"] < min_spot_size_usd:
                continue
            signal_type = "SPOT_BUY" if e["side"] == "BUY" else "SPOT_SELL"
            sig = Signal(
                signal_type=signal_type,
                wallet_address=wallet_address,
                wallet_score=wallet.smart_score,
                wallet_tier=wallet.tier,
                chain_id_spot=e["chain_id"],
                token_symbol=token_symbol,
                token_address=e["token_address"],
                price=e["price"],
                size_usd=e["amount_usd"],
                liquidity_usd=e["liquidity_usd"],
                created_at=dt.datetime.utcfromtimestamp(e["timestamp"]),
            )
            db.add(sig)
            created_signals.append(sig)

        for e in ctx["perp"]:
            if e["size_usd"] < min_perp_size_usd:
                continue
            if e["event_type"] not in ("OPEN", "INCREASE"):
                continue
            signal_type = "PERP_OPEN_LONG" if e["direction"] == "LONG" else "PERP_OPEN_SHORT"
            sig = Signal(
                signal_type=signal_type,
                wallet_address=wallet_address,
                wallet_score=wallet.smart_score,
                wallet_tier=wallet.tier,
                perp_platform=e["platform"],
                pair_perp=e["pair"],
                token_symbol=token_symbol,
                price=e["entry_price"],
                size_usd=e["size_usd"],
                created_at=dt.datetime.utcfromtimestamp(e["timestamp"]),
            )
            db.add(sig)
            created_signals.append(sig)

    db.commit()
    logger.info(f"Created {len(created_signals)} signals")
    return created_signals
