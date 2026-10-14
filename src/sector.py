"""업종 분류 조회: 공개 데이터셋을 런타임에 로드 (2018년 기준 분류, 참고용)."""

from __future__ import annotations

import gzip
import io

import pandas as pd
import requests

URL = "https://github.com/FinanceData/stock_master/raw/master/stock_master.csv.gz"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

_cache = None
_failed = False


def load_sector_table():
    global _cache, _failed
    if _cache is not None:
        return _cache["df"]
    if _failed:
        return None
    try:
        r = requests.get(URL, headers=UA, timeout=20)
        r.raise_for_status()
        raw = gzip.decompress(r.content)
        df = pd.read_csv(io.BytesIO(raw), dtype=str)
        df["Symbol"] = df["Symbol"].astype(str).str.strip()
        _cache = {"df": df}
        return df
    except Exception:
        _failed = True
        return None


def get_sector_info(code: str):
    try:
        df = load_sector_table()
        if df is None or "Symbol" not in df.columns:
            return None
        m = df[df["Symbol"] == str(code).strip()]
        if not len(m):
            return None
        row = m.iloc[0]
        return {
            "industry": str(row.get("Industry", "") or "").strip(),
            "sector": str(row.get("Sector", "") or "").strip(),
            "note": "2018년 기준 업종 분류(참고용)",
        }
    except Exception:
        return None
