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
    Masukkan wallet manual dari config.yaml (opsional).
    Leaderboard discovery akan menambah wallet otomatis.
    """
    tracked = config.get("tracked_wallets", [])
    for w in tracked:
        addr = w["address"].lower()
        wallet = db.query(Wallet).get(addr)
        if not wallet:
            wallet = Wallet(address=addr)
            db.add(wallet)

        wallet.smart_score = w.get("initial_score", 0)
        wallet.tier = w.get("initial_tier", "ignore")

    db.commit()


def main_loop():
    config = load_config()
    thresholds = config["thresholds"]
    min_spot_size_usd = thresholds["min_spot_size_usd"]   # tidak digunakan
    min_perp_size_usd = thresholds["min_perp_size_usd"]
    risk_default = thresholds["risk_per_trade_default"]

    # Telegram
    tele = None
    if config["telegram"]["enabled"]:
        tele = TelegramAlerter(
            bot_token=env("TELEGRAM_BOT_TOKEN"),
            chat_id=env("TELEGRAM_CHAT_ID"),
        )

    # === Seed awal wallet manual ===
    db0 = SessionLocal()
    seed_tracked_wallets(db0, config)

    # === First discovery leaderboard ===
    refresh_leaderboard_wallets(db0)  # ini akan memasukkan wallet top leaderboard ke DB
    db0.close()

    # === Init perp connector ===
    perp_connectors = []
    for p in config.get("perp_platforms", []):
        if p["name"] == "hyperliquid":
            base_url = env(p.get("base_url_env", ""), "https://api.hyperliquid.xyz/info")
            perp_connectors.append(HyperliquidConnector(base_url=base_url))

    if not perp_connectors:
        logger.error("No perp connectors configured. Check config.yaml")
        return

    # Simpan last timestamp untuk fetch perp
    last_ts_perp = {pc.platform_name: int(time.time()) - 120 for pc in perp_connectors}

    # Supaya loop pertama langsung discovery
    last_discovery_ts = int(time.time()) - 3600

    logger.info("Starting main loop (Hyperliquid perp-only + auto-leaderboard tracking)...")

    while True:
        db = SessionLocal()
        try:
            all_spot_events = []  # kosong (spot nonaktif)
            all_perp_events = []

            now_ts = int(time.time())

            # === Leaderboard refresh setiap 15 menit ===
            if now_ts - last_discovery_ts > 900:
                logger.info("[Discovery] Updating leaderboard wallets...")
                refresh_leaderboard_wallets(db)
                last_discovery_ts = now_ts

            # === Ambil semua wallet di DB sebagai tracked list ===
            wallets_in_db = [w.address for w in db.query(Wallet).all()]
            for pc in perp_connectors:
                if hasattr(pc, "set_tracked_wallets"):
                    pc.set_tracked_wallets(wallets_in_db)

            # === Fetch perp events ===
            for pc in perp_connectors:
                ev = pc.fetch_new_events(last_ts_perp[pc.platform_name])
                all_perp_events.extend(ev)
                last_ts_perp[pc.platform_name] = now_ts

            # === Update skor wallet yang baru ada event ===
            affected_wallets = set()
            for e in all_perp_events:
                affected_wallets.add(e["wallet_address"].lower())

            for addr in affected_wallets:
                wallet = db.query(Wallet).get(addr)
                if not wallet:
                    wallet = Wallet(address=addr)
                    db.add(wallet)

                score = compute_smart_score_from_wallet(wallet)
                tier = classify_tier(score)

                wallet.smart_score = score
                wallet.tier = tier

            db.commit()

            # === Generate signals dari perp saja ===
            new_signals = create_signals_from_events(
                db,
                all_spot_events,
                all_perp_events,
                min_spot_size_usd=min_spot_size_usd,
                min_perp_size_usd=min_perp_size_usd,
            )

            # === Signals → Alerts (dengan setup entry/SL/TP) ===
            alerts = process_signals_into_alerts(
                db,
                new_signals,
                risk_per_trade_default=risk_default,
            )

            # === Kirim Telegram ===
            if tele:
                for a in alerts:
                    tele.send_alert(a)

            db.close()

        except Exception as e:
            logger.exception(f"Error in main loop: {e}")
            db.close()

        time.sleep(5)
