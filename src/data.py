"""무료 데이터 수집 레이어.

우선순위:
- 주가: FinanceDataReader -> yfinance(.KS/.KQ) -> stooq CSV
- 지수: yfinance(^KS11, ^KQ11) -> FinanceDataReader(KS11, KQ11)
- 매크로: yfinance(KRW=X, ^TNX, ^VIX, ^IXIC, ^GSPC)
- 펀더멘털/뉴스: 네이버 금융 크롤링 (키 불필요)
"""

from __future__ import annotations

import io
import re
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

PRICE_YEARS = 2


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        known = {"open", "high", "low", "close", "adj close", "adj_close", "volume"}
        flat = []
        for c in df.columns:
            parts = [str(x).strip().lower() for x in c]
            hit = next((p for p in parts if p in known), parts[-1])
            flat.append(hit)
        df.columns = flat
    else:
        df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = _flatten_columns(df)
    rename = {
        "open": "open", "high": "high", "low": "low", "close": "close",
        "adj close": "close", "adj_close": "close", "volume": "volume",
        "시가": "open", "고가": "high", "저가": "low", "종가": "close", "거래량": "volume",
    }
    df = df.rename(columns={c: rename.get(c, c) for c in df.columns})
    df = df.loc[:, ~df.columns.duplicated()]
    for c in ["open", "high", "low", "close", "volume"]:
        if c not in df.columns:
            raise ValueError(f"OHLCV 컬럼 부족: {list(df.columns)}")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
    return df


