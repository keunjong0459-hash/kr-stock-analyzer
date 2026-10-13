"""지수 전체 흐름 + 매크로 호재/악재 판단 (규칙 기반, 무료 데이터)."""

from __future__ import annotations

import pandas as pd


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def _close(df: pd.DataFrame) -> pd.Series:
    cols = [str(c).lower() for c in df.columns]
    if "close" in cols:
        return df.iloc[:, cols.index("close")]
    return df.iloc[:, 0]


def judge_index(name: str, df: pd.DataFrame | None) -> dict:
    if df is None or len(df) < 65:
        return {"name": name, "status": "데이터 부족", "direction": 0,
                "desc": "지수 데이터를 가져오지 못했습니다.", "ret20": None}
    c = _close(df).dropna()
    last = float(c.iloc[-1])
    ma20 = float(_sma(c, 20).iloc[-1])
    ma60 = float(_sma(c, 60).iloc[-1])
    ret20 = float(c.iloc[-1] / c.iloc[-21] - 1) * 100
    if last > ma20 > ma60 and ret20 > 2:
        return {"name": name, "status": "상승 추세", "direction": 1,
                "desc": f"MA20({ma20:,.0f})·MA60({ma60:,.0f}) 상회, 20일 +{ret20:.1f}%", "ret20": round(ret20, 2)}
    if last < ma20 < ma60 and ret20 < -2:
        return {"name": name, "status": "하락 추세", "direction": -1,
                "desc": f"MA20·MA60 하회, 20일 {ret20:.1f}%", "ret20": round(ret20, 2)}
    if ret20 > 0:
        return {"name": name, "status": "횡보·반등 시도", "direction": 0,
                "desc": f"20일 {ret20:+.1f}%, 이평선 혼조", "ret20": round(ret20, 2)}
    return {"name": name, "status": "횡보·조정", "direction": 0,
            "desc": f"20일 {ret20:.1f}%, 방향 탐색", "ret20": round(ret20, 2)}


def judge_macro(bundle: dict) -> dict:
    bullish: list[str] = []
    bearish: list[str] = []
    neutrals: list[str] = []

    def last_close(key):
        try:
            df = bundle[key]["df"]
            if df is None or len(df) < 25:
                return None, None
            c = _close(df).dropna()
            return float(c.iloc[-1]), c
        except Exception:
            return None, None

    # KOSPI / KOSDAQ
    idx_results = {}
    for k, label in [("KOSPI", "코스피"), ("KOSDAQ", "코스닥")]:
        df = bundle.get(k, {}).get("df")
        r = judge_index(label, df)
        idx_results[k] = r
        if r["direction"] > 0:
            bullish.append(f"{label} {r['status']}: {r['desc']} — 지수 추종 수급에 우호적")
        elif r["direction"] < 0:
            bearish.append(f"{label} {r['status']}: {r['desc']} — 시장 베타 역풍")
        else:
            neutrals.append(f"{label} {r['status']}: {r['desc']}")

    # 환율 (원/달러 상승=원화 약세 → 외국인 수급 부담, 수출주엔 호재)
    last, series = last_close("USDKRW")
    if last and series is not None and len(series) > 20:
        ma20 = float(series.rolling(20).mean().iloc[-1])
        chg = float(series.iloc[-1] / series.iloc[-21] - 1) * 100
        if last > ma20 and chg > 1.5:
            bearish.append(f"원/달러 상승({last:,.0f}원, 20일 +{chg:.1f}%) — 외국인 매도 압력 가능. 수출주엔 우호적")
        elif last < ma20 and chg < -1.0:
            bullish.append(f"원/달러 하락({last:,.0f}원, 20일 {chg:.1f}%) — 외국인 수급에 우호적")
        else:
            neutrals.append(f"원/달러 {last:,.0f}원 — 안정 흐름")

    # VIX
    last, series = last_close("VIX")
    if last:
        if last >= 28:
            bearish.append(f"VIX {last:.1f} — 공포 구간, 변동성 확대 주의")
        elif last >= 20:
            neutrals.append(f"VIX {last:.1f} — 경계 구간")
        else:
            bullish.append(f"VIX {last:.1f} — 안정, 위험선호 우호적")

    # 미국 10년 금리
    last, series = last_close("US10Y")
    if last and series is not None and len(series) > 20:
        prev = float(series.iloc[-21])
        if last >= 4.5:
            bearish.append(f"미 10년 금리 {last:.2f}% — 고금리 부담, 성장주 밸류에이션 역풍")
        elif last > prev + 0.3:
            bearish.append(f"미 10년 금리 급등({prev:.2f}%→{last:.2f}%) — 긴축 경계")
        elif last < prev - 0.2:
            bullish.append(f"미 10년 금리 하락({prev:.2f}%→{last:.2f}%) — 성장주에 우호적")
        else:
            neutrals.append(f"미 10년 금리 {last:.2f}% — 안정")

    # 나스닥/S&P
    for k, label in [("NASDAQ", "나스닥"), ("SP500", "S&P500")]:
        last, series = last_close(k)
        if last and series is not None and len(series) > 21:
            chg = float(series.iloc[-1] / series.iloc[-21] - 1) * 100
            if chg > 3:
                bullish.append(f"{label} 20일 +{chg:.1f}% — 글로벌 위험선호 회복")
            elif chg < -3:
                bearish.append(f"{label} 20일 {chg:.1f}% — 글로벌 조정 압력")
            else:
                neutrals.append(f"{label} 20일 {chg:+.1f}% — 횡보")

    score = len(bullish) - len(bearish)
    if score >= 3:
        regime, rdir = "Risk-On (우호적)", 1
    elif score >= 1:
        regime, rdir = "온건 우호", 1
    elif score <= -3:
        regime, rdir = "Risk-Off (경계)", -1
    elif score <= -1:
        regime, rdir = "온건 경계", -1
    else:
        regime, rdir = "중립·혼조", 0

    return {
        "indices": idx_results,
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutrals,
        "regime": regime,
        "direction": rdir,
        "score": score,
    }
