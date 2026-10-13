"""퀀트 관점 상승 가능성 점수 (가중 합산, 0~100)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _safe(v, default=50.0):
    try:
        v = float(v)
        if np.isnan(v) or np.isinf(v):
            return default
        return max(0.0, min(100.0, v))
    except Exception:
        return default


def momentum_score(close: pd.Series) -> tuple[float, dict]:
    """1/3/6개월 수익률 기반."""
    rets = {}
    for n, label in [(20, "1M"), (60, "3M"), (120, "6M")]:
        if len(close) > n:
            rets[label] = float(close.iloc[-1] / close.iloc[-n - 1] - 1)
        else:
            rets[label] = 0.0
    # 각 수익률을 -20%~+40% 구간을 0~100으로 매핑 후 가중평균
    def map_ret(r):
        return max(0.0, min(100.0, (r + 0.20) / 0.60 * 100))

    score = map_ret(rets["1M"]) * 0.5 + map_ret(rets["3M"]) * 0.3 + map_ret(rets["6M"]) * 0.2
    return _safe(score), {k: round(v * 100, 2) for k, v in rets.items()}


def trend_score(df: pd.DataFrame) -> tuple[float, dict]:
    last = df.iloc[-1]
    c = float(last["close"])
    pts = 0.0
    detail = {}
    for col, w in [("ma20", 30), ("ma60", 40), ("ma120", 30)]:
        ma = float(last[col]) if pd.notna(last.get(col)) else float("nan")
        if pd.notna(ma) and ma > 0:
            ratio = (c / ma - 1) * 100
            detail[col] = round(ratio, 2)
            # -10%~-+10%를 0~100 매핑
            pts += max(0.0, min(100.0, (ratio + 10) / 20 * 100)) * (w / 100)
        else:
            detail[col] = None
    return _safe(pts), detail


def volatility_score(close: pd.Series) -> tuple[float, dict]:
    ret = close.pct_change().dropna().tail(120)
    if len(ret) < 20:
        return 50.0, {"ann_vol_pct": None, "mdd_pct": None}
    ann_vol = float(ret.std() * np.sqrt(252) * 100)
    cum = (1 + ret).cumprod()
    mdd = float((cum / cum.cummax() - 1).min() * 100)
    # 변동성 낮을수록, 낙폭 작을수록 고점
    vol_pts = max(0.0, min(100.0, (60 - ann_vol) / 60 * 100))  # 60%→0점, 0%→100점
    mdd_pts = max(0.0, min(100.0, (mdd + 40) / 40 * 100))  # -40%→0점
    return _safe(vol_pts * 0.5 + mdd_pts * 0.5), {"ann_vol_pct": round(ann_vol, 2), "mdd_pct": round(mdd, 2)}


def volume_score(df: pd.DataFrame) -> tuple[float, dict]:
    last = df.iloc[-1]
    vr = float(last.get("vol_ratio", 1.0)) if pd.notna(last.get("vol_ratio", 1.0)) else 1.0
    obv_now = float(df["obv"].iloc[-1]) if "obv" in df else 0.0
    obv_past = float(df["obv"].iloc[-21]) if "obv" in df and len(df) > 21 else 0.0
    obv_up = obv_now > obv_past
    # 거래대금 급등(과열은 감점): 0.5배→30점, 1배→60점, 1.5~2배→80점, 4배↑→40점
    if vr <= 0.5:
        pts = 30
    elif vr <= 1.2:
        pts = 50 + (vr - 0.5) * (20 / 0.7)
    elif vr <= 2.5:
        pts = 70 + (vr - 1.2) * (15 / 1.3)
    else:
        pts = max(35.0, 85 - (vr - 2.5) * 10)
    if obv_up:
        pts += 8
    else:
        pts -= 8
    return _safe(pts), {"vol_ratio": round(vr, 2), "obv_up": bool(obv_up)}


def rsi_score(rsi_val: float) -> tuple[float, str]:
    # 45~65 최적, 30 이하 과매도 반등 기대 중간, 75↑ 과열 감점
    r = float(rsi_val)
    if 45 <= r <= 65:
        return 80.0, "적정 모멘텀 구간"
    if 65 < r <= 70:
        return 65.0, "강세이나 과열 접근"
    if r > 70:
        return 35.0, "과매수 과열 — 추격 주의"
    if 40 <= r < 45:
        return 55.0, "중립 약화"
    if 30 <= r < 40:
        return 45.0, "약세 — 저점 탐색"
    return 55.0, "과매도 — 기술적 반등 가능 (분할 관점)"


def value_score(fund: dict) -> tuple[float, dict]:
    """PER/PBR 기반 밸류. 데이터 없으면 50 중립."""
    def num(x):
        try:
            return float(str(x).replace(",", ""))
        except Exception:
            return None

    per = num(fund.get("per"))
    pbr = num(fund.get("pbr"))
    pts_list, detail = [], {}
    if per is not None and 0 < per < 100:
        # PER 8→90점, 15→65점, 30→35점 선형 근사
        p = max(0.0, min(100.0, 100 - (per - 5) * 2.4))
        pts_list.append(p)
        detail["PER"] = per
    if pbr is not None and 0 < pbr < 20:
        p = max(0.0, min(100.0, 100 - (pbr - 0.5) * 28))
        pts_list.append(p)
        detail["PBR"] = pbr
    if not pts_list:
        return 50.0, {"note": "밸류 데이터 없음 → 중립"}
    return _safe(sum(pts_list) / len(pts_list)), detail


WEIGHTS = {"momentum": 0.25, "trend": 0.25, "volatility": 0.15, "volume": 0.15, "rsi": 0.10, "value": 0.10}


def quant_total(df_ind: pd.DataFrame, fund: dict) -> dict:
    close = df_ind["close"]
    last_rsi = float(df_ind["rsi14"].iloc[-1])
    m_pts, m_ret = momentum_score(close)
    t_pts, t_det = trend_score(df_ind)
    v_pts, v_det = volatility_score(close)
    vo_pts, vo_det = volume_score(df_ind)
    r_pts, r_note = rsi_score(last_rsi)
    va_pts, va_det = value_score(fund)

    parts = {"momentum": m_pts, "trend": t_pts, "volatility": v_pts,
             "volume": vo_pts, "rsi": r_pts, "value": va_pts}
    total = sum(parts[k] * WEIGHTS[k] for k in parts)
    total = _safe(total)

    if total >= 80:
        grade, upside = "S", "매우 높음"
    elif total >= 65:
        grade, upside = "A", "높음"
    elif total >= 50:
        grade, upside = "B", "보통"
    elif total >= 35:
        grade, upside = "C", "낮음"
    else:
        grade, upside = "D", "매우 낮음"

    # 상승 확률 프록시 (로지스틱 변환, 참고용)
    prob = 1 / (1 + np.exp(-(total - 50) / 12)) * 100

    return {
        "total": round(total, 1),
        "grade": grade,
        "upside": upside,
        "up_prob": round(float(prob), 1),
        "parts": {k: round(float(v), 1) for k, v in parts.items()},
        "details": {"returns_pct": m_ret, "ma_gap_pct": t_det, **v_det, **vo_det,
                    "rsi_note": r_note, "value": va_det},
        "weights": WEIGHTS,
    }
