import time
import random
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List
from email.utils import parsedate_to_datetime

# 反爬蟲機制
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# 股票名稱對照（爬新聞用）
STOCK_NAMES = {
    "2330": "台積電",
    "2317": "鴻海",
    "2454": "聯發科",
    "2412": "中華電",
    "2882": "國泰金",
    "2303": "聯電",
    "2881": "富邦金",
    "1301": "台塑",
    "2002": "中鋼",
    "2886": "兆豐金",
}


def get_headers() -> dict:
    """每次請求隨機挑選 User-Agent，降低被封鎖機率"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
    }


def random_delay(min_sec: float = 0.8, max_sec: float = 2.0):
    """隨機延遲，模擬人類瀏覽行為"""
    time.sleep(random.uniform(min_sec, max_sec))


def fetch_with_retry(url: str, params: dict = None, max_retries: int = 3) -> Optional[requests.Response]:
    """
    帶重試機制的 HTTP GET
    指數退避 (Exponential Backoff)：失敗後等待時間逐次加倍
    """
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if status == 429:
                wait = (2 ** attempt) * 2
                print(f"  [限流] 等待 {wait}s 後重試... (第 {attempt+1} 次)")
                time.sleep(wait)
            else:
                print(f"  [HTTP錯誤] {e}")
                return None
        except requests.exceptions.ConnectionError:
            wait = (2 ** attempt) * 1.5
            print(f"  [連線失敗] 等待 {wait:.1f}s 後重試... (第 {attempt+1} 次)")
            time.sleep(wait)
        except requests.exceptions.Timeout:
            print(f"  [逾時] 第 {attempt+1} 次嘗試")
        except Exception as e:
            print(f"  [未知錯誤] {e}")
            return None
    print(f"  [放棄] 已重試 {max_retries} 次，跳過此請求")
    return None


# Google News RSS 爬蟲 

def fetch_cnyes_stock_news(stock_id: str, pages: int = 2) -> pd.DataFrame:
    """
    爬取個股相關新聞
    來源：Google News RSS — 解析 XML <item> 標籤取得標題、時間、連結
    pages 參數保留相容性（RSS 一次回傳全部，不分頁）
    """
    stock_name = STOCK_NAMES.get(stock_id, stock_id)
    query = f"{stock_name} {stock_id} 股票"

    url = "https://news.google.com/rss/search"
    params = {
        "q": query,
        "hl": "zh-TW",
        "gl": "TW",
        "ceid": "TW:zh-Hant",
    }

    print(f"[新聞爬蟲] 開始抓取 {stock_id} {stock_name} 新聞")
    print(f"  -> 搜尋關鍵字：{query} ...", end=" ")

    resp = fetch_with_retry(url, params=params)
    if resp is None:
        print("失敗")
        return pd.DataFrame()

    # BeautifulSoup 解析 RSS XML
    soup = BeautifulSoup(resp.content, "xml")
    items = soup.find_all("item")

    if not items:
        # 備援：改用 lxml-xml parser
        soup = BeautifulSoup(resp.content, "lxml-xml")
        items = soup.find_all("item")

    rows = []
    for item in items:
        try:
            # 標題（移除來源後綴，例如「- 經濟日報」）
            title_tag = item.find("title")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            title = title.rsplit(" - ", 1)[0].strip()

            # 連結
            link_tag = item.find("link")
            link = link_tag.get_text(strip=True) if link_tag else ""

            # 發布時間（RSS 使用 RFC 2822 格式）
            pub_tag = item.find("pubDate")
            pub_date = None
            if pub_tag:
                try:
                    dt = parsedate_to_datetime(pub_tag.get_text(strip=True))
                    pub_date = dt.strftime("%Y-%m-%d")
                except Exception:
                    pub_date = datetime.now().strftime("%Y-%m-%d")

            # 來源媒體
            source_tag = item.find("source")
            source = source_tag.get_text(strip=True) if source_tag else "Google新聞"

            if title and pub_date:
                rows.append({
                    "stock_id": stock_id,
                    "date": pub_date,
                    "title": title,
                    "url": link,
                    "source": source,
                })
        except Exception:
            continue

    print(f"取得 {len(rows)} 則")

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.drop_duplicates("title").sort_values("date", ascending=False).reset_index(drop=True)
    print(f"[新聞爬蟲] {stock_id} 共取得 {len(df)} 則新聞")
    return df


def fetch_news_batch(stock_ids: List[str], pages: int = 2) -> pd.DataFrame:
    """批次爬取多支股票新聞"""
    all_frames = []
    for i, sid in enumerate(stock_ids):
        df = fetch_cnyes_stock_news(sid, pages=pages)
        if not df.empty:
            all_frames.append(df)
        if i < len(stock_ids) - 1:
            wait = random.uniform(1.5, 3.0)
            print(f"  [等待 {wait:.1f}s 後繼續...]\n")
            time.sleep(wait)

    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)


if __name__ == "__main__":
    df = fetch_cnyes_stock_news("2330")
    if not df.empty:
        print("\n最新 5 則新聞：")
        print(df[["date", "title", "source"]].head().to_string(index=False))
