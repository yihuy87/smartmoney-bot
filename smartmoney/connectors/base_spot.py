# smartmoney/connectors/base_spot.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseSpotConnector(ABC):
    chain_id: str

    @abstractmethod
    def get_latest_block(self) -> int:
        ...

    @abstractmethod
    def fetch_new_events(self, from_block: int, to_block: int) -> List[Dict[str, Any]]:
        """
        Normalized spot event:
        {
          "wallet_address": str,
          "chain_id": str,
          "dex": str,
          "tx_hash": str,
          "timestamp": int,
          "token_address": str,
          "token_symbol": str,
          "side": "BUY"/"SELL",
          "amount_usd": float,
          "price": float,
          "liquidity_usd": float
        }
        """
        ...
