# smartmoney/scoring.py
from typing import List
from .models import Wallet


def _score_roi_all(roi_all_frac: float) -> float:
    """
    Skor ROI total (fraksi, 0.5 = 50%):
    - ROI <= -50%  → 0
    - -50%..0%     → 0..40
    - 0..50%       → 40..80
    - 50%..300%    → 80..100
    - >300%        → 100
    """
    roi_pct = (roi_all_frac or 0.0) * 100.0

    if roi_pct <= -50:
        return 0.0
    if roi_pct >= 300:
        return 100.0

    if roi_pct < 0:
        # -50 → 0  maps to 0 → 40
        return 40.0 * (roi_pct + 50.0) / 50.0

    if roi_pct < 50:
        # 0 → 50  maps to 40 → 80
        return 40.0 + 40.0 * (roi_pct / 50.0)

    # 50 → 300 maps to 80 → 100
    return 80.0 + 20.0 * ((roi_pct - 50.0) / 250.0)


def _score_equity(account_value_usd: float) -> float:
    """
    Skor berdasarkan equity/account value:
    - < 1k      → 40
    - 1k–10k    → 55
    - 10k–50k   → 70
    - 50k–200k  → 85
    - > 200k    → 95
    """
    v = account_value_usd or 0.0
    if v < 1_000:
        return 40.0
    if v < 10_000:
        return 55.0
    if v < 50_000:
        return 70.0
    if v < 200_000:
        return 85.0
    return 95.0


def _score_pnl_all(pnl_all_usd: float) -> float:
    """
    Skor berdasarkan total PnL sepanjang waktu:
    - < 0         → 30
    - 0–10k       → 60
    - 10k–100k    → 80
    - 100k–1M     → 90
    - > 1M        → 98
    """
    p = pnl_all_usd or 0.0
    if p < 0:
        return 30.0
    if p < 10_000:
        return 60.0
    if p < 100_000:
        return 80.0
    if p < 1_000_000:
        return 90.0
    return 98.0


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
        0.6 * roi_score +
        0.25 * eq_score +
        0.15 * pnl_score
    )
    return float(smart_score)


def assign_tiers_by_rank(
    wallets: List[Wallet],
    min_score: float = 0.0,
    frac_s: float = 0.10,
    frac_a: float = 0.30,
    frac_b: float = 0.60,
) -> None:
    """
    Rank-based tiering:
    - Sort wallet berdasarkan smart_score (desc).
    - Hanya wallet dengan score >= min_score yang dikasih tier.
    - Sisanya: tier = "ignore".

    frac_s, frac_a, frac_b = persentase populasi:
    - top frac_s  → S
    - berikutnya sampai frac_a → A
    - berikutnya sampai frac_b → B
    - sisanya     → ignore
    """
    if not wallets:
        return

    # sort desc by score
    sorted_wallets = sorted(
        wallets,
        key=lambda w: (w.smart_score or 0.0),
        reverse=True,
    )
    n = len(sorted_wallets)
    if n == 0:
        return

    for idx, w in enumerate(sorted_wallets):
        score = float(w.smart_score or 0.0)

        if score < min_score:
            w.tier = "ignore"
            continue

        rank = (idx + 1) / n  # 1..n → (0,1]

        if rank <= frac_s:
            w.tier = "S"
        elif rank <= frac_a:
            w.tier = "A"
        elif rank <= frac_b:
            w.tier = "B"
        else:
            w.tier = "ignore"
