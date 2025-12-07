# smartmoney/engine/signals.py
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import datetime as dt
from loguru import logger

from ..models import Signal, Wallet
from .events import group_events_by_wallet_and_asset


def _safe_timestamp_to_dt(ts: int) -> dt.datetime:
    """
    Konversi timestamp (detik atau ms) jadi datetime UTC dengan aman.
    - Kalau ts > 1e12 → diasumsikan ms → dibagi 1000 dulu.
    """
    try:
        if ts > 10**12:
            ts = ts // 1000
        return dt.datetime.utcfromtimestamp(ts)
    except Exception:
        # fallback ke sekarang
        return dt.datetime.utcnow()


def create_signals_from_events(
    db: Session,
    spot_events: List[Dict[str, Any]],
    perp_events: List[Dict[str, Any]],
    min_spot_size_usd: float,
    min_perp_size_usd: float,
) -> List[Signal]:
    """
    - SPOT: masih didukung tapi bukan fokus utama (boleh saja dibiarkan kosong).
    - PERP: hanya wallet S-tier yang boleh menghasilkan sinyal,
      dengan syarat:
        - size_usd >= min_perp_size_usd
        - event_type in ("OPEN", "INCREASE")
    """

    contexts = group_events_by_wallet_and_asset(spot_events, perp_events)
    created_signals: List[Signal] = []

    for (wallet_address, token_symbol), ctx in contexts.items():
        wal_addr_lc = (wallet_address or "").lower()
        if not wal_addr_lc:
            continue

        wallet: Wallet = db.query(Wallet).get(wal_addr_lc)
        if not wallet:
            wallet = Wallet(address=wal_addr_lc)
            db.add(wallet)
            db.commit()

        # === SPOT signals (opsional, tetap ada tapi jarang dipakai) ===
        for e in ctx["spot"]:
            try:
                if e["amount_usd"] < min_spot_size_usd:
                    continue

                created_at = _safe_timestamp_to_dt(int(e["timestamp"]))
                signal_type = "SPOT_BUY" if e["side"] == "BUY" else "SPOT_SELL"

                sig = Signal(
                    signal_type=signal_type,
                    wallet_address=wal_addr_lc,
                    wallet_score=wallet.smart_score,
                    wallet_tier=wallet.tier,
                    chain_id_spot=e["chain_id"],
                    token_symbol=token_symbol,
                    token_address=e["token_address"],
                    price=e["price"],
                    size_usd=e["amount_usd"],
                    liquidity_usd=e["liquidity_usd"],
                    created_at=created_at,
                )
                db.add(sig)
                created_signals.append(sig)
            except Exception as ex:
                logger.error(f"[Signals] Error creating spot signal: {ex}")

        # === PERP signals (fokus utama) ===
        for e in ctx["perp"]:
            try:
                # hanya wallet S-tier yang dianggap benar-benar Smart Money
                if wallet.tier != "S":
                    continue

                # buang posisi kecil
                if e["size_usd"] < min_perp_size_usd:
                    continue

                # hanya entry / tambah posisi yang dijadikan sinyal
                if e["event_type"] not in ("OPEN", "INCREASE"):
                    continue

                created_at = _safe_timestamp_to_dt(int(e["timestamp"]))

                if e["direction"] == "LONG":
                    signal_type = "PERP_OPEN_LONG"
                else:
                    signal_type = "PERP_OPEN_SHORT"

                sig = Signal(
                    signal_type=signal_type,
                    wallet_address=wal_addr_lc,
                    wallet_score=wallet.smart_score,
                    wallet_tier=wallet.tier,
                    perp_platform=e["platform"],
                    pair_perp=e["pair"],
                    token_symbol=token_symbol,
                    price=e["entry_price"],
                    size_usd=e["size_usd"],
                    created_at=created_at,
                )
                db.add(sig)
                created_signals.append(sig)
            except Exception as ex:
                logger.error(f"[Signals] Error creating perp signal: {ex}")

    db.commit()
    logger.info(f"Created {len(created_signals)} signals")
    return created_signals
