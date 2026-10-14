"""KRX 종목 유니버스: 기업명 -> 종목코드 매핑 (무료 소스만 사용).

우선순위: FinanceDataReader(설치된 경우) -> 네이버 시세 크롤링 -> 내장 목록.
Streamlit Cloud 등 FinanceDataReader가 없는 환경에서도 전체 종목 검색이 된다.
"""

from __future__ import annotations

import difflib
import time
from pathlib import Path

import pandas as pd

# 최후 fallback: 주요 종목
BUILTIN_UNIVERSE = pd.DataFrame(
    [
        {"Code": "005930", "Name": "삼성전자", "Market": "KOSPI"},
        {"Code": "000660", "Name": "SK하이닉스", "Market": "KOSPI"},
        {"Code": "373220", "Name": "LG에너지솔루션", "Market": "KOSPI"},
        {"Code": "005380", "Name": "현대차", "Market": "KOSPI"},
        {"Code": "000270", "Name": "기아", "Market": "KOSPI"},
        {"Code": "035420", "Name": "NAVER", "Market": "KOSPI"},
        {"Code": "035720", "Name": "카카오", "Market": "KOSPI"},
        {"Code": "051910", "Name": "LG화학", "Market": "KOSPI"},
        {"Code": "006400", "Name": "삼성SDI", "Market": "KOSPI"},
        {"Code": "028260", "Name": "삼성물산", "Market": "KOSPI"},
        {"Code": "105560", "Name": "KB금융", "Market": "KOSPI"},
        {"Code": "055550", "Name": "신한지주", "Market": "KOSPI"},
        {"Code": "066570", "Name": "LG전자", "Market": "KOSPI"},
        {"Code": "003670", "Name": "포스코홀딩스", "Market": "KOSPI"},
        {"Code": "096770", "Name": "SK이노베이션", "Market": "KOSPI"},
        {"Code": "247540", "Name": "에코프로비엠", "Market": "KOSDAQ"},
        {"Code": "086520", "Name": "에코프로", "Market": "KOSDAQ"},
        {"Code": "041510", "Name": "에스엠", "Market": "KOSDAQ"},
        {"Code": "035900", "Name": "JYP Ent.", "Market": "KOSDAQ"},
        {"Code": "028300", "Name": "HLB", "Market": "KOSDAQ"},
        {"Code": "091990", "Name": "셀트리온헬스케어", "Market": "KOSDAQ"},
    ]
).drop_duplicates(subset=["Code"]).reset_index(drop=True)

_NAVER_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


def _load_bundled_csv() -> pd.DataFrame:
    here = Path(__file__).resolve().parent.parent / "data" / "krx_listing.csv"
    df = pd.read_csv(here, encoding="utf-8-sig", dtype=str)
    df = df.rename(columns={c: c.strip() for c in df.columns})
    df["Code"] = df["Code"].astype(str).str.strip()
    df["Name"] = df["Name"].astype(str).str.strip()
    df["Market"] = df["Market"].astype(str).str.strip().str.upper()
    df = df[df["Code"].str.len().between(5, 6) & df["Name"].ne("")].reset_index(drop=True)
    df = df.drop_duplicates(subset=["Code"]).reset_index(drop=True)
    if len(df) < 100:
        raise RuntimeError("bundled listing too small")
    return df


def _load_naver_universe(pages_per_market: int = 60, pause: float = 0.15) -> pd.DataFrame:
    """네이버 금융 시가총액 페이지를 순회해 전체 상장 목록 수집."""
    import requests
    from bs4 import BeautifulSoup

    rows: list[dict] = []
    for sosok, mkt in [(0, "KOSPI"), (1, "KOSDAQ")]:
        for page in range(1, pages_per_market + 1):
            url = (
                "https://finance.naver.com/sise/sise_market_sum.naver"
                f"?sosok={sosok}&page={page}"
            )
            try:
                r = requests.get(url, headers=_NAVER_UA, timeout=6)
                r.raise_for_status()
            except Exception:
                break
            soup = BeautifulSoup(r.text, "lxml")
            found = 0
            for a in soup.select("table.type_2 a"):
                href = a.get("href", "")
                if "main.naver?code=" not in href:
                    continue
                code = href.split("code=")[-1].split("&")[0]
                name = a.get_text(strip=True)
                if len(code) == 6 and code.isdigit() and name:
                    rows.append({"Code": code, "Name": name, "Market": mkt})
                    found += 1
            if found == 0:
                break
            time.sleep(pause)
    df = pd.DataFrame(rows).drop_duplicates(subset=["Code"]).reset_index(drop=True)
    if len(df) < 500:
        raise RuntimeError(f"naver listing too small: {len(df)}")
    return df


