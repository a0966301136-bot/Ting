import pandas as pd
import numpy as np


def calc_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ma5"]  = df["close"].rolling(5).mean().round(2)
    df["ma20"] = df["close"].rolling(20).mean().round(2)
    df["ma60"] = df["close"].rolling(60).mean().round(2)
    return df


def calc_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    df = df.copy()
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi14"] = (100 - (100 / (1 + rs))).round(2)
    return df


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    買賣訊號策略：
    - 買入:  MA5 上穿 MA20（黃金交叉），且 RSI < 70
    - 賣出: MA5 下穿 MA20（死亡交叉），且 RSI > 30
    - 其餘為 HOLD
    """
    df = df.copy()
    signals = []

    for i in range(len(df)):
        if i < 1 or pd.isna(df["ma5"].iloc[i]) or pd.isna(df["ma20"].iloc[i]):
            signals.append("HOLD")
            continue

        prev_ma5  = df["ma5"].iloc[i - 1]
        prev_ma20 = df["ma20"].iloc[i - 1]
        curr_ma5  = df["ma5"].iloc[i]
        curr_ma20 = df["ma20"].iloc[i]
        rsi       = df["rsi14"].iloc[i] if "rsi14" in df.columns else 50

        golden_cross = (prev_ma5 <= prev_ma20) and (curr_ma5 > curr_ma20)
        death_cross  = (prev_ma5 >= prev_ma20) and (curr_ma5 < curr_ma20)

        if golden_cross and (pd.isna(rsi) or rsi < 70):
            signals.append("BUY")
        elif death_cross and (pd.isna(rsi) or rsi > 30):
            signals.append("SELL")
        else:
            signals.append("HOLD")

    df["signal"] = signals
    return df


def run_analysis(price_df: pd.DataFrame) -> pd.DataFrame:
    """完整分析流程，回傳含所有指標的 DataFrame"""
    if price_df.empty:
        return pd.DataFrame()

    df = price_df.copy()
    df = calc_moving_averages(df)
    df = calc_rsi(df)
    df = generate_signals(df)
    return df


def summary_stats(df: pd.DataFrame) -> dict:
    """回傳基本統計摘要"""
    if df.empty:
        return {}

    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest

    return {
        "最新收盤": latest["close"],
        "今日漲跌%": latest.get("change_pct", 0),
        "52週最高": df["high"].max() if "high" in df.columns else None,
        "52週最低": df["low"].min()  if "low"  in df.columns else None,
        "平均成交量": int(df["volume"].mean()) if "volume" in df.columns else None,
        "MA5":  latest.get("ma5"),
        "MA20": latest.get("ma20"),
        "RSI":  latest.get("rsi14"),
        "訊號": latest.get("signal", "HOLD"),
    }
