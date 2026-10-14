"""한국 주식 기술적+퀀트+매크로+기대감 분석 대시보드 (Streamlit, 무료 데이터만)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.universe import load_universe, resolve_company, suggest_names  # noqa: E402
from src.data import (  # noqa: E402
    get_price, get_macro_bundle, get_fundamentals, get_naver_news, get_dart_disclosures,
)
from src.technicals import analyze_technicals  # noqa: E402
from src.quant import quant_total  # noqa: E402
from src.market import judge_macro  # noqa: E402
from src.sentiment import analyze_expectation  # noqa: E402
from src.report import build_report  # noqa: E402
from src.strategy import build_strategy  # noqa: E402
from src.intraday import get_intraday, analyze_session  # noqa: E402
from src.news import get_company_news, get_sector_news  # noqa: E402
from src.sector import get_sector_info  # noqa: E402
from src.explain import GLOSSARY, SIGNAL_EASY, QUANT_EASY, GRADE_EASY  # noqa: E402

st.set_page_config(page_title="한국 주식 종합 분석", page_icon="📈", layout="wide")
st.title("📈 한국 주식 종합 분석 — 기술적 + 퀀트 + 지수/매크로 + 기업 기대감")
st.caption("기업명을 입력하면 무료 데이터(주가·지수·네이버 금융)로 자동 분석합니다. 투자 권유가 아닙니다.")

# ---------- 유니버스 ----------
@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _universe():
    return load_universe()

try:
    universe = _universe()
except Exception as e:
    st.error(f"종목 목록 로드 실패: {e}")
    st.stop()

# ---------- 사이드바 ----------
with st.sidebar:
    st.header("🔎 종목 검색")
    q = st.text_input("기업명 입력", value="삼성전자", placeholder="예: 삼성전자, SK하이닉스, 에코프로")
    cands = suggest_names(q, universe)
    pick = st.selectbox("후보", cands, index=0 if cands else None)
    query = pick or q
    years = st.slider("차트 기간(년)", 1, 3, 2)
    news_pages = st.slider("뉴스 수집 페이지", 1, 5, 2)
    go = st.button("분석 실행", type="primary", use_container_width=True)
    easy_mode = st.checkbox("초보자 쉬운 설명 보기", value=True)
    st.caption("종목 DB " + str(len(universe)) + "개")

if not go:
    st.info("왼쪽에서 기업명을 입력하고 **분석 실행**을 눌러주세요.")
    st.dataframe(universe.head(20), use_container_width=True)
    st.stop()

company = resolve_company(query, universe)
if not company:
    st.error(f"'{query}'와 일치하는 종목을 찾지 못했습니다. 철자를 확인해주세요.")
    st.stop()

st.subheader(f"{company['Name']} ({company['Code']}) · {company['Market']}")

# ---------- 데이터 수집 ----------
with st.spinner("주가·지수·뉴스 수집 중..."):
    try:
        price = get_price(company["Code"], company["Market"], years=years)
    except Exception as e:
        st.error(f"주가 조회 실패: {e}")
        st.stop()
    macro_bundle = get_macro_bundle()
    fund = get_fundamentals(company["Code"])
    gnews = get_company_news(company["Name"], max_items=20)
    nnews = get_naver_news(company["Code"], pages=news_pages)
    seen_titles, news = set(), []
    for n in gnews + nnews:
        if n["title"] not in seen_titles:
            seen_titles.add(n["title"])
            news.append(n)
    discs = get_dart_disclosures(company["Code"])
    sector = get_sector_info(company["Code"])
    sector_news = get_sector_news(sector["industry"], 8) if sector and sector.get("industry") else []

tech = analyze_technicals(price)
quant = quant_total(tech["df"], fund)
macro = judge_macro(macro_bundle)
expect = analyze_expectation(news, discs)
strategy = build_strategy(tech, quant, macro, expect)
try:
    _idf = get_intraday(company["Code"], company["Market"])
    intra = analyze_session(_idf)
except Exception:
    intra = None
if intra:
    strategy = build_strategy(tech, quant, macro, expect, intra)
try:
    report_md = build_report(company, tech, quant, macro, expect, fund, strategy)
except TypeError:
    report_md = build_report(company, tech, quant, macro, expect, fund)

# ---------- 상단 요약 카드 ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("현재가", f"{tech['last_close']:,.0f}원", f"RSI {tech['rsi']:.1f}")
c2.metric("기술적 흐름", tech["trend"], f"신호 {tech['signal_score']:+d}")
c3.metric("성적표(100점 만점)", f"{quant['total']}점 · {quant['grade']}", quant["upside"])
c4.metric("시장 국면", macro["regime"], f"기대감 {expect['label']}")

st.success("결론: " + strategy["action"] + " — " + strategy["action_easy"] + " [" + strategy["mode"] + " 기준]")
s1, s2, s3 = st.columns(3)
s1.metric("살 가격", f"{strategy['prices']['buy_zone']:,.0f}원 아래")
s2.metric("파는 목표", f"{strategy['prices']['target1']:,.0f}원")
s3.metric("손절 가격", f"{strategy['prices']['stop']:,.0f}원")
if intra:
    with st.expander("오늘 장 흐름 (5분봉)", expanded=True):
        for line in intra.get("lines", []):
            st.write("- " + line)
        st.write("**한 줄 판단: " + intra.get("verdict", "") + "**")
        try:
            import plotly.graph_objects as go
            f = intra["frame"]
            lo = float(f["low"].min())
            hi = float(f["high"].max())
            pad = max((hi - lo) * 0.1, hi * 0.001)
            fig = go.Figure(data=[go.Candlestick(x=f.index, open=f["open"], high=f["high"], low=f["low"], close=f["close"], name="5분봉")])
            fig.update_layout(height=380, xaxis_rangeslider_visible=False, yaxis=dict(range=[lo - pad, hi + pad]), margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.line_chart(intra["frame"][["close"]])

tab_all, tab_tech, tab_quant, tab_macro, tab_news, tab_theme, tab_raw = st.tabs(
    ["종합 리포트", "기술적 분석", "퀀트 점수", "지수·매크로", "기업 기대감", "산업·테마", "원본 데이터"]
)

with tab_all:
    st.markdown(report_md)
    st.download_button("리포트 다운로드 (.md)", report_md, file_name=f"{company['Name']}_분석.md")
    if easy_mode:
        with st.expander("어려운 용어 쉽게 보기"):
            for k, v in GLOSSARY.items():
                st.write(f"- **{k}**: {v}")

with tab_tech:
    st.write("#### 신호 목록")
    sig_df = pd.DataFrame(tech["signals"])
    emoji = {1: "▲", -1: "▼", 0: "■"}
    sig_df["방향"] = sig_df["direction"].map(emoji)
    if easy_mode:
        sig_df["쉬운 설명"] = sig_df["name"].map(lambda x: SIGNAL_EASY.get(x, ""))
        show_cols = ["방향", "name", "desc", "쉬운 설명"]
    else:
        show_cols = ["방향", "name", "desc"]
    st.dataframe(sig_df[show_cols].rename(columns={"name": "신호", "desc": "설명"}),
                 use_container_width=True, hide_index=True)
    st.write("#### 가격 차트 (일봉 + MA + 볼린저 + 거래량)")
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        d = tech["df"].tail(250)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=d.index, open=d["open"], high=d["high"], low=d["low"],
                                     close=d["close"], name="주가"), row=1, col=1)
        for col, color in [("ma5", "orange"), ("ma20", "blue"), ("ma60", "green")]:
            if col in d:
                fig.add_trace(go.Scatter(x=d.index, y=d[col], name=col.upper(),
                                         line=dict(width=1, color=color)), row=1, col=1)
        fig.add_trace(go.Scatter(x=d.index, y=d["bb_up"], name="BB상단",
                                 line=dict(width=1, dash="dot", color="gray")), row=1, col=1)
        fig.add_trace(go.Scatter(x=d.index, y=d["bb_low"], name="BB하단",
                                 line=dict(width=1, dash="dot", color="gray")), row=1, col=1)
        colors = ["red" if c >= o else "blue" for c, o in zip(d["close"], d["open"])]
        fig.add_trace(go.Bar(x=d.index, y=d["volume"], name="거래량", marker_color=colors), row=2, col=1)
        fig.update_layout(height=620, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"차트 렌더링 실패: {e}")
        st.line_chart(tech["df"]["close"].tail(250))
    sr = tech["support_resistance"]
    st.info(f"최근 60일 고점 {sr['recent_high']:,.0f}원({sr['high_date']}) · 저점 {sr['recent_low']:,.0f}원({sr['low_date']})")

with tab_quant:
    st.write(f"### 종합 {quant['total']}점 · {quant['grade']}등급 · 상승여력 {quant['upside']} (참고확률 {quant['up_prob']}%)")
    qp = pd.DataFrame([{"항목": k, "점수": v} for k, v in quant["parts"].items()])
    st.bar_chart(qp.set_index("항목"))
    st.json(quant["details"])
    if easy_mode:
        with st.expander("쉽게 보기", expanded=True):
            for k, v in quant["parts"].items():
                label, desc = QUANT_EASY.get(k, (k, ""))
                st.write(f"- **{label}**({k}): {v}점")
            st.write("등급 설명: " + GRADE_EASY.get(quant["grade"], ""))
    st.caption("가중치: " + ", ".join(f"{k} {v*100:.0f}%" for k, v in quant["weights"].items()))

with tab_macro:
    st.write(f"### 국면: {macro['regime']}")
    m1, m2, m3 = st.columns(3)
    with m1:
        st.success("호재")
        for b in macro["bullish"] or ["없음"]:
            st.write(f"- {b}")
    with m2:
        st.error("악재")
        for b in macro["bearish"] or ["없음"]:
            st.write(f"- {b}")
    with m3:
        st.info("중립")
        for n in macro["neutral"] or ["없음"]:
            st.write(f"- {n}")
    st.write("#### 지수 추이")
    try:
        import plotly.graph_objects as go2

        fig2 = go2.Figure()
        for k, label in [("KOSPI", "코스피"), ("KOSDAQ", "코스닥")]:
            dfm = macro_bundle.get(k, {}).get("df")
            if dfm is not None:
                col = "close" if "close" in [str(c).lower() for c in dfm.columns] else dfm.columns[0]
                s = dfm[col]
                s = s / s.iloc[0] * 100
                fig2.add_trace(go2.Scatter(x=s.index, y=s.values, name=f"{label}(기준=100)"))
        fig2.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig2, use_container_width=True)
    except Exception as e:
        st.warning(f"지수 차트 실패: {e}")

with tab_news:
    st.write(f"### 기대감: {expect['label']} ({expect['score']}점)")
    if not expect["counts"]["total"]:
        st.warning("뉴스를 가져오지 못했습니다. 해외 서버에서는 네이버 뉴스가 차단될 수 있어 Google 뉴스로 보완 중입니다.")
    st.write(f"뉴스 {expect['counts']['total']}건 · 긍정 {expect['counts']['pos']} · 부정 {expect['counts']['neg']} · 중립 {expect['counts']['neu']}")
    if expect["top_keywords"]:
        st.write("핵심 키워드: " + ", ".join(f"{k['word']}({k['count']})" for k in expect["top_keywords"][:10]))
    st.write("#### 전체 뉴스 (제목 클릭 시 원문 이동)")
    for n in expect["all_news"]:
        mark = "🟢" if n["score"] > 0 else ("🔴" if n["score"] < 0 else "⚪")
        if n.get("link"):
            st.markdown(f"{mark} [{n['title']}]({n['link']}) — {n.get('date','')} {n.get('source','')}")
        else:
            st.write(f"{mark} {n['title']} — {n.get('date','')} {n.get('source','')}")
    if expect["watch_disclosures"]:
        st.write("#### 주목 공시")
        for dc in expect["watch_disclosures"]:
            st.write(f"- {dc['title']} ({dc.get('date','')})")

with tab_theme:
    st.write("### 산업·테마")
    if sector and (sector.get("industry") or sector.get("sector")):
        st.write("산업구분: " + sector.get("industry", "-") + " / 업종: " + sector.get("sector", "-"))
        st.caption(sector.get("note", ""))
    else:
        st.info("업종 분류를 찾지 못했습니다.")
    if expect["top_keywords"]:
        st.write("테마 힌트: " + ", ".join(k["word"] for k in expect["top_keywords"][:10]))
    st.write("#### 같은 산업 뉴스")
    if sector_news:
        for n in sector_news:
            st.write("- " + n["title"] + " (" + n.get("date", "") + ")")
    else:
        st.write("같은 산업 뉴스가 없습니다.")

with tab_raw:
    st.write("#### 펀더멘털 (네이버 금융 크롤링)")
    st.json(fund)
    st.write("#### 일봉 원본 (최근 10행)")
    st.dataframe(price.tail(10), use_container_width=True)
