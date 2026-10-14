"""매집 분석 + 살 가격/팔 가격/손절 가격 + 대응 결론. 쉬운 말 고정."""

from __future__ import annotations

import pandas as pd


def accumulation_status(tech: dict) -> dict:
    d = tech["df"]
    last = d.iloc[-1]
    reasons: list[str] = []
    score = 50.0
    if len(d) > 21:
        obv_up = float(d["obv"].iloc[-1] - d["obv"].iloc[-21]) > 0
    else:
        obv_up = False
    if obv_up:
        score += 20
        reasons.append("거래량 누적이 20일째 늘고 있어 누군가 조용히 모으는 중입니다")
    else:
        score -= 20
        reasons.append("거래량 누적이 줄고 있어 가진 주식을 파는 중일 수 있습니다")
    vr = float(tech.get("vol_ratio") or 1.0)
    if vr >= 1.5:
        score += 10
        reasons.append(f"거래량이 평소의 {vr:.1f}배로 시장의 관심을 받고 있습니다")
    elif vr <= 0.6:
        score -= 5
        reasons.append("거래가 말라 있어 관심이 식은 상태입니다")
    ma60 = last.get("ma60")
    close = float(tech["last_close"])
    if pd.notna(ma60) and ma60:
        if close >= float(ma60):
            score += 10
            reasons.append("주가가 60일 평균 위에 있어 힘이 있습니다")
        else:
            score -= 10
            reasons.append("주가가 60일 평균 아래에 있어 힘이 약합니다")
    rsi = float(tech.get("rsi") or 50)
    if rsi <= 35:
        score += 5
        reasons.append("많이 떨어져서 싸게 모으기 좋은 자리일 수 있습니다")
    score = max(0.0, min(100.0, score))
    if score >= 70:
        label = "세력이 모으는 중"
    elif score >= 50:
        label = "조용히 지켜보는 중"
    elif score >= 30:
        label = "관심이 식는 중"
    else:
        label = "빠져나가는 중"
    return {"score": round(score, 1), "label": label, "reasons": reasons[:4]}


