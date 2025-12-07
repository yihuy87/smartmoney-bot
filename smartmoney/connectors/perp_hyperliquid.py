# smartmoney/connectors/perp_hyperliquid.py
from typing import List, Dict, Any
import time
import requests
from loguru import logger

from .base_perp import BasePerpConnector
from ..tracked import load_config

# ambil list wallet dari config.yaml (tracked_wallets)
_config = load_config()
_TRACKED = [w["address"] for w in _config.get("tracked_wallets", [])]


class HyperliquidConnector(BasePerpConnector):
    """
    Connector perp Hyperliquid pakai Info API (public):
    - type: "userFillsByTime"
    - per wallet, ambil trade perp (Open/Increase Long/Short)
    Dok: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
    """

    def __init__(self, base_url: str = "https://api.hyperliquid.xyz/info"):
        self.platform_name = "hyperliquid"
        self.base_url = base_url.rstrip("/")

    def _fetch_fills_for_wallet(self, wallet: str, since_ts: int) -> List[Dict[str, Any]]:
        """
        POST https://api.hyperliquid.xyz/info
        body:
        {
          "type": "userFillsByTime",
          "user": "0x....",
          "startTime": <ms>,
          "endTime": <ms>,
          "aggregateByTime": true
        }
        Returns: list of fills (perp + spot, kita filter sendiri).
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
                timeout=10,
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
        - doc: "Returns at most 2000 fills per response and only the 10000 most recent fills are available" 1
        - Kita ambil hanya:
          * perp coin (coin seperti 'BTC', 'ETH', dll)
          * arah:
            - 'Open Long', 'Increase Long' → LONG
            - 'Open Short', 'Increase Short' → SHORT
        - size_usd = px * sz (kasar tapi cukup buat sinyal)
        """
        all_events: List[Dict[str, Any]] = []
        now = int(time.time())

        logger.info(f"[Hyperliquid] Fetching fills since {since_ts} for tracked wallets...")

        for wal in _TRACKED:
            fills = self._fetch_fills_for_wallet(wal, since_ts)
            for f in fills:
                try:
                    coin = f.get("coin")
                    # Spot fill: coin seperti '@107' atau 'PURR/USDC' (lihat docs) 2
                    # Kita mau perp coin saja (BTC, ETH, SOL, dll)
                    if not coin or coin.startswith("@") or "/" in coin:
                        continue

                    dir_str = f.get("dir", "")
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
                        # Close / lainnya nggak dipakai sebagai sinyal entry
                        continue

                    px = float(f.get("px", "0") or 0.0)
                    sz = float(f.get("sz", "0") or 0.0)
                    size_usd = px * sz
                    ts = int(f.get("time", now))

                    if size_usd <= 0:
                        continue

                    all_events.append(
                        {
                            "wallet_address": wal,
                            "platform": self.platform_name,
                            "pair": f"{coin}-PERP",
                            "direction": direction,
                            "event_type": event_type,
                            "entry_price": px,
                            "size_usd": size_usd,
                            "leverage": 1.0,  # Info API tidak expose leverage langsung
                            "timestamp": ts,
                        }
                    )
                except Exception as e:
                    logger.error(f"[Hyperliquid] Error parsing fill for {wal}: {e}")

        logger.info(f"[Hyperliquid] New perp events (since {since_ts}): {len(all_events)}")
        return all_events
