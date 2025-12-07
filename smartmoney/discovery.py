# smartmoney/discovery.py
from typing import List
import requests
from loguru import logger
from sqlalchemy.orm import Session

from .env import env
from .models import Wallet
from .tracked import load_config


_config = load_config()
_disc_cfg = _config.get("discovery", {}) if _config else {}

TOP_N_DEFAULT = _disc_cfg.get("top_n", 50)
MIN_ACCOUNT_VALUE_DEFAULT = _disc_cfg.get("min_account_value", 10_000.0)


def _get_leaderboard_url() -> str:
    return env(
        "HYPERLIQUID_LEADERBOARD_URL",
        "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard",
    )


def _fetch_leaderboard_raw() -> dict:
    url = _get_leaderboard_url()
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"[Discovery] Error fetching leaderboard from {url}: {e}")
        return {}


def _extract_addresses_from_raw(raw: dict, top_n: int, min_account_value: float) -> List[str]:
    """
    Raw format (lihat client Go):
    {
      "leaderboardRows": [
        {
          "ethAddress": "0x....",
          "accountValue": "12345.67",
          "windowPerformances": [
            [pnl_day, roi_day, vlm_day],
            [pnl_week, roi_week, vlm_week],
            [pnl_month, roi_month, vlm_month],
            [pnl_all, roi_all, vlm_all]
          ]
        },
        ...
      ]
    }
    1
    """
    rows = raw.get("leaderboardRows", [])
    addrs: List[str] = []
    for row in rows[:top_n]:
        try:
            addr = row.get("ethAddress")
            if not addr:
                continue
            acct_val = float(row.get("accountValue", "0") or 0.0)
            if acct_val < min_account_value:
                continue
            addrs.append(addr)
        except Exception:
            continue
    return addrs


def refresh_leaderboard_wallets(
    db: Session,
    top_n: int = TOP_N_DEFAULT,
    min_account_value: float = MIN_ACCOUNT_VALUE_DEFAULT,
) -> List[str]:
    """
    Ambil leaderboard → update tabel Wallet → return list address yang dari leaderboard.
    NOTE: kita tidak mengubah smart_score di sini; scoring engine akan handle sendiri.
    """
    logger.info(
        f"[Discovery] Refresh leaderboard wallets (top_n={top_n}, min_account_value={min_account_value})"
    )
    raw = _fetch_leaderboard_raw()
    if not raw:
        return []

    addrs = _extract_addresses_from_raw(raw, top_n=top_n, min_account_value=min_account_value)
    if not addrs:
        logger.warning("[Discovery] No addresses passed filters from leaderboard")
        return []

    existing = {w.address for w in db.query(Wallet).filter(Wallet.address.in_(addrs)).all()}
    new_addrs = [a for a in addrs if a not in existing]

    for addr in new_addrs:
        w = Wallet(address=addr)
        db.add(w)

    if new_addrs:
        logger.info(f"[Discovery] Added {len(new_addrs)} new wallets from leaderboard")
        db.commit()
    else:
        logger.info("[Discovery] No new wallets to add from leaderboard")

    return addrs
