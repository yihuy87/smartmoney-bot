# smartmoney/scoring.py
from .models import Wallet


def _score_roi_all(roi_all_frac: float) -> float:
    """
    roi_all_frac = ROI total dalam fraksi (0.5 = 50%).
    Kita map ke skor 0–100.
    """
    roi_pct = roi_all_frac * 100.0
    if roi_pct < 0:
        return 20
    if roi_pct < 20:
        return 60
    if roi_pct < 50:
        return 80
    if roi_pct < 100:
        return 90
    return 95


def _score_equity(account_value_usd: float) -> float:
    """
    Account value / equity:
    - < 1k  → kecil
    - 1k-10k
    - 10k-100k
    - >100k
    """
    v = account_value_usd
    if v < 1_000:
        return 40
    if v < 10_000:
        return 60
    if v < 100_000:
        return 80
    return 90


def _score_pnl_all(pnl_all_usd: float) -> float:
    """
    Total PnL sepanjang waktu (USDC).
    """
    p = pnl_all_usd
    if p < 0:
        return 30
    if p < 10_000:
        return 60
    if p < 100_000:
        return 80
    return 95


def compute_smart_score_from_wallet(wallet: Wallet) -> float:
    """
    Skor akhir 0–100 berdasarkan:
    - ROI total (paling berat)
    - account value
    - total PnL
    """
    roi_score = _score_roi_all(wallet.roi_all or 0.0)
    eq_score = _score_equity(wallet.account_value_usd or 0.0)
    pnl_score = _score_pnl_all(wallet.pnl_all_usd or 0.0)

    smart_score = (
        0.5 * roi_score +
        0.3 * eq_score +
        0.2 * pnl_score
    )
    return smart_score


def classify_tier(score: float) -> str:
    """
    Threshold tier:
    - S: >= 85
    - A: >= 70
    - B: >= 60
    - lainnya: ignore
    """
    if score >= 85:
        return "S"
    if score >= 70:
        return "A"
    if score >= 60:
        return "B"
    return "ignore"
