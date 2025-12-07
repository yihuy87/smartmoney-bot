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


def _parse_row_stats(row: dict):
    """
    Format umum (berdasarkan stats server Hyperliquid):
    {
      "ethAddress": "0x....",
      "accountValue": "12345.67",
      "windowPerformances": [
        [pnl_day, roi_day, volume_day],
        [pnl_week, roi_week, volume_week],
        [pnl_month, roi_month, volume_month],
        [pnl_all, roi_all, volume_all]
      ]
    }

    Kita ambil:
    - accountValue
    - pnl_all, roi_all (index ke-3 kalau ada)
    """
    acct_val = float(row.get("accountValue", "0") or 0.0)
    pnl_all = 0.0
    roi_all_frac = 0.0

    windows = row.get("windowPerformances") or []
    if len(windows) >= 4:
        all_row = windows[3] or []
        if len(all_row) >= 2:
            try:
                pnl_all = float(all_row[0] or 0.0)
                roi_all_pct = float(all_row[1] or 0.0)
                roi_all_frac = roi_all_pct / 100.0
            except Exception:
                pass

    return acct_val, pnl_all, roi_all_frac


def refresh_leaderboard_wallets(
    db: Session,
    top_n: int = TOP_N_DEFAULT,
    min_account_value: float = MIN_ACCOUNT_VALUE_DEFAULT,
) -> List[str]:
    """
    Ambil leaderboard → update/insert Wallet dengan:
    - account_value_usd
    - pnl_all_usd
    - roi_all
    Return: list address (string) yang lulus filter.
    """
    logger.info(
        f"[Discovery] Refresh leaderboard wallets (top_n={top_n}, min_account_value={min_account_value})"
    )
    raw = _fetch_leaderboard_raw()
    if not raw:
        return []

    rows = raw.get("leaderboardRows", [])
    selected_addrs: List[str] = []

    for row in rows[:top_n]:
        try:
            addr = row.get("ethAddress")
            if not addr:
                continue
            acct_val, pnl_all, roi_all = _parse_row_stats(row)
            if acct_val < min_account_value:
                continue

            addr_lc = addr.lower()
            wallet = db.query(Wallet).get(addr_lc)
            if not wallet:
                wallet = Wallet(address=addr_lc)
                db.add(wallet)

            wallet.account_value_usd = acct_val
            wallet.pnl_all_usd = pnl_all
            wallet.roi_all = roi_all

            selected_addrs.append(addr_lc)
        except Exception as e:
            logger.error(f"[Discovery] Error parsing leaderboard row: {e}")
            continue

    if selected_addrs:
        db.commit()
        logger.info(
            f"[Discovery] Upserted {len(selected_addrs)} wallets from leaderboard (after filters)"
        )
    else:
        logger.warning("[Discovery] No wallets passed filters from leaderboard")

    return selected_addrs