def get_price(code: str, market: str = "", years: int = PRICE_YEARS) -> pd.DataFrame:
    """종목 일봉 반환. 실패 시 예외 발생 (상위에서 처리)."""
    errors: list[str] = []

    # 1) FinanceDataReader
    try:
        import FinanceDataReader as fdr

        end = datetime.now()
        start = end - timedelta(days=int(years * 365) + 30)
        df = fdr.DataReader(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if df is not None and len(df) > 0:
            return _normalize_ohlcv(df)
        errors.append("fdr: 데이터 부족")
    except Exception as e:  # noqa: BLE001
        errors.append(f"fdr: {e}")

    # 2) yfinance (.KS / .KQ 둘 다 시도)
    try:
        import yfinance as yf

        suffixes = []
        if "KOSDAQ" in (market or "").upper() or "KQ" in (market or "").upper():
            suffixes = [".KQ", ".KS"]
        else:
            suffixes = [".KS", ".KQ"]
        for sfx in suffixes:
            try:
                df = yf.download(
                    code + sfx, period=f"{years}y", interval="1d",
                    auto_adjust=False, progress=False, threads=False,
                )
                if df is not None and len(df) > 0:
                    return _normalize_ohlcv(df)
            except Exception as e:  # noqa: BLE001
                errors.append(f"yfinance{sfx}: {e}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"yfinance import: {e}")

    # 3) stooq (한국 종목은 지원이 약하지만 마지막 시도)
    try:
        url = f"https://stooq.com/q/d/l/?s={code.lower()}.kr&d1={(datetime.now()-timedelta(days=years*365)).strftime('%Y%m%d')}&d2={datetime.now().strftime('%Y%m%d')}&i=d"
        r = requests.get(url, headers=UA, timeout=15)
        if r.ok and "Date" in r.text[:200]:
            df = pd.read_csv(io.StringIO(r.text), parse_dates=["Date"], index_col="Date")
            if len(df) > 0:
                return _normalize_ohlcv(df)
        errors.append("stooq: 데이터 부족")
    except Exception as e:  # noqa: BLE001
        errors.append(f"stooq: {e}")

    raise RuntimeError("주가 조회 실패: " + " | ".join(errors))


def get_index(symbol: str, years: int = 2) -> pd.DataFrame:
    """^KS11, ^KQ11 등 지수/매크로 시계열. 종가 한 컬럼 이상 보장."""
    errors: list[str] = []
    # yfinance 우선
    try:
        import yfinance as yf

        df = yf.download(symbol, period=f"{years}y", interval="1d",
                         auto_adjust=False, progress=False, threads=False)
        if df is not None and len(df) > 0:
            df = _flatten_columns(df)
            df = df.loc[:, ~df.columns.duplicated()]
            if "adj close" in df.columns and "close" not in df.columns:
                df = df.rename(columns={"adj close": "close"})
            df.index = pd.to_datetime(df.index)
            return df.sort_index()
        errors.append("yf: 부족")
    except Exception as e:  # noqa: BLE001
        errors.append(f"yf: {e}")
    # FinanceDataReader (KS11/KQ11)
    try:
        import FinanceDataReader as fdr

        alt = {"^KS11": "KS11", "^KQ11": "KQ11"}.get(symbol, symbol)
        end = datetime.now()
        start = end - timedelta(days=years * 365 + 30)
        df = fdr.DataReader(alt, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if df is not None and len(df) > 0:
            return _normalize_ohlcv(df) if "volume" in [c.lower() for c in df.columns] else df
        errors.append("fdr: 부족")
    except Exception as e:  # noqa: BLE001
        errors.append(f"fdr: {e}")
    raise RuntimeError(f"{symbol} 조회 실패: " + " | ".join(errors))


def get_macro_bundle() -> dict:
    """지수+환율+미국채+변동성 묶음. 각 키: df 또는 None + error."""
    tickers = {
        "KOSPI": "^KS11",
        "KOSDAQ": "^KQ11",
        "USDKRW": "KRW=X",
        "US10Y": "^TNX",
        "VIX": "^VIX",
        "NASDAQ": "^IXIC",
        "SP500": "^GSPC",
    }
    out: dict = {}
    for k, t in tickers.items():
        try:
            out[k] = {"df": get_index(t), "error": None}
        except Exception as e:  # noqa: BLE001
            out[k] = {"df": None, "error": str(e)}
    return out


def _naver_get(url: str, timeout: int = 12) -> requests.Response:
    return requests.get(url, headers=UA, timeout=timeout)


def get_fundamentals(code: str) -> dict:
    """네이버 금융에서 PER/PBR/ROE/시가총액 등 크롤링. 실패해도 빈 dict."""
    info: dict = {"code": code, "error": None}
    try:
        from bs4 import BeautifulSoup

        url = f"https://finance.naver.com/item/main.naver?code={code}"
        r = _naver_get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        text = soup.get_text(" ", strip=True)

        def grab(pattern: str):
            m = re.search(pattern, text)
            return m.group(1).strip() if m else None

        # PER / PBR / ROE / 시가총액 / 배당수익률
        info["per"] = grab(r"PER\s*([\d.,]+)\s*배")
        info["pbr"] = grab(r"PBR\s*([\d.,]+)\s*배")
        info["roe"] = grab(r"ROE\s*\(.*?\)\s*([-\d.,]+)\s*%")
        if not info["roe"]:
            info["roe"] = grab(r"ROE\s*([-\d.,]+)\s*%")
        info["marketcap"] = grab(r"시가총액\s*([\d조억,\s원]+)")
        info["div_yield"] = grab(r"배당수익률\s*([\d.,]+)\s*%")
        # 업종
        info["sector"] = grab(r"업종\s*([가-힣A-Za-z0-9\s·&/+-]+?)\s*(상장주식수|결산월|매출액)")
        # 현재가/전일대비
        info["raw_ok"] = True
    except Exception as e:  # noqa: BLE001
        info["error"] = str(e)
    return info


def get_naver_news(code: str, pages: int = 2, pause: float = 0.4) -> list[dict]:
    """네이버 금융 종목 뉴스 (제목/날짜/출처/링크)."""
    items: list[dict] = []
    try:
        from bs4 import BeautifulSoup

        for p in range(1, pages + 1):
            url = f"https://finance.naver.com/item/news_news.naver?code={code}&page={p}"
            r = _naver_get(url)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            for tr in soup.select("table.type5 tr"):
                tds = tr.select("td")
                if len(tds) < 3:
                    continue
                a = tds[0].select_one("a")
                if not a:
                    continue
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if href.startswith("/"):
                    href = "https://finance.naver.com" + href
                items.append(
                    {
                        "title": title,
                        "date": tds[1].get_text(strip=True),
                        "source": tds[2].get_text(strip=True),
                        "link": href,
                    }
                )
            time.sleep(pause)
    except Exception:
        pass
    # 중복 제거
    seen, out = set(), []
    for it in items:
        if it["title"] not in seen:
            seen.add(it["title"])
            out.append(it)
    return out


def get_dart_disclosures(code: str, pages: int = 1) -> list[dict]:
    """네이버 금융 경유 최근 공시."""
    items: list[dict] = []
    try:
        from bs4 import BeautifulSoup

        for p in range(1, pages + 1):
            url = f"https://finance.naver.com/item/dart.naver?code={code}&page={p}"
            r = _naver_get(url)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            for tr in soup.select("table.type5 tr"):
                tds = tr.select("td")
                if len(tds) < 3:
                    continue
                a = tds[0].select_one("a")
                if not a:
                    continue
                items.append(
                    {
                        "title": a.get_text(strip=True),
                        "date": tds[1].get_text(strip=True),
                        "source": tds[2].get_text(strip=True),
                    }
                )
            time.sleep(0.3)
    except Exception:
        pass
    return items
