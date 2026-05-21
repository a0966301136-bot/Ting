import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from database import init_db, list_stocks, load_prices, load_analysis, load_news, upsert_news
from scraper  import STOCK_NAMES
from analyzer import run_analysis, summary_stats
from news_scraper import fetch_cnyes_stock_news

# 頁面設定 
st.set_page_config(
    page_title="台股爬蟲分析系統",
    page_icon="📈",
    layout="wide",
)

init_db()

#側邊欄
with st.sidebar:
    st.title("台股智慧分析")
    st.markdown("---")

    stocks_df = list_stocks()
    if stocks_df.empty:
        st.warning("尚無資料，請先執行 `python main.py` 抓取資料")
        st.stop()

    options = {f"{r['stock_id']} {r['name']}": r["stock_id"] for _, r in stocks_df.iterrows()}
    selected_label = st.selectbox("選擇股票", list(options.keys()))
    stock_id = options[selected_label]

    st.markdown("---")
    show_ma5   = st.checkbox("MA5",  value=True)
    show_ma20  = st.checkbox("MA20", value=True)
    show_ma60  = st.checkbox("MA60", value=True)
    show_vol   = st.checkbox("成交量", value=True)
    show_rsi   = st.checkbox("RSI",  value=True)
    show_news  = st.checkbox("新聞標記", value=True)

# 載入資料 
price_df    = load_prices(stock_id)
analysis_df = load_analysis(stock_id)
news_df     = load_news(stock_id, days=180)

if price_df.empty:
    st.error(f"找不到 {stock_id} 的價格資料，請重新執行 main.py")
    st.stop()

# 合併價格與分析
merged = price_df.merge(
    analysis_df[["date", "ma5", "ma20", "ma60", "rsi14", "signal"]],
    on="date", how="left"
)

# 頁首
name = stocks_df[stocks_df["stock_id"] == stock_id]["name"].values[0]
st.title(f"📈 {stock_id} {name}")

latest = merged.iloc[-1]
col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("收盤價", f"{latest['close']:.2f}")
col2.metric("漲跌幅", f"{latest['change_pct']:.2f}%", delta=f"{latest['change_pct']:.2f}%")
col3.metric("MA5",  f"{latest['ma5']:.2f}"  if pd.notna(latest.get('ma5'))  else "N/A")
col4.metric("MA20", f"{latest['ma20']:.2f}" if pd.notna(latest.get('ma20')) else "N/A")
rsi_val = latest.get('rsi14')
col5.metric("RSI",  f"{rsi_val:.1f}" if pd.notna(rsi_val) else "N/A")

st.markdown("---")

# 訊號標籤 
signal = latest.get("signal", "HOLD")
if signal == "BUY":
    st.success("🟢 目前訊號：**買入 (BUY)** — MA5 黃金交叉且 RSI < 70")
elif signal == "SELL":
    st.error("🔴 目前訊號：**賣出 (SELL)** — MA5 死亡交叉且 RSI > 30")
else:
    st.info("⚪ 目前訊號：**持有觀望 (HOLD)**")

# 主圖：K線 + 均線 
rows = 1 + int(show_vol) + int(show_rsi)
row_heights = [0.55]
if show_vol: row_heights.append(0.2)
if show_rsi: row_heights.append(0.25)

fig = make_subplots(
    rows=rows, cols=1,
    shared_xaxes=True,
    row_heights=row_heights,
    vertical_spacing=0.03,
)

# K線
fig.add_trace(go.Candlestick(
    x=merged["date"],
    open=merged["open"], high=merged["high"],
    low=merged["low"],   close=merged["close"],
    name="K線",
    increasing_line_color="#ef5350",
    decreasing_line_color="#26a69a",
), row=1, col=1)

# 均線
ma_configs = [
    ("ma5",  show_ma5,  "#FFA726", "MA5"),
    ("ma20", show_ma20, "#42A5F5", "MA20"),
    ("ma60", show_ma60, "#AB47BC", "MA60"),
]
for col_name, show, color, label in ma_configs:
    if show and col_name in merged.columns:
        fig.add_trace(go.Scatter(
            x=merged["date"], y=merged[col_name],
            mode="lines", line=dict(color=color, width=1.5),
            name=label,
        ), row=1, col=1)

# 買賣訊號
buy_df  = merged[merged["signal"] == "BUY"]
sell_df = merged[merged["signal"] == "SELL"]

if not buy_df.empty:
    fig.add_trace(go.Scatter(
        x=buy_df["date"], y=buy_df["low"] * 0.98,
        mode="markers+text", name="買入",
        marker=dict(symbol="triangle-up", size=12, color="red"),
        text=["▲"] * len(buy_df), textposition="bottom center",
    ), row=1, col=1)

if not sell_df.empty:
    fig.add_trace(go.Scatter(
        x=sell_df["date"], y=sell_df["high"] * 1.02,
        mode="markers+text", name="賣出",
        marker=dict(symbol="triangle-down", size=12, color="green"),
        text=["▼"] * len(sell_df), textposition="top center",
    ), row=1, col=1)

