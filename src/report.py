"""종합 리포트 생성. 결론 우선 + 100점 만점 성적표 + 쉬운 말 고정."""

from __future__ import annotations

from src.explain import GRADE_EASY, MACRO_EASY, QUANT_EASY, SIGNAL_EASY
from src.strategy import action_guide, build_strategy


def build_report(company: dict, tech: dict, quant: dict, macro: dict,
                 expect: dict, fund: dict, strategy: dict | None = None) -> str:
    if strategy is None:
        strategy = build_strategy(tech, quant, macro, expect)
    acc = strategy["accumulation"]
    px = strategy["prices"]
    L = []
    L.append(f"# {company['Name']} ({company['Code']}) 분석 — 결론부터 봅니다")
    L.append("")
    L.append(f"## 결론: {strategy['action']}")
    L.append(f"**{strategy['action_easy']}**")
    L.append("")
    L.append(f"- 성적표: **{quant['total']}점 (100점 만점)** · {quant['grade']}등급")
    L.append(f"- 대응법: {action_guide(quant['total'])}")
    L.append(f"- 살 가격: **{px['buy_zone']:,.0f}원 아래** / 파는 목표: **{px['target1']:,.0f}원** / 손절: **{px['stop']:,.0f}원 깨지면 팔기**")
    L.append("")
    L.append("## 성적표 자세히 (100점 만점)")
    L.append("100점에 가까울수록 오를 조건이 잘 갖춰졌다는 뜻입니다.")
    for k, v in quant["parts"].items():
        label, desc = QUANT_EASY.get(k, (k, ""))
        L.append(f"- {label}: {v}점 — {desc}")
    d = quant["details"]
    L.append(f"- 최근 성적: 1개월 {d['returns_pct'].get('1M')}% / 3개월 {d['returns_pct'].get('3M')}% / 6개월 {d['returns_pct'].get('6M')}%")
    L.append(f"- {quant['grade']}등급 대응법: {GRADE_EASY.get(quant['grade'], '')}")
    if fund.get("per") or fund.get("pbr"):
        L.append(f"- 참고: PER {fund.get('per', '-')} / PBR {fund.get('pbr', '-')} (낮을수록 쌀수록 좋음)")
    L.append("")
    L.append("## 세력이 모으는 중인가요?")
    L.append(f"- 판단: **{acc['label']} ({acc['score']}점)**")
    for r in acc["reasons"]:
        L.append(f"  - {r}")
    L.append("")
    intra = strategy.get("intra")
    if intra:
        L.append("## 오늘 장 흐름 (5분봉으로 본 하루)")
        for line in intra.get("lines", []):
            L.append("- " + line)
        L.append("- 한 줄 판단: " + intra.get("verdict", ""))
        L.append("")
    L.append("## 살 가격·팔 가격·손절 가격 (왜 이 가격인가요?)")
    L.append(f"- 기준: **{px['mode']}**")
    L.append(f"- 살 가격 {px['buy_zone']:,.0f}원 아래: {px['buy_why']}")
    L.append(f"- 1차 목표 {px['target1']:,.0f}원: {px['target1_why']}")
    L.append(f"- 2차 목표 {px['target2']:,.0f}원: {px['target2_why']}")
    L.append(f"- 손절 {px['stop']:,.0f}원: {px['stop_why']}")
    L.append("")
    L.append("## 시장 날씨 (좋은 일·나쁜 일)")
    L.append(f"### 날씨: {macro['regime']} — {MACRO_EASY.get(macro['direction'], '')}")
    L.append("#### 좋은 일(호재)")
    L += [f"- {b}" for b in macro["bullish"]] or ["- 없음"]
    L.append("#### 나쁜 일(악재)")
    L += [f"- {b}" for b in macro["bearish"]] or ["- 없음"]
    L.append("")
    L.append("## 회사 소식")
    L.append(f"- 종합: {expect['label']} ({expect['score']}점)")
    if expect["top_keywords"]:
        kw = ", ".join(f"{k['word']}({k['count']})" for k in expect["top_keywords"][:8])
        L.append(f"- 자주 나온 말: {kw}")
    if expect["pos_news"]:
        L.append("- 좋은 소식:")
        for n in expect["pos_news"]:
            L.append(f"  - {n['title']} ({n.get('date', '')}, {n.get('source', '')})")
    if expect["neg_news"]:
        L.append("- 나쁜 소식:")
        for n in expect["neg_news"]:
            L.append(f"  - {n['title']} ({n.get('date', '')}, {n.get('source', '')})")
    if expect["watch_disclosures"]:
        L.append("- 챙겨볼 공시:")
        for dc in expect["watch_disclosures"]:
            L.append(f"  - {dc['title']} ({dc.get('date', '')})")
    L.append("")
    L.append("## 지표 자세히 (궁금할 때만 보세요)")
    for s in tech["signals"]:
        arrow = "▲" if s["direction"] > 0 else ("▼" if s["direction"] < 0 else "■")
        L.append(f"- {arrow} **{s['name']}**: {s['desc']}")
        easy = SIGNAL_EASY.get(s["name"], "")
        if easy:
            L.append(f"  - 쉽게: {easy}")
    sr = tech["support_resistance"]
    L.append(f"- 최근 60일 비쌌던 가격 {sr['recent_high']:,.0f}원 / 쌌던 가격 {sr['recent_low']:,.0f}원")
    L.append("")
    L.append("> 이 분석은 무료 공개 자료로 만든 참고용이며 투자를 권하는 게 아닙니다.")
    return "\n".join(L)
