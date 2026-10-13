"""기업 자체 기대감: 뉴스/공시 키워드 기반 규칙 분석 (LLM 키 불필요)."""

from __future__ import annotations

from collections import Counter
import re

POS_WORDS = [
    "흑자", "실적", "호실적", "어닝서프", "서프라이즈", "수주", "계약", "공급",
    "상향", "목표가상향", "돌파", "최대", "신고가", "성장", "확대", "승인",
    "허가", "출시", "신제품", "신약", "임상", "통과", "투자유치", "유치",
    "배당", "자사주", "매입", "소각", "인수", "합병", "제휴", "협력",
    "수혜", "기대", "회복", "개선", "증가", "급증", "상승", "강세",
    "추천", "매수", "비중확대", "아웃퍼폼",
]

NEG_WORDS = [
    "적자", "어닝쇼크", "쇼크", "하향", "목표가하향", "매도", "비중축소",
    "하락", "급락", "폭락", "우려", "경고", "리스크", "횡령", "배임",
    "감자", "유상증자", "전환사채", "CB", "BW", "매각", "매물",
    "과징금", "제재", "소송", "기소", "조사", "감사", "의견거절",
    "관리종목", "거래정지", "감사의견", "부도", "파산", "구조조정",
    "감원", "공장중단", "리콜", "화재", "사고", "감소", "둔화", "부진",
]

STOPWORDS = {"속보", "단독", "종합", "특징주"}


def _score_title(title: str) -> int:
    s = 0
    for w in POS_WORDS:
        if w in title:
            s += 1
    for w in NEG_WORDS:
        if w in title:
            s -= 1
    # 강한 표현 가중
    for w in ["어닝서프라이즈", "신고가", "상한가", "자사주소각", "어닝쇼크", "거래정지", "의견거절"]:
        if w in title:
            s += 1 if w in ["어닝서프라이즈", "신고가", "상한가", "자사주소각"] else -1
    return s


def analyze_expectation(news: list[dict], disclosures: list[dict]) -> dict:
    scored = []
    for n in news or []:
        t = n.get("title", "")
        scored.append({**n, "score": _score_title(t)})
    pos = [s for s in scored if s["score"] > 0]
    neg = [s for s in scored if s["score"] < 0]
    neu = [s for s in scored if s["score"] == 0]

    total = len(scored)
    if total == 0:
        exp_score, exp_label = 50.0, "뉴스 부족 — 중립"
    else:
        raw = sum(s["score"] for s in scored) / total  # -2~+2 범위 대개
        exp_score = max(0.0, min(100.0, 50 + raw * 25))
        if exp_score >= 70:
            exp_label = "긍정 기대감 우세"
        elif exp_score >= 55:
            exp_label = "완만한 긍정"
        elif exp_score >= 45:
            exp_label = "혼조·중립"
        elif exp_score >= 30:
            exp_label = "완만한 부정"
        else:
            exp_label = "부정 이슈 우세 — 주의"

    # 키워드 추출 (2글자 이상 한글/영문 토큰 상위)
    toks: Counter = Counter()
    for s in scored:
        for tok in re.findall(r"[가-힣A-Za-z]{2,}", s.get("title", "")):
            if len(tok) >= 2 and tok not in ("속보", "단독", "종합", "특징주"):
                toks[tok] += 1
    top_kw = [{"word": w, "count": c} for w, c in toks.most_common(12)]

    # 공시에서 주의 키워드
    watch = []
    for d in disclosures or []:
        t = d.get("title", "")
        if any(k in t for k in ["유상증자", "전환사채", "감자", "거래정지", "감사의견", "횡령", "배임", "합병", "분할", "자사주", "배당"]):
            watch.append(d)

    return {
        "score": round(exp_score, 1),
        "label": exp_label,
        "counts": {"total": total, "pos": len(pos), "neg": len(neg), "neu": len(neu)},
        "pos_news": sorted(pos, key=lambda x: -x["score"])[:5],
        "neg_news": sorted(neg, key=lambda x: x["score"])[:5],
        "top_keywords": top_kw,
        "watch_disclosures": watch[:5],
        "all_news": scored[:30],
    }
