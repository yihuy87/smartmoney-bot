# smartmoney/scoring.py
from dataclasses import dataclass

@dataclass
class WalletStats:
    winrate_30d: float              # 0–1
    pnl_30d_usd: float
    max_drawdown_30d: float         # 0–1
    avg_leverage_30d: float
    rugpull_ratio_30d: float        # 0–1
    avg_trade_size_ratio: float     # 0–1

def _map_winrate(winrate: float) -> float:
    w = winrate * 100
    if w < 40: return 20
    if w < 50: return 50
    if w < 60: return 70
    if w < 70: return 85
    return 95

def _map_profitability(pnl: float) -> float:
    if pnl < 0: return 30
    if pnl < 0.3: return 70
    if pnl < 1.0: return 85
    return 95

def _map_drawdown(dd: float) -> float:
    d = dd * 100
    if d > 70: return 20
    if d > 50: return 40
    if d > 30: return 60
    if d > 15: return 80
    return 95

def _map_leverage(avg_lev: float) -> float:
    if avg_lev > 20: return 20
    if avg_lev > 10: return 40
    if avg_lev > 5:  return 60
    if avg_lev > 2:  return 80
    return 90

def _map_rugpull_ratio(r: float) -> float:
    p = r * 100
    if p > 30: return 20
    if p > 20: return 40
    if p > 10: return 60
    if p > 5:  return 80
    return 90

def _map_size_ratio(r: float) -> float:
    p = r * 100
    if p > 50: return 20
    if p > 30: return 40
    if p > 10: return 70
    if p > 5:  return 85
    return 95

def compute_smart_score(stats: WalletStats) -> float:
    winrate_score = _map_winrate(stats.winrate_30d)
    prof_score = _map_profitability(stats.pnl_30d_usd)
    dd_score = _map_drawdown(stats.max_drawdown_30d)
    lev_score = _map_leverage(stats.avg_leverage_30d)
    rug_score = _map_rugpull_ratio(stats.rugpull_ratio_30d)
    size_score = _map_size_ratio(stats.avg_trade_size_ratio)
    behavior_score = 70  # placeholder sederhana

    smart_score = (
        0.20 * winrate_score +
        0.20 * prof_score +
        0.15 * dd_score +
        0.15 * behavior_score +
        0.10 * lev_score +
        0.10 * rug_score +
        0.10 * size_score
    )
    return smart_score

def classify_tier(score: float) -> str:
    if score >= 80: return "S"
    if score >= 70: return "A"
    if score >= 60: return "B"
    return "ignore"
