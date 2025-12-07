# smartmoney/engine/events.py
from typing import List, Dict, Any

def group_events_by_wallet_and_asset(
    spot_events: List[Dict[str, Any]],
    perp_events: List[Dict[str, Any]],
):
    contexts = {}
    for e in spot_events:
        key = (e["wallet_address"], e["token_symbol"])
        ctx = contexts.setdefault(key, {"spot": [], "perp": []})
        ctx["spot"].append(e)

    for e in perp_events:
        token_symbol = e["pair"].split("-")[0]
        key = (e["wallet_address"], token_symbol)
        ctx = contexts.setdefault(key, {"spot": [], "perp": []})
        ctx["perp"].append(e)

    return contexts