# 新聞標記（黃色菱形） 
if show_news and not news_df.empty:
    news_dates = news_df["date"].unique()
    matched = merged[merged["date"].isin(news_dates)].copy()

    if not matched.empty:
        # 同一天多則新聞合併為 hover 文字
        news_titles = (
            news_df.groupby("date")["title"]
            .apply(lambda x: "<br>".join(
                f"• {t[:28]}…" if len(t) > 28 else f"• {t}" for t in x
            ))
            .reset_index()
        )
        matched = matched.merge(news_titles, on="date", how="left")

        fig.add_trace(go.Scatter(
            x=matched["date"],
            y=matched["high"] * 1.035,
            mode="markers",
            name="新聞事件",
            marker=dict(
                symbol="diamond",
                size=10,
                color="#FFD700",
                line=dict(color="#FF8C00", width=1.5),
            ),
            hovertemplate="<b>%{x}</b><br>%{customdata}<extra></extra>",
            customdata=matched["title"],
        ), row=1, col=1)

current_row = 2

# 成交量
if show_vol:
    colors = ["#ef5350" if c >= 0 else "#26a69a" for c in merged["change_pct"].fillna(0)]
    fig.add_trace(go.Bar(
        x=merged["date"], y=merged["volume"],
        name="成交量", marker_color=colors, opacity=0.7,
    ), row=current_row, col=1)
    fig.update_yaxes(title_text="成交量", row=current_row, col=1)
    current_row += 1

# RSI
if show_rsi and "rsi14" in merged.columns:
    fig.add_trace(go.Scatter(
        x=merged["date"], y=merged["rsi14"],
        mode="lines", line=dict(color="#FF7043", width=1.5),
        name="RSI(14)",
    ), row=current_row, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red",   annotation_text="超買(70)", row=current_row, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="超賣(30)", row=current_row, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=current_row, col=1)

fig.update_layout(
    height=700,
    xaxis_rangeslider_visible=False,
    template="plotly_dark",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=20, r=20, t=40, b=20),
)
st.plotly_chart(fig, use_container_width=True)

# 新聞面板 
with st.expander("📰 最新相關新聞", expanded=True):
    col_btn, col_info = st.columns([1, 5])

    with col_btn:
        if st.button("🔄 更新新聞"):
            with st.spinner("爬取新聞中，請稍候..."):
                fresh = fetch_cnyes_stock_news(stock_id, pages=2)
                if not fresh.empty:
                    upsert_news(fresh, stock_id)
                    st.success(f"已更新 {len(fresh)} 則新聞")
                    st.rerun()
                else:
                    st.warning("未取得新聞，請稍後再試")

    with col_info:
        st.caption("新聞來源：鉅亨網｜圖表上 ◆ 黃色標記 = 當日有相關新聞（滑鼠懸停可看標題）")

    if news_df.empty:
        st.info("尚無新聞資料，請點擊「更新新聞」按鈕抓取")
    else:
        for _, row in news_df.head(15).iterrows():
            c_date, c_title = st.columns([1.2, 8])
            with c_date:
                st.markdown(
                    f"<span style='color:#aaa; font-size:0.85em;'>{row['date']}</span>",
                    unsafe_allow_html=True,
                )
            with c_title:
                if row.get("url"):
                    st.markdown(f"[{row['title']}]({row['url']})")
                else:
                    st.markdown(row["title"])
        st.caption(f"共 {len(news_df)} 則新聞｜顯示最新 15 則")

# 資料表 
with st.expander("📋 原始資料 & 分析結果"):
    display = merged[["date", "open", "high", "low", "close", "volume",
                       "change_pct", "ma5", "ma20", "ma60", "rsi14", "signal"]].copy()
    display.columns = ["日期", "開盤", "最高", "最低", "收盤", "成交量",
                       "漲跌%", "MA5", "MA20", "MA60", "RSI(14)", "訊號"]

    def color_signal(val):
        if val == "BUY":  return "background-color: #ef5350; color: white"
        if val == "SELL": return "background-color: #26a69a; color: white"
        return ""

    styled = display.iloc[::-1].style.map(color_signal, subset=["訊號"])
    st.dataframe(styled, use_container_width=True, height=300)

#統計摘要
with st.expander("統計摘要"):
    c1, c2 = st.columns(2)
    with c1:
        st.write("**價格統計**")
        st.write(merged["close"].describe().rename("收盤價").to_frame())
    with c2:
        st.write("**訊號分佈**")
        sig_counts = merged["signal"].value_counts().rename_axis("訊號").reset_index(name="次數")
        st.dataframe(sig_counts)

st.caption("資料來源：台灣證券交易所 (TWSE) | 新聞來源：鉅亨網 | 技術分析僅供參考，不構成投資建議")