def volume_regime(tech: dict) -> dict:
    d = tech["df"]
    win = d.tail(10)
    if "vol_ratio" not in win.columns or len(win) < 5:
        return {"surge": False}
    idx = win["vol_ratio"].idxmax()
    row = win.loc[idx]
    vr = float(row["vol_ratio"]) if pd.notna(row["vol_ratio"]) else 1.0
    if vr < 2.0:
        return {"surge": False, "vr": round(vr, 2)}
    return {
        "surge": True,
        "vr": round(vr, 2),
        "date": pd.to_datetime(idx).strftime("%m월 %d일"),
        "close": float(row["close"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
    }


def price_levels(tech: dict) -> dict:
    close = float(tech["last_close"])
    sr = tech["support_resistance"]
    d = tech["df"]
    last = d.iloc[-1]
    reg = volume_regime(tech)
    low10 = float(d["low"].tail(10).min())
    high10 = float(d["high"].tail(10).max())
    atr_pct_top = float(last.get("atr_pct")) if pd.notna(last.get("atr_pct")) else 2.0
    atr_won = close * atr_pct_top / 100
    if reg.get("surge"):
        sdate = reg["date"]
        buy = round(min(reg["low"], low10))
        t1 = round(reg["high"])
        t2 = round(max(high10, reg["high"]))
        if close > t1:
            t1 = round(close + atr_won)
            t1why = "뚫고 올라와서 새로 잡은 1차 목표예요."
            t2 = round(close + atr_won * 2)
            why2 = "더 오르면 노리는 2차 목표예요. 욕심내지 말고 나눠 파세요."
            buy = round(min(reg["low"], low10))
            buy_why = "지금 새로 살 자리는 아니에요. 여기로 밀리면 그때 다시 보세요."
            stop = round(reg["high"] * 0.97)
            stop_why = "뚫고 올라온 자리(터진 날 고점)를 깨면 실패이니 파세요."
            buy_agg = round(close)
            buy_agg_why = "이미 오른 자리에서 따라붙는 가격이라 위험이 큽니다. 소액만 하세요."
            stop_agg = round(close * 0.98)
            stop_agg_why = "오늘 산 가격에서 2%만 빠져도 파세요."
        elif t2 <= t1:
            t1why = "터진 날 고점이 1차 목표예요. 여기를 뚫으면 더 갑니다."
            t2 = round(t1 * 1.03)
            why2 = f"터진 날 고점({t1:,.0f}원)을 뚫고 더 오르면 노리는 가격이에요."
        else:
            t1why = "터진 날 고점이 1차 목표예요. 여기를 뚫으면 더 갑니다."
            why2 = "최근 10일 가장 비쌌던 가격이에요. 여기 오면 나머지도 파세요."
        buy_why = f"거래가 터진 날의 가장 쌌던 가격 근처예요. 여기로 밀리면 단기로 사는 자리입니다."
        stop_why = "터진 날 저점 밑으로 떨어지면 단기 실패이니 바로 파세요."
        buy_agg = round(reg["close"])
        buy_agg_why = "불이 붙은 자리에서 따라사는 가격이에요. 돈의 절반 이하만 쓰세요."
        stop_agg = round(reg["close"] * 0.97)
        stop_agg_why = "따라붙는 자리는 3%만 밀려도 바로 파세요."
        if close <= t1:
            stop = round(min(reg["low"], low10) * 0.98)
        return {
            "mode": "단기",
            "mode_why": f"거래량이 평소의 {reg['vr']}배로 터져 단기 기준으로 잡았습니다.",
            "buy_zone": buy,
            "buy_why": buy_why,
            "buy_agg": buy_agg,
            "buy_agg_why": buy_agg_why,
            "stop_agg": stop_agg,
            "stop_agg_why": stop_agg_why,
            "target1": t1,
            "target1_why": t1why,
            "target2": t2,
            "target2_why": why2,
            "stop": stop,
            "stop_why": stop_why,
        }
    ma5 = float(last.get("ma5")) if pd.notna(last.get("ma5")) else None
    ma20 = float(last.get("ma20")) if pd.notna(last.get("ma20")) else None
    ma60 = float(last.get("ma60")) if pd.notna(last.get("ma60")) else None
    low = float(sr["recent_low"])
    high = float(sr["recent_high"])
    bb_up = float(last.get("bb_up")) if pd.notna(last.get("bb_up")) else None

    cands = [x for x in [ma20, ma60] if x]
    buy_zone = min(cands) if cands else close
    if buy_zone > close:
        buy_zone = close

    target1 = round(high)
    t2raw = max(high, bb_up) if bb_up else high
    if round(t2raw) <= target1:
        target2 = round(high * 1.05)
        why2 = "1차 목표를 뚫고 더 오르면 노리는 가격이에요."
    else:
        target2 = round(t2raw)
        why2 = "주가가 다니는 통로 윗쪽까지 간 가격이에요. 여기 오면 나머지도 파세요."

    atr_pct = float(last.get("atr_pct")) if pd.notna(last.get("atr_pct")) else 2.0
    stop = round(min(low * 0.97, close - close * atr_pct / 100 * 1.5))

    return {
        "mode": "중기",
        "mode_why": "거래량이 평소 수준이라 60일 큰 그림 기준으로 잡았습니다.",
        "buy_zone": round(buy_zone),
        "buy_why": "평균선 근처라 쌀 때 사는 자리입니다. 이 가격 아래로 내려오면 2~3번 나눠 사세요.",
        "buy_agg": round(ma5) if ma5 else round(close),
        "buy_agg_why": "단기 평균선 자리에서 바로 사는 공격 가격이에요. 떨어지면 바로 파세요.",
        "stop_agg": round((ma5 if ma5 else close) * 0.97),
        "stop_agg_why": "공격 매수는 3% 룰. 미련 두지 말고 파세요.",
        "target1": target1,
        "target1_why": f"최근 60일 가장 비쌌던 가격이라 여기서 막힐 수 있어요. 절반은 여기서 파세요.",
        "target2": target2,
        "target2_why": why2,
        "stop": stop,
        "stop_why": "여기까지 떨어지면 생각이 틀린 것이니 파세요.",
    }


def decide_action(total: float, acc_score: float, close: float = 0, target1: float = 0, rsi: float = 50) -> tuple[str, str]:
    if close and target1 and close >= target1:
        return ("지금 사면 늦었어요", "새로 사지 마세요. 갖고 있으면 절반 팔고 눌리면 다시 사세요.")
    if rsi >= 75:
        return ("너무 뜨거워진 자리예요", "새로 사지 말고 눌릴 때까지 기다리세요.")
    if total >= 65 and acc_score >= 50:
        return ("지금 사도 되는 자리예요", "한 번에 다 사지 말고 2~3번에 나눠 사세요.")
    if total >= 55:
        return ("바로 사기보다 눌릴 때 사세요", "살 가격 아래로 내려오면 1차 매수하세요.")
    if total >= 45:
        return ("방향이 정해질 때까지 기다리세요", "이미 갖고 있으면 들고 있고, 없으면 사지 마세요.")
    return ("지금은 사지 마세요", "가지고 있으면 손절 가격을 정해 놓고 파는 것을 검토하세요.")


def action_guide(total: float) -> str:
    if total >= 80:
        return "조건이 아주 좋아요. 그래도 2~3번 나눠 사세요."
    if total >= 65:
        return "살 만한 자리예요. 조금 떨어질 때 사면 더 좋습니다."
    if total >= 50:
        return "좋은 점 나쁜 점 반반이에요. 사지 말고 기다리세요."
    if total >= 35:
        return "지금 사면 위험해요. 오르는 신호가 나올 때까지 기다리세요."
    return "쉬세요. 떨어지는 주식을 잡지 마세요."


def adjust_for_session(action, action_easy, intra, px):
    s = int(intra.get("session_score", 0))
    close = float(intra.get("close") or 0)
    t1 = float(px.get("target1") or 0)
    if close and t1 and close >= t1:
        if s < 0:
            return ("올랐지만 오늘 힘이 빠졌어요", "내일 시초에 절반 팔고 나머지는 손절가까지 들고 가세요.")
        return ("뚫고 기세 좋게 마감했어요", "들고 가되 손절가를 터진 날 저점으로 올리세요. 새로 사지는 마세요.")
    if s <= -2:
        return ("오늘 장이 약했어요", "내일 아침 바로 사지 말고 오전 흐름을 보고 사세요.")
    if s >= 2 and action.startswith("지금 사도"):
        return (action, action_easy + " 오늘 마감도 강했으니 눌리면 과감히 사세요.")
    return (action, action_easy)


def build_strategy(tech: dict, quant: dict, macro: dict, expect: dict, intra: dict | None = None) -> dict:
    acc = accumulation_status(tech)
    px = price_levels(tech)
    action, action_easy = decide_action(float(quant["total"]), float(acc["score"]), float(tech["last_close"]), float(px["target1"]), float(tech.get("rsi") or 50))
    if intra and px.get("mode") == "단기":
        action, action_easy = adjust_for_session(action, action_easy, intra, px)
    return {"accumulation": acc, "prices": px, "mode": px["mode"], "mode_why": px["mode_why"], "action": action, "action_easy": action_easy, "intra": intra}
