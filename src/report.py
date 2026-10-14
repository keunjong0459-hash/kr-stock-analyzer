"""종합 리포트 생성 (한글 마크다운)."""

from __future__ import annotations

from src.explain import GRADE_EASY, MACRO_EASY


def build_report(company: dict, tech: dict, quant: dict, macro: dict, expect: dict, fund: dict) -> str:
    c = tech["last_close"]
    sr = tech["support_resistance"]
    L = []
    L.append(f"# {company['Name']} ({company['Code']}) 종합 분석")
    L.append("")
    L.append(f"- 현재가: {c:,.0f}원 / 기술적 흐름: **{tech['trend']}** (신호점수 {tech['signal_score']:+d})")
    L.append(f"- 퀀트 종합: **{quant['total']}점 · {quant['grade']}등급 · 상승여력 {quant['upside']}** (참고 확률 {quant['up_prob']}%)")
    L.append(f"- 시장 국면: **{macro['regime']}** (호재 {len(macro['bullish'])} / 악재 {len(macro['bearish'])})")
    L.append(f"- 기업 기대감: **{expect['label']} ({expect['score']}점)** — 뉴스 {expect['counts']['total']}건(긍정 {expect['counts']['pos']}/부정 {expect['counts']['neg']})")
    if fund.get("per") or fund.get("pbr"):
        L.append(f"- 밸류: PER {fund.get('per','-')} / PBR {fund.get('pbr','-')} / ROE {fund.get('roe','-')}% / 시총 {fund.get('marketcap','-')}")
    L.append("")
    L.append("## 0) 30초 요약 (쉬운 말로)")
    L.append(f"- 지금 흐름: {tech['trend']} (신호 {tech['signal_score']:+d}점)")
    L.append(f"- 성적표: {quant['total']}점 {quant['grade']}등급")
    L.append(f"- 시장 날씨: {macro['regime']}")
    L.append(f"- 회사 소식: {expect['label']} ({expect['score']}점)")
    L.append("")
    L.append("## 1) 기술적 분석 흐름")
    for s in tech["signals"]:
        arrow = "▲" if s["direction"] > 0 else ("▼" if s["direction"] < 0 else "■")
        L.append(f"- {arrow} **{s['name']}**: {s['desc']}")
    L.append(f"- RSI(14): {tech['rsi']:.1f} / 거래량 비율: {tech['vol_ratio']:.2f}배")
    if tech["atr_pct"]:
        L.append(f"- ATR(14): {tech['atr_pct']:.2f}% — 하루 평균 변동폭 참고 (손절·분할매수 간격용)")
    L.append(f"- 최근 60일 고점 {sr['recent_high']:,.0f}원({sr['high_date']}) / 저점 {sr['recent_low']:,.0f}원({sr['low_date']})")
    L.append("")
    L.append("## 2) 퀀트 관점 (상승 가능성)")
    for k, v in quant["parts"].items():
        L.append(f"- {k}: {v}점")
    d = quant["details"]
    L.append(f"- 수익률: 1M {d['returns_pct'].get('1M')}% / 3M {d['returns_pct'].get('3M')}% / 6M {d['returns_pct'].get('6M')}%")
    L.append(f"- 이평 괴리율: {d.get('ma_gap_pct')} / 변동성: {d.get('ann_vol_pct')}% · MDD {d.get('mdd_pct')}%")
    L.append(f"- RSI 코멘트: {d.get('rsi_note')}")
    L.append("")
    L.append("## 3) 지수 + 매크로 (호재/악재)")
    L.append(f"### 국면: {macro['regime']}")
    L.append("#### 호재")
    L += [f"- {b}" for b in macro["bullish"]] or ["- 없음"]
    L.append("#### 악재")
    L += [f"- {b}" for b in macro["bearish"]] or ["- 없음"]
    L.append("#### 중립")
    L += [f"- {n}" for n in macro["neutral"]] or ["- 없음"]
    L.append("")
    L.append("## 4) 기업 자체 기대감")
    L.append(f"- 종합: {expect['label']} ({expect['score']}점)")
    if expect["top_keywords"]:
        kw = ", ".join(f"{k['word']}({k['count']})" for k in expect["top_keywords"][:8])
        L.append(f"- 핵심 키워드: {kw}")
    if expect["pos_news"]:
        L.append("- 긍정 뉴스:")
        for n in expect["pos_news"]:
            L.append(f"  - {n['title']} ({n.get('date','')}, {n.get('source','')})")
    if expect["neg_news"]:
        L.append("- 부정 뉴스:")
        for n in expect["neg_news"]:
            L.append(f"  - {n['title']} ({n.get('date','')}, {n.get('source','')})")
    if expect["watch_disclosures"]:
        L.append("- 주목 공시:")
        for dc in expect["watch_disclosures"]:
            L.append(f"  - {dc['title']} ({dc.get('date','')})")
    L.append("")
    L.append("## 5) 종합 판단 (자동 생성, 투자 조언 아님)")
    L.append(judgment_text(tech, quant, macro, expect))
    L.append("")
    L.append("> 본 리포트는 무료 공개 데이터 기반 규칙 분석이며 투자 권유가 아닙니다. "
             "실제 매매 전 사업보고서·공시를 직접 확인하세요.")
    return "\n".join(L)


