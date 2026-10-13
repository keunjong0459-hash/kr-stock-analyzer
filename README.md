# 한국 주식 종합 분석 (기술적 + 퀀트 + 지수/매크로 + 기업 기대감)

기업명을 입력하면 해당 회사의 상승 가능성을 분석하는 Streamlit 대시보드입니다.
API 키 없이 무료 데이터만 사용합니다.

## 기능

- **기업명 입력 → 자동 분석**: KRX 종목 매핑 (FinanceDataReader, 실패 시 내장 목록)
- **기술적 분석 흐름**: MA5/20/60/120, RSI, MACD, 볼린저, 스토캐스틱, ATR, OBV, 거래량, 골든/데드크로스, 20일 신고가/신저가
- **퀀트 관점**: 모멘텀·추세·변동성·수급·RSI·밸류 6개 팩터 → 0~100점 + S/A/B/C/D 등급 + 상승여력
- **지수 + 매크로**: 코스피/코스닥 추세, 원/달러, VIX, 미 10년 금리, 나스닥/S&P → 호재/악재/중립 + Risk-On/Off 국면
- **기업 자체 기대감**: 네이버 금융 뉴스/공시 크롤링 → 긍정/부정 키워드 사전 기반 점수 + 핵심 키워드 + 주목 공시
- **종합 리포트**: 마크다운 자동 생성 + 다운로드

## 구조

```
kr_stock_analyzer/
  app.py            # Streamlit 대시보드 (진입점)
  requirements.txt
  pyproject.toml
  src/
    universe.py     # KRX 종목명 → 코드
    data.py         # 무료 데이터 수집 (주가/지수/매크로/펀더멘털/뉴스)
    technicals.py   # 기술적 지표 + 신호
    quant.py        # 퀀트 팩터 점수
    market.py       # 지수/매크로 호재·악재 판단
    sentiment.py    # 뉴스 기반 기대감
    report.py       # 종합 리포트 생성
```

## 설치 & 실행 (Windows)

1. Python 3.10+ 설치 (https://www.python.org/downloads/ — 설치 시 **Add python.exe to PATH** 체크)

2. PowerShell에서:

```powershell
cd "C:\\Users\\user\\Desktop\\project\\영상제작\\kr_stock_analyzer"
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

3. 브라우저가 열리면 왼쪽 사이드바에 기업명 입력 → **분석 실행**

### 설치가 안 될 때

```powershell
python -m pip install --upgrade pip
python -m pip install streamlit pandas numpy yfinance FinanceDataReader requests beautifulsoup4 lxml plotly
```

## 데이터 출처

- 주가/상장목록: FinanceDataReader (KRX) → 실패 시 yfinance(.KS/.KQ)
- 지수/환율/금리/VIX: yfinance (`^KS11`, `^KQ11`, `KRW=X`, `^TNX`, `^VIX`, `^IXIC`, `^GSPC`)
- 펀더멘털/뉴스/공시: 네이버 금융 크롤링 (키 불필요)

## 주의

- 본 프로그램의 점수·등급·판단은 **규칙 기반 참고자료**이며 투자 권유가 아닙니다.
- 실전 매매 전 사업보고서·DART 공시를 직접 확인하세요.
- 네이버 크롤링은 페이지 구조 변경 시 일시적으로 실패할 수 있으며, 이 경우 뉴스 점수는 중립(50점)으로 처리됩니다.

## 설치 없이 브라우저만으로 실행 (Streamlit Cloud, 무료)

PC에 아무것도 설치하지 않고 웹 브라우저만으로 사용합니다.

1. GitHub 가입/로그인 (https://github.com) → 새 저장소 생성 (예: `kr-stock-analyzer`, Public)
2. 이 폴더(`kr_stock_analyzer`) 안의 파일 전체를 웹에서 업로드:
   저장소 페이지 → `Add file` → `Upload files` → `app.py`, `requirements.txt`, `runtime.txt`,
   `.streamlit/`, `.gitignore`, `src/` 폴더 안의 파일들을 그대로 드래그 → `Commit changes`
   (폴더 구조 유지가 중요: `app.py`와 `src/`가 같은 위치에 있어야 합니다)
3. https://share.streamlit.io 접속 → `Deploy an app` → 방금 만든 저장소 선택
   - Branch: `main`, Main file path: `app.py` → `Deploy`
4. 2~5분 후 `https://xxx.streamlit.app` 주소가 생기면 접속해서 사용. 이후부터는 설치 없이 URL만 열면 됩니다.

> 참고: 무료 티어는 트래픽이 없으면 절전(sleep)되고, 접속 시 1분 정도 깨어나는 시간이 걸립니다.
