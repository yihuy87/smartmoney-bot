# smartmoney/connectors/mock_connectors.py
from typing import List, Dict, Any
import time

from .base_spot import BaseSpotConnector
from .base_perp import BasePerpConnector

class MockSpotConnector(BaseSpotConnector):
    def __init__(self, chain_id: str = "mock"):
        self.chain_id = chain_id
        self.dex = "mock_dex"
        self._block = 0

    def get_latest_block(self) -> int:
        self._block += 1
        return self._block

    def fetch_new_events(self, from_block: int, to_block: int) -> List[Dict[str, Any]]:
        now = int(time.time())
        return [{
            "wallet_address": "0xMOCKWALLET",
            "chain_id": self.chain_id,
            "dex": self.dex,
            "tx_hash": f"0xMOCKTX{to_block}",
            "timestamp": now,
            "token_address": "0xMOCKTOKEN",
            "token_symbol": "MOCK",
            "side": "BUY",
            "amount_usd": 10000.0,
            "price": 1.0,
            "liquidity_usd": 500000.0,
        }]

class MockPerpConnector(BasePerpConnector):
    def __init__(self):
        self.platform_name = "mock_perp"

    def fetch_new_events(self, since_ts: int) -> List[Dict[str, Any]]:
        now = int(time.time())
        return [{
            "wallet_address": "0xMOCKWALLET",
            "platform": self.platform_name,
            "pair": "MOCK-PERP",
            "direction": "LONG",
            "event_type": "OPEN",
            "entry_price": 1.0,
            "size_usd": 50000.0,
            "leverage": 3.0,
            "timestamp": now,
        }]