def judgment_text(tech: dict, quant: dict, macro: dict, expect: dict) -> str:
    ups = []
    downs = []
    if tech["signal_score"] >= 2:
        ups.append("기술적 흐름이 상승 쪽에 기울어 있음")
    elif tech["signal_score"] <= -2:
        downs.append("기술적 흐름이 하락 쪽에 기울어 있음")
    else:
        downs.append("기술적으로 방향 탐색 중 (돌파/이탈 확인 필요)")
    if quant["total"] >= 65:
        ups.append(f"퀀트 점수 {quant['total']}점({quant['grade']})으로 상승 여력 양호")
    elif quant["total"] < 45:
        downs.append(f"퀀트 점수 {quant['total']}점({quant['grade']})으로 모멘텀·수급 약함")
    if macro["direction"] > 0:
        ups.append(f"시장 국면 '{macro['regime']}'으로 베타 환경 우호적")
    elif macro["direction"] < 0:
        downs.append(f"시장 국면 '{macro['regime']}'으로 지수 역풍 가능")
    if expect["score"] >= 55:
        ups.append(f"기업 기대감 '{expect['label']}' — 긍정 뉴스 우세")
    elif expect["score"] < 45:
        downs.append(f"기업 기대감 '{expect['label']}' — 부정 이슈 점검 필요")

    if len(ups) >= 3 and not downs:
        verdict = "기술·퀀트·매크로·기대감이 모두 우호적인 구간입니다. 다만 과열 지표(RSI·볼린저·거래량)를 확인해 분할 접근을 권장합니다."
    elif len(ups) >= 2 and len(downs) <= 1:
        verdict = "부분적으로 우호적이나 확인이 필요한 구간입니다. 지지선·거래량을 보며 추격보다 눌림·돌파 확인 전략이 적합합니다."
    elif len(downs) >= 2:
        verdict = "하방 압력이 우세한 구간입니다. 신규 진입보다 반전 신호(MACD 전환·RSI 회복·거래량 동반 상승) 확인 후 접근을 권장합니다."
    else:
        verdict = "방향성이 뚜렷하지 않은 혼조 구간입니다. 지수 방향과 기업 이벤트(실적·공시)를 확인하며 비중을 조절하세요."
    bullets = ["- 상승 요인: " + (" / ".join(ups) if ups else "뚜렷하지 않음"),
               "- 하락·경계 요인: " + (" / ".join(downs) if downs else "뚜렷하지 않음"),
               f"- 한 줄 판단: {verdict}"]
    return "\n".join(bullets)
