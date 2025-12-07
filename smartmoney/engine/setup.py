# smartmoney/engine/setup.py
def generate_trade_setup(mode: str, price: float, risk_per_trade: float):
    price = price or 0.0
    if price <= 0:
        price = 1.0

    market = "PERP"
    if mode in ("SPOT_LONG", "EXIT"):
        market = "SPOT"

    if "LONG" in mode:
        entry_min = price * 0.995
        entry_max = price * 1.005
        stop_loss = price * 0.90
        tp1 = price * 1.05
        tp2 = price * 1.15
        tp3 = price * 1.30
    elif "SHORT" in mode:
        entry_min = price * 0.995
        entry_max = price * 1.005
        stop_loss = price * 1.10
        tp1 = price * 0.95
        tp2 = price * 0.85
        tp3 = price * 0.70
    else:
        entry_min = price
        entry_max = price
        stop_loss = price
        tp1 = price
        tp2 = price
        tp3 = price

    return {
        "mode": "LONG" if "LONG" in mode else ("SHORT" if "SHORT" in mode else "NONE"),
        "market": market,
        "entry_min": entry_min,
        "entry_max": entry_max,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "suggested_risk_per_trade": risk_per_trade,
    }
