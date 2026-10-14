"""당일 분봉 흐름 분석. yfinance 5분봉으로 오늘 장의 힘 읽기."""

from __future__ import annotations

import pandas as pd


def get_intraday(code: str, market: str = "", interval: str = "5m", period: str = "5d") -> pd.DataFrame:
    from src.data import _flatten_columns

    import yfinance as yf

    suffixes = [".KQ", ".KS"] if "KOSDAQ" in (market or "").upper() else [".KS", ".KQ"]
    errors: list[str] = []
    for sfx in suffixes:
        try:
            df = yf.download(code + sfx, period=period, interval=interval,
                             auto_adjust=False, progress=False, threads=False)
            if df is None or len(df) < 10:
                errors.append(f"{sfx}: 부족")
                continue
            df = _flatten_columns(df)
            need = {"open", "high", "low", "close", "volume"}
            if not need.issubset(set(df.columns)):
                errors.append(f"{sfx}: 컬럼 부족")
                continue
            df.index = pd.to_datetime(df.index)
            try:
                df.index = df.index.tz_convert("Asia/Seoul")
            except Exception:
                pass
            df = df.loc[:, ~df.columns.duplicated()].dropna(subset=["close"])
            if len(df) >= 10:
                return df
        except Exception as e:
            errors.append(f"{sfx}: {e}")
    raise RuntimeError("분봉 조회 실패: " + " | ".join(errors))


def analyze_session(df: pd.DataFrame) -> dict | None:
    if df is None or len(df) < 10:
        return None
    day = df.index[-1].date()
    sess = df[df.index.date == day]
    if len(sess) < 6:
        days = sorted(set(df.index.date))
        if len(days) < 2:
            return None
        day = days[-2]
        sess = df[df.index.date == day]
        if len(sess) < 6:
            return None

    o = float(sess["open"].iloc[0])
    h = float(sess["high"].max())
    l = float(sess["low"].min())
    c = float(sess["close"].iloc[-1])
    prev = df[df.index.date < day]
    prev_close = float(prev["close"].iloc[-1]) if len(prev) else o
    gap = (o / prev_close - 1) * 100 if prev_close else 0.0
    day_chg = (c / prev_close - 1) * 100 if prev_close else 0.0
    rng = (h / l - 1) * 100 if l else 0.0
    pos = (c - l) / (h - l) * 100 if h > l else 50.0

    tp = (sess["high"] + sess["low"] + sess["close"]) / 3
    cumvol = sess["volume"].cumsum()
    if float(cumvol.iloc[-1]) > 0:
        vwap = float(((tp * sess["volume"]).cumsum() / cumvol).iloc[-1])
    else:
        vwap = c
    above_vwap = c >= vwap

    n = len(sess)
    half = n // 2
    mid = float(sess["close"].iloc[half - 1]) if half else o
    am = (mid / o - 1) * 100 if o else 0.0
    pm = (c / mid - 1) * 100 if mid else 0.0

    ma20 = sess["close"].rolling(20).mean()
    ma_ok = len(sess) >= 20 and pd.notna(ma20.iloc[-1]) and pd.notna(ma20.iloc[-5])
    trend_up = bool(ma_ok and c > float(ma20.iloc[-1]) and float(ma20.iloc[-1]) >= float(ma20.iloc[-5]))

    score = 0
    lines: list[str] = []
    datestr = pd.to_datetime(day).strftime("%m월 %d일")
    lines.append(f"시가 {o:,.0f}원 출발 (어제보다 {gap:+.1f}%)")
    score += 1 if gap > 0.5 else (-1 if gap < -1 else 0)
    if pm > am:
        lines.append(f"오전 {am:+.1f}% / 오후 {pm:+.1f}% — 오후에 힘이 붙음")
    elif am > pm + 0.5:
        lines.append(f"오전 {am:+.1f}% / 오후 {pm:+.1f}% — 오전에 세고 오후에 식음")
    else:
        lines.append(f"오전 {am:+.1f}% / 오후 {pm:+.1f}% — 오전·오후 비슷")
    score += 1 if pm > 0.5 else (-1 if pm < -0.5 else 0)
    lines.append(f"평균 매수가격(VWAP) {vwap:,.0f}원보다 {'위' if above_vwap else '아래'}에서 끝남")
    score += 1 if above_vwap else -1
    if pos >= 80:
        lines.append(f"마감 위치: 하루 중 {pos:.0f}% 지점 — 고점 근처에서 끝나 강함")
        score += 1
    elif pos <= 20:
        lines.append(f"마감 위치: 하루 중 {pos:.0f}% 지점 — 저점 근처에서 끝나 약함")
        score -= 1
    else:
        lines.append(f"마감 위치: 하루 중 {pos:.0f}% 지점 — 중간")
    if ma_ok:
        lines.append(f"5분봉 평균선보다 {'위' if trend_up else '아래'} — 단기 흐름 {'위쪽' if trend_up else '아래쪽'}")
        score += 1 if trend_up else -1
    lines.append(f"하루 변동폭 {rng:.1f}% / 오늘 성적 {day_chg:+.1f}%")

    if score >= 3:
        verdict = "오늘 힘이 좋았어요. 내일 눌리면 단기로 노려보세요."
    elif score >= 1:
        verdict = "오늘 무난했어요. 내일 오전 흐름 보고 판단하세요."
    elif score >= -1:
        verdict = "오늘 오락가락했어요. 서두르지 마세요."
    else:
        verdict = "오늘 힘이 빠졌어요. 내일 아침 바로 사지 마세요."

    return {
        "date": datestr, "open": o, "high": h, "low": l, "close": c,
        "gap": round(gap, 2), "day_chg": round(day_chg, 2), "pos": round(pos, 1),
        "above_vwap": bool(above_vwap), "session_score": int(score),
        "lines": lines, "verdict": verdict, "frame": sess[["open", "high", "low", "close"]].copy(),
    }
