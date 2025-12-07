# smartmoney/engine/runner.py
import time
import yaml
from loguru import logger
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Wallet
from ..scoring import compute_smart_score, classify_tier, WalletStats
from ..tracked import get_tracked_wallet_info
from ..connectors.mock_connectors import MockSpotConnector, MockPerpConnector
from ..connectors.perp_hyperliquid import HyperliquidConnector
from ..bots.telegram_bot import TelegramAlerter
from ..env import env
from .signals import create_signals_from_events
from .confluence import process_signals_into_alerts

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def compute_wallet_stats_dummy(db: Session, wallet_address: str) -> WalletStats:
    base = get_tracked_wallet_info(wallet_address) or {}
    default_score = base.get("initial_score", 0) / 100.0
    winrate = default_score if default_score > 0 else 0.6
    return WalletStats(
        winrate_30d=winrate,
        pnl_30d_usd=0.5,
        max_drawdown_30d=0.2,
        avg_leverage_30d=3.0,
        rugpull_ratio_30d=0.05,
        avg_trade_size_ratio=0.1,
    )

def seed_tracked_wallets(db: Session, config):
    tracked = config.get("tracked_wallets", [])
    for w in tracked:
        addr = w["address"]
        wallet = db.query(Wallet).get(addr)
        if not wallet:
            wallet = Wallet(address=addr)
            db.add(wallet)
        wallet.smart_score = w.get("initial_score", 0)
        wallet.tier = w.get("initial_tier", "A")
    db.commit()

def main_loop():
    config = load_config()
    thresholds = config["thresholds"]
    min_spot_size_usd = thresholds["min_spot_size_usd"]
    min_perp_size_usd = thresholds["min_perp_size_usd"]
    risk_default = thresholds["risk_per_trade_default"]

    tele = None
    if config["telegram"]["enabled"]:
        tele = TelegramAlerter(
            bot_token=env("TELEGRAM_BOT_TOKEN"),
            chat_id=env("TELEGRAM_CHAT_ID"),
        )

    db0 = SessionLocal()
    seed_tracked_wallets(db0, config)
    db0.close()

    # Connectors
    spot_connectors = []
    spot_connectors.append(MockSpotConnector(chain_id="mock"))

    perp_connectors = []
    perp_connectors.append(MockPerpConnector())

    for p in config.get("perp_platforms", []):
        if p["name"] == "hyperliquid":
            base_url = env(p.get("base_url_env", ""), "https://api.hyperliquid.xyz/info")
            perp_connectors.append(HyperliquidConnector(base_url=base_url))

    last_block = {c.chain_id: 0 for c in spot_connectors}
    last_ts_perp = {pc.platform_name: int(time.time()) - 60 for pc in perp_connectors}

    logger.info("Starting main loop (DB + tracked wallets)...")
    while True:
        db = SessionLocal()
        try:
            all_spot_events = []
            all_perp_events = []

            # Spot (mock)
            for conn in spot_connectors:
                if last_block[conn.chain_id] == 0:
                    last_block[conn.chain_id] = conn.get_latest_block()
                    continue
                new_block = conn.get_latest_block()
                if new_block > last_block[conn.chain_id]:
                    ev = conn.fetch_new_events(last_block[conn.chain_id] + 1, new_block)
                    all_spot_events.extend(ev)
                    last_block[conn.chain_id] = new_block

            # Perp (mock + hyperliquid)
            now_ts = int(time.time())
            for pc in perp_connectors:
                ev = pc.fetch_new_events(last_ts_perp[pc.platform_name])
                all_perp_events.extend(ev)
                last_ts_perp[pc.platform_name] = now_ts

            # Update skor wallet
            affected_wallets = set()
            for e in all_spot_events + all_perp_events:
                affected_wallets.add(e["wallet_address"])

            for addr in affected_wallets:
                stats = compute_wallet_stats_dummy(db, addr)
                score = compute_smart_score(stats)
                tier = classify_tier(score)
                wallet = db.query(Wallet).get(addr)
                if not wallet:
                    wallet = Wallet(address=addr)
                    db.add(wallet)
                wallet.smart_score = score
                wallet.tier = tier
                wallet.winrate_30d = stats.winrate_30d
                wallet.pnl_30d_usd = stats.pnl_30d_usd
                wallet.max_drawdown_30d = stats.max_drawdown_30d
                wallet.avg_leverage_30d = stats.avg_leverage_30d
                wallet.rugpull_ratio_30d = stats.rugpull_ratio_30d
                wallet.avg_trade_size_ratio = stats.avg_trade_size_ratio
            db.commit()

            # Signals
            new_signals = create_signals_from_events(
                db,
                all_spot_events,
                all_perp_events,
                min_spot_size_usd=min_spot_size_usd,
                min_perp_size_usd=min_perp_size_usd,
            )

            # Alerts
            alerts = process_signals_into_alerts(
                db,
                new_signals,
                risk_per_trade_default=risk_default,
            )

            # Telegram
            if tele:
                for a in alerts:
                    tele.send_alert(a)

            db.close()
        except Exception as e:
            logger.exception(f"Error in main loop: {e}")
            db.close()

        time.sleep(5)
