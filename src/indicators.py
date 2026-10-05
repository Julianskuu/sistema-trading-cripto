"""Indicadores calculados a mano (pandas puro), para poder recalcularlos en 4H/1D
despues de resamplear el OHLCV horario (los indicadores del CSV original solo son
validos en resolucion horaria, no se pueden "resamplear" directamente)."""

import numpy as np
import pandas as pd


def sma(series, n):
    return series.rolling(n).mean()


def ema(series, n):
    return series.ewm(span=n, adjust=False).mean()


def rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def true_range(high, low, close):
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr


def atr(high, low, close, n=14):
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def macd_hist(close, fast=12, slow=26, signal=9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    return macd_line - signal_line


def adx(high, low, close, n=14):
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = true_range(high, low, close)

    tr_smooth = tr.ewm(alpha=1 / n, adjust=False).mean()
    plus_dm_smooth = pd.Series(plus_dm, index=high.index).ewm(alpha=1 / n, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=high.index).ewm(alpha=1 / n, adjust=False).mean()

    plus_di = 100 * (plus_dm_smooth / tr_smooth.replace(0, np.nan))
    minus_di = 100 * (minus_dm_smooth / tr_smooth.replace(0, np.nan))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1 / n, adjust=False).mean()
    return adx_val.fillna(0)


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["SMA_200"] = sma(df["CLOSE"], 200)
    df["RSI_14"] = rsi(df["CLOSE"], 14)
    df["ATR_14"] = atr(df["HIGH"], df["LOW"], df["CLOSE"], 14)
    df["MACD_HIST"] = macd_hist(df["CLOSE"])
    df["ADX_14"] = adx(df["HIGH"], df["LOW"], df["CLOSE"], 14)
    return df
