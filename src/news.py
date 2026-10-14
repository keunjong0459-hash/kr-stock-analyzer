"""뉴스 수집: Google News RSS(1순위, 해외 서버에서도 동작) + 네이버 금융(2순위, 국내망 위주)."""

from __future__ import annotations

import html
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}
GNEWS_URL = "https://news.google.com/rss/search"


def _split_title(raw: str):
    t = html.unescape((raw or "").strip())
    if " - " in t:
        title, src = t.rsplit(" - ", 1)
        return title.strip(), src.strip()
    return t, ""


def _short_date(pub: str) -> str:
    try:
        dt = parsedate_to_datetime(pub)
        return dt.strftime("%m-%d %H:%M")
    except Exception:
        return (pub or "")[:16]


def get_google_news(query: str, max_items: int = 20, timeout: int = 10):
    items = []
    try:
        r = requests.get(
            GNEWS_URL,
            params={"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
            headers=UA,
            timeout=timeout,
        )
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for it in root.iter("item"):
            if len(items) >= max_items:
                break
            title_raw = it.findtext("title") or ""
            link = (it.findtext("link") or "").strip()
            pub = it.findtext("pubDate") or ""
            src_tag = it.findtext("source") or ""
            title, src_from_title = _split_title(title_raw)
            if not title:
                continue
            items.append(
                {
                    "title": title,
                    "date": _short_date(pub),
                    "source": src_tag.strip() or src_from_title,
                    "link": link,
                }
            )
    except Exception:
        pass
    return items


def get_company_news(name: str, max_items: int = 20):
    return get_google_news(name + " 주가", max_items=max_items)


def get_sector_news(keyword: str, max_items: int = 8):
    if not keyword:
        return []
    return get_google_news(keyword + " 전망", max_items=max_items)
