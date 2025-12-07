# smartmoney/connectors/perp_hyperliquid.py
from typing import List, Dict, Any
import time
import requests
from loguru import logger

from .base_perp import BasePerpConnector


class HyperliquidConnector(BasePerpConnector):
    """
    Connector perp Hyperliquid pakai Info API (public):
    - Endpoint: POST https://api.hyperliquid.xyz/info
    - type: "userFillsByTime"
    - Per wallet, ambil trade perp (Open/Increase Long/Short)
    - Daftar wallet diisi dinamis lewat .set_tracked_wallets([...])
    """

    def __init__(self, base_url: str = "https://api.hyperliquid.xyz/info"):
        self.platform_name = "hyperliquid"
        self.base_url = base_url.rstrip("/")
        self._tracked_wallets: List[str] = []

    def set_tracked_wallets(self, wallets: List[str]):
        """
        Set ulang daftar wallet yang akan di-scan.
        wallets: list of address string (0x...)
        """
        uniq = {w.lower() for w in wallets if w}
        self._tracked_wallets = list(uniq)
        logger.info(f"[Hyperliquid] Tracked wallets updated, count={len(self._tracked_wallets)}")

    def _fetch_fills_for_wallet(self, wallet: str, since_ts: int) -> List[Dict[str, Any]]:
        """
        Call userFillsByTime untuk 1 wallet:
        - startTime / endTime dalam ms
        - since_ts masuk dalam detik → dikali 1000
        """
        start_ms = since_ts * 1000
        end_ms = int(time.time() * 1000)

        body = {
            "type": "userFillsByTime",
            "user": wallet,
            "startTime": start_ms,
            "endTime": end_ms,
            "aggregateByTime": True,
        }

        try:
            resp = requests.post(
                self.base_url,
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"[Hyperliquid] Error calling userFillsByTime for {wallet}: {e}")
            return []

        try:
            fills = resp.json()
        except Exception as e:
            logger.error(f"[Hyperliquid] Failed to decode JSON for {wallet}: {e}")
            return []

        if not isinstance(fills, list):
            logger.warning(f"[Hyperliquid] Unexpected response format for {wallet}: {fills}")
            return []

        return fills

    def fetch_new_events(self, since_ts: int) -> List[Dict[str, Any]]:
        """
        Convert fills -> perp events:
        - Filter hanya perp coin (coin tidak dimulai '@' dan tidak mengandung '/')
        - Gunakan field `dir`:
          * "Open Long"      → LONG,  OPEN
          * "Open Short"     → SHORT, OPEN
          * "Increase Long"  → LONG,  INCREASE
          * "Increase Short" → SHORT, INCREASE
        - size_usd = px * sz
        - time dari API dalam ms → kita convert ke detik
        """
        all_events: List[Dict[str, Any]] = []
        now = int(time.time())

        if not self._tracked_wallets:
            logger.info("[Hyperliquid] No tracked wallets set, skipping fetch")
            return []

        logger.info(
            f"[Hyperliquid] Fetching fills since {since_ts} for {len(self._tracked_wallets)} wallets..."
        )

        for wal in self._tracked_wallets:
            fills = self._fetch_fills_for_wallet(wal, since_ts)
            for f in fills:
                try:
                    coin = f.get("coin")
                    # Spot / index fill biasanya '@...' atau 'TOKEN/USDC' → skip
                    if not coin or coin.startswith("@") or "/" in coin:
                        continue

                    dir_str = f.get("dir", "") or ""
                    dir_str = str(dir_str)

                    if "Open Long" in dir_str:
                        direction = "LONG"
                        event_type = "OPEN"
                    elif "Open Short" in dir_str:
                        direction = "SHORT"
                        event_type = "OPEN"
                    elif "Increase Long" in dir_str:
                        direction = "LONG"
                        event_type = "INCREASE"
                    elif "Increase Short" in dir_str:
                        direction = "SHORT"
                        event_type = "INCREASE"
                    else:
                        # Close / reduce / lainnya tidak kita pakai sebagai entry sinyal
                        continue

                    px = float(f.get("px", "0") or 0.0)
                    sz = float(f.get("sz", "0") or 0.0)
                    size_usd = px * sz

                    raw_time = f.get("time", now)
                    try:
                        ts_ms = int(raw_time)
                        # convert ms → detik
                        ts = ts_ms // 1000
                    except Exception:
                        ts = now

                    if size_usd <= 0:
                        continue

                    all_events.append(
                        {
                            "wallet_address": wal.lower(),
                            "platform": self.platform_name,
                            "pair": f"{coin}-PERP",
                            "direction": direction,
                            "event_type": event_type,
                            "entry_price": px,
                            "size_usd": size_usd,
                            "leverage": 1.0,
                            "timestamp": ts,
                        }
                    )
                except Exception as e:
                    logger.error(f"[Hyperliquid] Error parsing fill for {wal}: {e}")

        logger.info(f"[Hyperliquid] New perp events (since {since_ts}): {len(all_events)}")
        return all_events
