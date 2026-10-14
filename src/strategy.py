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


def price_levels(tech: dict) -> dict:
    close = float(tech["last_close"])
    sr = tech["support_resistance"]
    d = tech["df"].iloc[-1]
    ma20 = float(d.get("ma20")) if pd.notna(d.get("ma20")) else None
    ma60 = float(d.get("ma60")) if pd.notna(d.get("ma60")) else None
    low = float(sr["recent_low"])
    high = float(sr["recent_high"])
    bb_up = float(d.get("bb_up")) if pd.notna(d.get("bb_up")) else None

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

    atr_pct = float(d.get("atr_pct")) if pd.notna(d.get("atr_pct")) else 2.0
    stop = round(min(low * 0.97, close - close * atr_pct / 100 * 1.5))

    return {
        "buy_zone": round(buy_zone),
        "buy_why": "평균선 근처라 쌀 때 사는 자리입니다. 이 가격 아래로 내려오면 2~3번 나눠 사세요.",
        "target1": target1,
        "target1_why": f"최근 60일 가장 비쌌던 가격이라 여기서 막힐 수 있어요. 절반은 여기서 파세요.",
        "target2": target2,
        "target2_why": why2,
        "stop": stop,
    }


def decide_action(total: float, acc_score: float) -> tuple[str, str]:
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


def build_strategy(tech: dict, quant: dict, macro: dict, expect: dict) -> dict:
    acc = accumulation_status(tech)
    px = price_levels(tech)
    action, action_easy = decide_action(float(quant["total"]), float(acc["score"]))
    return {"accumulation": acc, "prices": px, "action": action, "action_easy": action_easy}
