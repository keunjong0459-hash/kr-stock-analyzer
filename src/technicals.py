"""기술적 분석 지표 (pandas/numpy만 사용, 외부 TA-Lib 불필요)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    gain = d.clip(lower=0)
    loss = -d.clip(upper=0)
    ag = gain.ewm(alpha=1 / n, adjust=False).mean()
    al = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = ag / al.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(50)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    m = ema(close, fast) - ema(close, slow)
    sig = m.ewm(span=signal, adjust=False).mean()
    return m, sig, m - sig


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std()
    return mid, mid + k * sd, mid - k * sd


def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14, m: int = 3):
    ll = low.rolling(n).min()
    hh = high.rolling(n).max()
    k = 100 * (close - ll) / (hh - ll).replace(0, np.nan)
    d = k.rolling(m).mean()
    return k.fillna(50), d.fillna(50)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    pc = close.shift(1)
    tr = pd.concat([high - low, (high - pc).abs(), (low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def obv(close: pd.Series, vol: pd.Series) -> pd.Series:
    direction = np.sign(close.diff().fillna(0))
    return (direction * vol.fillna(0)).cumsum()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    for n in (5, 20, 60, 120):
        df[f"ma{n}"] = sma(c, n)
    df["ema20"] = ema(c, 20)
    df["rsi14"] = rsi(c)
    m, s, hist = macd(c)
    df["macd"], df["macd_signal"], df["macd_hist"] = m, s, hist
    mid, up, lo = bollinger(c)
    df["bb_mid"], df["bb_up"], df["bb_low"] = mid, up, lo
    df["bb_pos"] = (c - lo) / (up - lo).replace(0, np.nan)
    sk, sd = stochastic(h, l, c)
    df["stoch_k"], df["stoch_d"] = sk, sd
    df["atr14"] = atr(h, l, c)
    df["atr_pct"] = df["atr14"] / c * 100
    df["obv"] = obv(c, v)
    df["vol_ma20"] = v.rolling(20).mean()
    df["vol_ratio"] = v / df["vol_ma20"].replace(0, np.nan)
    df["ret1"] = c.pct_change()
    # 고/저 돌파
    df["high20"] = h.rolling(20).max().shift(1)
    df["low20"] = l.rolling(20).min().shift(1)
    return df


def support_resistance(df: pd.DataFrame, lookback: int = 60) -> dict:
    win = df.tail(lookback)
    return {
        "recent_high": float(win["high"].max()),
        "recent_low": float(win["low"].min()),
        "high_date": str(win["high"].idxmax().date()),
        "low_date": str(win["low"].idxmin().date()),
    }


def analyze_technicals(df: pd.DataFrame) -> dict:
    """마지막 행 기준 기술적 상태 + 신호 리스트."""
    d = add_indicators(df)
    last = d.iloc[-1]
    prev = d.iloc[-2] if len(d) > 1 else last
    close = float(last["close"])

    def gt(a, b) -> bool:
        return bool(pd.notna(a) and pd.notna(b) and a > b)

    signals: list[dict] = []  # {name, direction(1/-1/0), desc}

    # 추세: 이평선 정배열/역배열
    bull_align = gt(last.get("ma5"), last.get("ma20")) and gt(last.get("ma20"), last.get("ma60"))
    bear_align = (not bull_align) and (last.get("ma5", 0) < last.get("ma20", 0) < last.get("ma60", 0))
    above60 = gt(close, last.get("ma60"))
    above20 = gt(close, last.get("ma20"))
    if bull_align and above20:
        signals.append({"name": "이평선 정배열", "direction": 1, "desc": f"MA5({last['ma5']:.0f})>MA20>MA60, 종가가 MA20 위에 위치"})
    elif bear_align:
        signals.append({"name": "이평선 역배열", "direction": -1, "desc": "MA5<MA20<MA60 하락 추세"})
    else:
        signals.append({"name": "이평선 혼조", "direction": 0, "desc": f"MA20={last.get('ma20', float('nan')):.0f}, MA60={last.get('ma60', float('nan')):.0f}"})

    # 골든/데드크로스 (최근 5일 내 교차, 자료가 짧으면 생략)
    cross = None
    for i in range(1, 6):
        if len(d) < i + 1:
            continue
        a_now, b_now = d["ma5"].iloc[-i], d["ma20"].iloc[-i]
        a_pr, b_pr = d["ma5"].iloc[-i - 1], d["ma20"].iloc[-i - 1]
        if pd.notna(a_now) and pd.notna(b_now) and pd.notna(a_pr) and pd.notna(b_pr):
            if a_pr <= b_pr and a_now > b_now:
                cross = ("골든크로스", 1, f"{i}일 전 MA5가 MA20 상향 돌파")
                break
            if a_pr >= b_pr and a_now < b_now:
                cross = ("데드크로스", -1, f"{i}일 전 MA5가 MA20 하향 이탈")
                break
    if cross:
        signals.append({"name": cross[0], "direction": cross[1], "desc": cross[2]})

    # RSI
    r = float(last["rsi14"])
    if r >= 70:
        signals.append({"name": "RSI 과매수", "direction": -1, "desc": f"RSI {r:.1f} — 단기 과열, 추격 매수 주의"})
    elif r >= 60:
        signals.append({"name": "RSI 강세", "direction": 1, "desc": f"RSI {r:.1f} — 매수 모멘텀 우위"})
    elif r <= 30:
        signals.append({"name": "RSI 과매도", "direction": 1, "desc": f"RSI {r:.1f} — 과매도, 기술적 반등 가능 (분할 접근)"})
    elif r <= 40:
        signals.append({"name": "RSI 약세", "direction": -1, "desc": f"RSI {r:.1f} — 매도 압력 우위"})
    else:
        signals.append({"name": "RSI 중립", "direction": 0, "desc": f"RSI {r:.1f}"})

    # MACD
    mh = float(last["macd_hist"]) if pd.notna(last["macd_hist"]) else 0.0
    mh_prev = float(prev["macd_hist"]) if pd.notna(prev["macd_hist"]) else 0.0
    if mh > 0 and mh_prev <= 0:
        signals.append({"name": "MACD 상향 전환", "direction": 1, "desc": "히스토그램 음→양 전환"})
    elif mh > 0:
        signals.append({"name": "MACD 양수 유지", "direction": 1, "desc": f"히스토그램 +{mh:.0f}"})
    elif mh < 0 and mh_prev >= 0:
        signals.append({"name": "MACD 하향 전환", "direction": -1, "desc": "히스토그램 양→음 전환"})
    else:
        signals.append({"name": "MACD 음수 유지", "direction": -1, "desc": f"히스토그램 {mh:.0f}"})

    # 볼린저
    bp = float(last["bb_pos"]) if pd.notna(last["bb_pos"]) else 0.5
    if bp >= 1:
        signals.append({"name": "볼린저 상단 돌파", "direction": 1, "desc": "밴드 상단 위 — 강한 돌파이나 과열 병존"})
    elif bp >= 0.8:
        signals.append({"name": "볼린저 상단 접근", "direction": 1, "desc": f"밴드 위치 {bp:.2f} — 상승 탄력"})
    elif bp <= 0:
        signals.append({"name": "볼린저 하단 이탈", "direction": -1, "desc": "밴드 하단 아래 — 침체, 반등 탐색"})
    elif bp <= 0.2:
        signals.append({"name": "볼린저 하단 접근", "direction": 0, "desc": f"밴드 위치 {bp:.2f} — 저점 탐색"})
    else:
        signals.append({"name": "볼린저 밴드 내", "direction": 0, "desc": f"밴드 위치 {bp:.2f}"})

    # 스토캐스틱
    k, dd = float(last["stoch_k"]), float(last["stoch_d"])
    if k > dd and prev["stoch_k"] <= prev["stoch_d"] and k < 30:
        signals.append({"name": "스토캐스틱 저점 골든", "direction": 1, "desc": f"%K {k:.1f} 저점 상향 교차"})
    elif k < dd and prev["stoch_k"] >= prev["stoch_d"] and k > 70:
        signals.append({"name": "스토캐스틱 고점 데드", "direction": -1, "desc": f"%K {k:.1f} 고점 하향 교차"})
    else:
        signals.append({"name": "스토캐스틱", "direction": 0, "desc": f"%K {k:.1f} / %D {dd:.1f}"})

    # 거래량
    vr = float(last["vol_ratio"]) if pd.notna(last["vol_ratio"]) else 1.0
    ret = float(last["ret1"]) if pd.notna(last["ret1"]) else 0.0
    if vr >= 2.0 and ret > 0:
        signals.append({"name": "거래량 급증+상승", "direction": 1, "desc": f"평소 대비 {vr:.1f}배, 수급 유입"})
    elif vr >= 2.0 and ret < 0:
        signals.append({"name": "거래량 급증+하락", "direction": -1, "desc": f"평소 대비 {vr:.1f}배, 투매 가능성"})
    elif vr <= 0.5:
        signals.append({"name": "거래량 침체", "direction": 0, "desc": f"평소 대비 {vr:.1f}배 — 관망"})
    else:
        signals.append({"name": "거래량 정상", "direction": 0, "desc": f"평소 대비 {vr:.1f}배"})

    # OBV 추세 (20일 기울기)
    obv_slope = float(d["obv"].iloc[-1] - d["obv"].iloc[-21]) if len(d) > 21 else 0.0
    signals.append(
        {"name": "OBV 누적 추세", "direction": 1 if obv_slope > 0 else (-1 if obv_slope < 0 else 0),
         "desc": "20일간 매집 우위" if obv_slope > 0 else ("20일간 분산 우위" if obv_slope < 0 else "OBV 횡보")}
    )

    # 신고가/신저가
    if close >= float(d["high20"].iloc[-1] or 0):
        signals.append({"name": "20일 신고가", "direction": 1, "desc": "20일 최고가 돌파 — 추세 추종 관점 긍정"})
    elif close <= float(d["low20"].iloc[-1] or 0):
        signals.append({"name": "20일 신저가", "direction": -1, "desc": "20일 최저가 이탈 — 낙폭 과대 여부 확인 필요"})

    score = sum(s["direction"] for s in signals)
    if score >= 4:
        trend = "강한 상승 흐름"
    elif score >= 2:
        trend = "상승 흐름"
    elif score >= -1:
        trend = "횡보 / 방향 탐색"
    elif score >= -3:
        trend = "하락 흐름"
    else:
        trend = "강한 하락 흐름"

    sr = support_resistance(df)
    atr_pct = float(last["atr_pct"]) if pd.notna(last["atr_pct"]) else None

    return {
        "df": d,
        "last_close": close,
        "signals": signals,
        "signal_score": score,
        "trend": trend,
        "above_ma20": above20,
        "above_ma60": above60,
        "rsi": r,
        "vol_ratio": vr,
        "atr_pct": atr_pct,
        "support_resistance": sr,
    }
