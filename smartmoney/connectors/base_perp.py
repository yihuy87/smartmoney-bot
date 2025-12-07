# smartmoney/connectors/base_perp.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BasePerpConnector(ABC):
    platform_name: str

    @abstractmethod
    def fetch_new_events(self, since_ts: int) -> List[Dict[str, Any]]:
        """
        Normalized perp event:
        {
          "wallet_address": str,
          "platform": str,
          "pair": str,
          "direction": "LONG"/"SHORT",
          "event_type": "OPEN"/"CLOSE"/"INCREASE"/"DECREASE",
          "entry_price": float,
          "size_usd": float,
          "leverage": float,
          "timestamp": int
        }
        """
        ...
