# smartmoney/tracked.py
import yaml

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

_config = load_config()

_TRACKED = {
    w["address"].lower(): w
    for w in _config.get("tracked_wallets", [])
}

def is_tracked_wallet(address: str) -> bool:
    if not address:
        return False
    return address.lower() in _TRACKED

def get_tracked_wallet_info(address: str):
    if not address:
        return None
    return _TRACKED.get(address.lower())
