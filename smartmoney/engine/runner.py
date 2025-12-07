# smartmoney/engine/runner.py
import time
import yaml
from loguru import logger
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Wallet
from ..scoring import compute_smart_score_from_wallet, classify_tier
from ..tracked import get_tracked_wallet_info
from ..connectors.perp_hyperliquid import HyperliquidConnector
from ..bots.telegram_bot import TelegramAlerter
from ..env import env
from .signals import create_signals_from_events
from .confluence import process_signals_into_alerts
from ..discovery import refresh_leaderboard_wallets


def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)


def seed_tracked_wallets(db: Session, config):
    """
    Seed awal dari config.tracked_wallets (opsional).
    Leaderboard discovery akan menambah wallet lain kemudian.
    """
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
    min_spot_size_usd = thresholds["min_spot_size_usd"]   # tidak terpakai sekarang (spot off)
    min_perp_size_usd = thresholds["min_perp_size_usd"]
    risk_default = thresholds["risk_per_trade_default"]

    # Telegram (opsional)
    tele = None
    if config["telegram"]["enabled"]:
        tele = TelegramAlerter(
            bot_token=env("TELEGRAM_BOT_TOKEN"),
            chat_id=env("TELEGRAM_CHAT_ID"),
        )

    # Seed manual wallets dari config
    db0 = SessionLocal()
    seed_tracked_wallets(db0, config)

    # Initial discovery leaderboard
    refresh_leaderboard_wallets(db0)
    db0.close()

    # Perp connector Hyperliquid
    perp_connectors = []
    for p in config.get("perp_platforms", []):
        if p["name"] == "hyperliquid":
            base_url = env(p.get("base_url_env", ""), "https://api.hyperliquid.xyz/info")
            perp_connectors.append(HyperliquidConnector(base_url=base_url))

    if not perp_connectors:
        logger.error("No perp connectors configured. Check config.yaml")
        return

    last_ts_perp = {pc.platform_name: int(time.time()) - 60 for pc in perp_connectors}
    last_discovery_ts = int(time.time()) - 3600  # supaya di loop pertama langsung refresh

    logger.info("Starting main loop (perp-only Hyperliquid + leaderboard discovery)...")
    while True:
        db = SessionLocal()
        try:
            all_spot_events = []   # kosong (kita nggak pakai spot sekarang)
            all_perp_events = []

            now_ts = int(time.time())

            # ==== Leaderboard discovery setiap ~15 menit ====
            if now_ts - last_discovery_ts > 900:
                refresh_leaderboard_wallets(db)
                last_discovery_ts = now_ts

            # ==== Tentukan wallet yang mau di-follow ====
            # Strategi sederhana:
            # - semua wallet di tabel Wallet (manual + leaderboard)
            wallets_in_db = [w.address for w in db.query(Wallet).all()]
            for pc in perp_connectors:
                if hasattr(pc, "set_tracked_wallets"):
                    pc.set_tracked_wallets(wallets_in_db)

            # ==== Ambil event perp untuk wallet tersebut ====
            for pc in perp_connectors:
                ev = pc.fetch_new_events(last_ts_perp[pc.platform_name])
                all_perp_events.extend(ev)
                last_ts_perp[pc.platform_name] = now_ts

            # ==== Update skor wallet untuk wallet yang ada event baru ====
            affected_wallets = set()
            for e in all_perp_events:
            affected_wallets.add(e["wallet_address"].lower())

            for addr in affected_wallets:
                wallet = db.query(Wallet).get(addr)
                if not wallet:
                    # kalau ada wallet baru (misal dari config manual, belum pernah masuk leaderboard)
                    wallet = Wallet(address=addr)
                    db.add(wallet)

            score = compute_smart_score_from_wallet(wallet)
            tier = classify_tier(score)

            wallet.smart_score = score
            wallet.tier = tier

            db.commit()

            # ==== Signals dari perp (spot_events kosong) ====
            new_signals = create_signals_from_events(
                db,
                all_spot_events,
                all_perp_events,
                min_spot_size_usd=min_spot_size_usd,
                min_perp_size_usd=min_perp_size_usd,
            )

            # ==== Signals → Alerts (+ trade setup) ====
            alerts = process_signals_into_alerts(
                db,
                new_signals,
                risk_per_trade_default=risk_default,
            )

            # ==== Kirim Telegram (kalau aktif) ====
            if tele:
                for a in alerts:
                    tele.send_alert(a)

            db.close()
        except Exception as e:
            logger.exception(f"Error in main loop: {e}")
            db.close()

        time.sleep(5)