def load_universe() -> pd.DataFrame:
    """KRX 전체 종목 목록 반환. 실패하면 내장 목록."""

    try:
        return _load_bundled_csv()
    except Exception:
        pass
    # 1) FinanceDataReader (로컬 등 설치된 환경)
    try:
        import FinanceDataReader as fdr

        df = fdr.StockListing("KRX")
        cols = {c.lower(): c for c in df.columns}
        code_c = cols.get("code", "Code")
        name_c = cols.get("name", "Name")
        mkt_c = cols.get("market", "Market" if "Market" in df.columns else None)
        out = pd.DataFrame(
            {
                "Code": df[code_c].astype(str).str.zfill(6),
                "Name": df[name_c].astype(str),
                "Market": df[mkt_c].astype(str) if mkt_c else "KRX",
            }
        )
        out = out.dropna(subset=["Code", "Name"])
        if len(out) > 100:
            return out.reset_index(drop=True)
    except Exception:
        pass
    # 2) 네이버 크롤링 (키 불필요)
    try:
        return _load_naver_universe()
    except Exception:
        pass
    # 3) 내장 목록
    return BUILTIN_UNIVERSE.copy()


_YAHOO_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


def yahoo_search_fallback(query: str):
    q = (query or "").strip()
    if not q:
        return None
    try:
        import requests

        r = requests.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": q, "quotesCount": 10, "country": "South Korea", "lang": "ko"},
            headers=_YAHOO_UA,
            timeout=8,
        )
        r.raise_for_status()
        quotes = (r.json().get("quotes", []) or [])
    except Exception:
        return None
    for item in quotes:
        try:
            sym = str(item.get("symbol", ""))
            if sym.endswith(".KS"):
                code, mkt = sym[:-3], "KOSPI"
            elif sym.endswith(".KQ"):
                code, mkt = sym[:-3], "KOSDAQ"
            else:
                continue
            if not code:
                continue
            name = str(item.get("longname") or item.get("shortname") or q).strip()
            return {"Code": code, "Name": name or q, "Market": mkt}
        except Exception:
            continue
    return None

def resolve_company(query: str, universe: pd.DataFrame) -> dict | None:
    """기업명(부분 일치/유사도)으로 종목 찾기. {'Code','Name','Market'} 반환."""
    q = (query or "").strip()
    if not q:
        return None
    q_nospace = q.replace(" ", "").lower()

    # 0) 종목코드 직접 입력 (숫자 5~6자리)
    if q_nospace.isdigit() and len(q_nospace) in (5, 6):
        m = universe[universe["Code"] == q_nospace.zfill(6)]
        if len(m):
            r = m.iloc[0]
            return {"Code": r["Code"], "Name": r["Name"], "Market": r["Market"]}

    # 1) 정확 일치
    m = universe[universe["Name"].str.replace(" ", "").str.lower() == q_nospace]
    if len(m):
        r = m.iloc[0]
        return {"Code": r["Code"], "Name": r["Name"], "Market": r["Market"]}
    # 2) 부분 포함 (짧은 순 = 더 정확한 매칭 우선)
    contains = universe[universe["Name"].str.replace(" ", "").str.lower().str.contains(q_nospace, na=False)]
    if len(contains):
        contains = contains.iloc[(contains["Name"].str.len()).argsort()].reset_index(drop=True)
        r = contains.iloc[0]
        return {"Code": r["Code"], "Name": r["Name"], "Market": r["Market"]}
    # 3) 유사도
    names = universe["Name"].tolist()
    best = difflib.get_close_matches(q, names, n=1, cutoff=0.5)
    if best:
        r = universe[universe["Name"] == best[0]].iloc[0]
        return {"Code": r["Code"], "Name": r["Name"], "Market": r["Market"]}
    # 4) Yahoo 검색 보완 (ETF, 신규, 별명)
    y = yahoo_search_fallback(q)
    if y:
        return y
    return None


def suggest_names(query: str, universe: pd.DataFrame, n: int = 8) -> list[str]:
    q = (query or "").strip().replace(" ", "").lower()
    if not q:
        return universe["Name"].head(n).tolist()
    if q.replace(" ", "").isdigit():
        codeq = q.replace(" ", "")
        hits = universe[universe["Code"].str.startswith(codeq)]["Name"].head(n).tolist()
        if hits:
            return hits
    mask = universe["Name"].str.replace(" ", "").str.lower().str.contains(q, na=False)
    hits = universe[mask]["Name"].head(n).tolist()
    if len(hits) >= n:
        return hits
    extra = difflib.get_close_matches(query, universe["Name"].tolist(), n=n - len(hits), cutoff=0.4)
    return hits + [e for e in extra if e not in hits]
