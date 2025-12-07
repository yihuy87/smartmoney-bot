# smartmoney/connectors/evm_spot_uniswap.py
from typing import List, Dict, Any
from web3 import Web3
from loguru import logger

from .base_spot import BaseSpotConnector
from ..tracked import is_tracked_wallet

UNISWAP_V2_SWAP_TOPIC = Web3.keccak(
    text="Swap(address,uint256,uint256,uint256,uint256,address)"
).hex()

PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "token0",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token1",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]

KNOWN_STABLES = {
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48".lower(),  # USDC
    "0xdac17f958d2ee523a2206206994597c13d831ec7".lower(),  # USDT
    "0x6b175474e89094c44da98b954eedeac495271d0f".lower(),  # DAI
}

class UniswapV2SpotConnector(BaseSpotConnector):
    def __init__(self, chain_id: str, rpc_url: str, dex_name: str = "uniswap_v2"):
        self.chain_id = chain_id
        self.dex = dex_name
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            logger.warning(f"[{chain_id}] RPC not connected")

        self._pair_cache = {}
        self._token_meta = {}

    def get_latest_block(self) -> int:
        return self.w3.eth.block_number

    def _get_pair_tokens(self, pair_addr: str):
        addr = self.w3.to_checksum_address(pair_addr)
        if addr in self._pair_cache:
            return self._pair_cache[addr]
        pair = self.w3.eth.contract(address=addr, abi=PAIR_ABI)
        t0 = pair.functions.token0().call()
        t1 = pair.functions.token1().call()
        self._pair_cache[addr] = (t0, t1)
        return t0, t1

    def _get_token_meta(self, token_addr: str):
        addr = self.w3.to_checksum_address(token_addr)
        if addr in self._token_meta:
            return self._token_meta[addr]
        c = self.w3.eth.contract(address=addr, abi=ERC20_ABI)
        try:
            symbol = c.functions.symbol().call()
        except Exception:
            symbol = "UNKNOWN"
        try:
            decimals = c.functions.decimals().call()
        except Exception:
            decimals = 18
        self._token_meta[addr] = (symbol, decimals)
        return symbol, decimals

    def fetch_new_events(self, from_block: int, to_block: int) -> List[Dict[str, Any]]:
        logger.info(f"[{self.chain_id}] Fetching Swap logs {from_block}–{to_block}")
        logs = self.w3.eth.get_logs({
            "fromBlock": from_block,
            "toBlock": to_block,
            "topics": [UNISWAP_V2_SWAP_TOPIC]
        })
        events: List[Dict[str, Any]] = []

        for log in logs:
            try:
                tx = self.w3.eth.get_transaction(log["transactionHash"])
                wallet = tx["from"]
                if not is_tracked_wallet(wallet):
                    continue

                block = self.w3.eth.get_block(log["blockNumber"])
                ts = block["timestamp"]

                pair_addr = log["address"]
                token0, token1 = self._get_pair_tokens(pair_addr)
                t0_sym, t0_dec = self._get_token_meta(token0)
                t1_sym, t1_dec = self._get_token_meta(token1)

                data_bytes = bytes.fromhex(log["data"][2:])
                amount0_in, amount1_in, amount0_out, amount1_out = \
                    self.w3.codec.decode(["uint256", "uint256", "uint256", "uint256"], data_bytes)

                token0_lower = token0.lower()
                token1_lower = token1.lower()

                amt0_in = amount0_in / (10 ** t0_dec)
                amt1_in = amount1_in / (10 ** t1_dec)
                amt0_out = amount0_out / (10 ** t0_dec)
                amt1_out = amount1_out / (10 ** t1_dec)

                if token0_lower in KNOWN_STABLES and token1_lower not in KNOWN_STABLES:
                    main_token_addr = token1
                    main_symbol = t1_sym
                    if amt1_out > 0:
                        side = "BUY"
                        amount_token = amt1_out
                        stable_amount = amt0_in
                    else:
                        side = "SELL"
                        amount_token = amt1_in
                        stable_amount = amt0_out
                elif token1_lower in KNOWN_STABLES and token0_lower not in KNOWN_STABLES:
                    main_token_addr = token0
                    main_symbol = t0_sym
                    if amt0_out > 0:
                        side = "BUY"
                        amount_token = amt0_out
                        stable_amount = amt1_in
                    else:
                        side = "SELL"
                        amount_token = amt0_in
                        stable_amount = amt1_out
                else:
                    main_token_addr = token0
                    main_symbol = t0_sym
                    side = "BUY" if amt0_out > 0 else "SELL"
                    amount_token = amt0_out if amt0_out > 0 else amt0_in
                    stable_amount = 0.0

                if stable_amount > 0 and amount_token > 0:
                    price = stable_amount / amount_token
                    amount_usd = stable_amount
                else:
                    price = 0.0
                    amount_usd = 0.0

                events.append({
                    "wallet_address": wallet,
                    "chain_id": self.chain_id,
                    "dex": self.dex,
                    "tx_hash": tx["hash"].hex(),
                    "timestamp": int(ts),
                    "token_address": main_token_addr,
                    "token_symbol": main_symbol,
                    "side": side,
                    "amount_usd": float(amount_usd),
                    "price": float(price),
                    "liquidity_usd": 0.0,
                })
            except Exception as e:
                logger.error(f"[{self.chain_id}] Error parsing log: {e}")
        return events
