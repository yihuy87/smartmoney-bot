# smartmoney/engine/confluence.py
from typing import List, Dict
from sqlalchemy.orm import Session
from loguru import logger

from ..models import Signal as SignalModel, Alert
from .setup import generate_trade_setup
from ..schemas import AlertSchema, SpotContext, PerpContext, Setup

def derive_spot_bias(signals: List[SignalModel]) -> int:
    if not signals:
        return 0
    buy = sum(1 for s in signals if s.signal_type == "SPOT_BUY")
    sell = sum(1 for s in signals if s.signal_type == "SPOT_SELL")
    if buy > sell:
        return 1
    if sell > buy:
        return -1
    return 0

def derive_perp_bias(signals: List[SignalModel]) -> int:
    if not signals:
        return 0
    long_ = sum(1 for s in signals if s.signal_type == "PERP_OPEN_LONG")
    short_ = sum(1 for s in signals if s.signal_type == "PERP_OPEN_SHORT")
    if long_ > short_:
        return 1
    if short_ > long_:
        return -1
    return 0

def decide_confluence(spot_bias: int, perp_bias: int):
    if spot_bias == 1 and perp_bias == 1:
        return "STRONG", "LONG"
    if spot_bias == -1 and perp_bias == -1:
        return "STRONG", "SHORT"
    if spot_bias == 1 and perp_bias == 0:
        return "NORMAL", "SPOT_LONG"
    if spot_bias == 0 and perp_bias == 1:
        return "NORMAL", "PERP_LONG"
    if spot_bias == -1 and perp_bias == 0:
        return "NORMAL", "EXIT"
    if spot_bias == 0 and perp_bias == -1:
        return "NORMAL", "PERP_SHORT"
    if spot_bias == 1 and perp_bias == -1:
        return "AVOID", "MIXED"
    if spot_bias == -1 and perp_bias == 1:
        return "AVOID", "MIXED"
    return "WEAK", "NONE"

def process_signals_into_alerts(
    db: Session,
    new_signals: List[SignalModel],
    risk_per_trade_default: float
) -> List[AlertSchema]:
    if not new_signals:
        return []

    grouped: Dict = {}
    for s in new_signals:
        key = (s.wallet_address, s.token_symbol)
        grouped.setdefault(key, []).append(s)

    alerts_schemas: List[AlertSchema] = []

    for (wallet_address, token_symbol), sigs in grouped.items():
        spot_sigs = [s for s in sigs if s.signal_type.startswith("SPOT_")]
        perp_sigs = [s for s in sigs if s.signal_type.startswith("PERP_")]

        if not sigs:
            continue

        spot_bias = derive_spot_bias(spot_sigs)
        perp_bias = derive_perp_bias(perp_sigs)
        signal_strength, mode = decide_confluence(spot_bias, perp_bias)

        if mode in ("MIXED", "NONE"):
            logger.info(f"Mixed/none signal for {wallet_address} {token_symbol}, skipping alert")
            continue

        main_sig = sigs[-1]
        price = main_sig.price or 0.0
        setup_data = generate_trade_setup(mode, price, risk_per_trade_default)
        setup = Setup(**setup_data)

        spot_ctx = SpotContext(present=bool(spot_sigs))
        if spot_sigs:
            s0 = spot_sigs[-1]
            spot_ctx.chain_id = s0.chain_id_spot
            spot_ctx.token_symbol = s0.token_symbol
            spot_ctx.token_address = s0.token_address
            spot_ctx.price = s0.price
            spot_ctx.size_usd = s0.size_usd
            spot_ctx.liquidity_usd = s0.liquidity_usd
            spot_ctx.bias = spot_bias

        perp_ctx = PerpContext(present=bool(perp_sigs))
        if perp_sigs:
            p0 = perp_sigs[-1]
            perp_ctx.platform = p0.perp_platform
            perp_ctx.pair = p0.pair_perp
            perp_ctx.entry_price_wallet = p0.price
            perp_ctx.size_usd = p0.size_usd
            perp_ctx.leverage = 1.0
            perp_ctx.bias = perp_bias

        raw_payload = {
            "wallet_address": wallet_address,
            "wallet_score": main_sig.wallet_score,
            "spot_bias": spot_bias,
            "perp_bias": perp_bias,
            "mode": mode,
        }

        alert_model = Alert(
            alert_type="HYBRID" if spot_sigs and perp_sigs else ("SPOT_ONLY" if spot_sigs else "PERP_ONLY"),
            signal_strength=signal_strength,
            wallet_address=wallet_address,
            wallet_score=main_sig.wallet_score,
            chain_id_spot=spot_ctx.chain_id,
            perp_platform=perp_ctx.platform,
            token_symbol=token_symbol,
            pair_perp=perp_ctx.pair,
            spot_bias=spot_bias,
            perp_bias=perp_bias,
            entry_min=setup.entry_min,
            entry_max=setup.entry_max,
            stop_loss=setup.stop_loss,
            tp1=setup.tp1,
            tp2=setup.tp2,
            tp3=setup.tp3,
            raw_payload=raw_payload,
        )
        db.add(alert_model)
        db.commit()

        alert_schema = AlertSchema(
            id=str(alert_model.id),
            alert_type=alert_model.alert_type,
            signal_strength=signal_strength,
            wallet_address=wallet_address,
            wallet_score=main_sig.wallet_score,
            spot=spot_ctx,
            perp=perp_ctx,
            setup=setup,
        )
        alerts_schemas.append(alert_schema)

    return alerts_schemas
