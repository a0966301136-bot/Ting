from typing import List
import sys
from scraper      import fetch_stock_history, get_stock_name, STOCK_NAMES
from database     import init_db, upsert_stock, upsert_prices, upsert_analysis, upsert_news
from analyzer     import run_analysis, summary_stats
from news_scraper import fetch_cnyes_stock_news


def run(stock_ids: List[str], months: int = 6, fetch_news: bool = True):
    init_db()

    for sid in stock_ids:
        name = get_stock_name(sid)
        upsert_stock(sid, name)

        print(f"\n{'='*40}")
        print(f"  處理股票：{sid} {name}")
        print(f"{'='*40}")

        # 1. 爬取股價資料
        price_df = fetch_stock_history(sid, months=months)
        if price_df.empty:
            print(f"[跳過] {sid} 無法取得股價資料\n")
            continue

        # 2. 存入資料庫
        upsert_prices(price_df, sid)
        print(f"[DB] {sid} 存入 {len(price_df)} 筆價格資料")

        # 3. 技術分析
        analysis_df = run_analysis(price_df)
        analysis_df["stock_id"] = sid
        upsert_analysis(
            analysis_df[["date", "ma5", "ma20", "ma60", "rsi14", "signal", "stock_id"]],
            sid,
        )
        print(f"[分析] {sid} 完成技術指標計算")

        if fetch_news:
            news_df = fetch_cnyes_stock_news(sid, pages=2)
            if not news_df.empty:
                upsert_news(news_df, sid)
            else:
                print(f"[新聞] {sid} 本次未取得新聞")

        
        stats = summary_stats(analysis_df)
        print(f"\n  {sid} {name} 分析摘要")
        print(f"  {'-'*30}")
        for k, v in stats.items():
            print(f"  {k:10s}: {v}")
        print()


if __name__ == "__main__":
    args = sys.argv[1:]

    # 支援 --no-news 旗標跳過新聞爬蟲
    fetch_news = "--no-news" not in args
    stock_args = [a for a in args if not a.startswith("--")]

    targets = stock_args if stock_args else ["2330", "2317", "2454", "2412", "2882"]

    run(targets, months=6, fetch_news=fetch_news)
    print("\n[完成] 所有資料已更新，請執行 streamlit run app.py 查看儀表板")
