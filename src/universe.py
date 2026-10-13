"""KRX 종목 유니버스: 기업명 -> 종목코드 매핑 (무료 소스만 사용)."""

from __future__ import annotations

import difflib
import pandas as pd

# FinanceDataReader 없을 때도 앱이 죽지 않도록 최소 내장 유니버스
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


def load_universe() -> pd.DataFrame:
    """KRX 전체 종목 목록 반환. 실패하면 내장 목록."""
    try:
        import FinanceDataReader as fdr

        df = fdr.StockListing("KRX")
        # 컬럼명 버전 차이 흡수: Code/Name/Market
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
    return BUILTIN_UNIVERSE.copy()


def resolve_company(query: str, universe: pd.DataFrame) -> dict | None:
    """기업명(부분 일치/유사도)으로 종목 찾기. {'Code','Name','Market'} 반환."""
    q = (query or "").strip()
    if not q:
        return None
    q_nospace = q.replace(" ", "").lower()

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
    return None


def suggest_names(query: str, universe: pd.DataFrame, n: int = 8) -> list[str]:
    q = (query or "").strip().replace(" ", "").lower()
    if not q:
        return universe["Name"].head(n).tolist()
    mask = universe["Name"].str.replace(" ", "").str.lower().str.contains(q, na=False)
    hits = universe[mask]["Name"].head(n).tolist()
    if len(hits) >= n:
        return hits
    extra = difflib.get_close_matches(query, universe["Name"].tolist(), n=n - len(hits), cutoff=0.4)
    return hits + [e for e in extra if e not in hits]
