"""Estrategia minimalista: estar comprado mientras CLOSE > SMA_200, plano en caso contrario.
Sin RSI, sin ADX, sin MACD -- solo seguir la tendencia de fondo. Sirve para saber si el exceso
de filtros de la v1/v2 estaba costando mas de lo que protegia.
"""
import os, sys, json
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from indicators import add_all_indicators
from backtest import BacktestConfig, run_backtest, compute_metrics
from multi_timeframe import load_hourly, resample, bh


def simple_trend_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["trend_ok"] = df["CLOSE"] > df["SMA_200"]
    # Nota (corregida 2026-09-28): la version anterior intentaba entrar "solo al
    # cruzar hacia arriba" con `trend_ok & ~trend_ok.shift(1).fillna(False)`, pero
    # shift() convierte la serie booleana a dtype object y `~` sobre objetos es el
    # NOT bit a bit de Python (~True == -2, ~False == -1: ambos "verdaderos"). En la
    # practica la condicion era simplemente `trend_ok`. Todos los resultados
    # publicados se obtuvieron con ese comportamiento real, que aqui se deja
    # explicito: mientras el precio este sobre la SMA_200, si no hay posicion
    # abierta (p. ej. tras un stop-loss o take-profit) se abre una nueva.
    df["entry_signal"] = df["trend_ok"]
    df["exit_trend_break"] = ~df["trend_ok"]
    return df


def evaluate(df, cfg, label):
    df = add_all_indicators(df)
    df = simple_trend_signals(df)
    out, trades = run_backtest(df, cfg)
    m = compute_metrics(out, trades, cfg)
    m["buy_hold_pct"] = bh(df)
    print(f"\n=== {label} ===")
    print(json.dumps(m, indent=2, default=str))
    return m, out, trades


def main():
    hourly = load_hourly()
    cfg = BacktestConfig()
    results = {}

    for label, rule in [("1h", None), ("4h", "4h"), ("1d", "1D")]:
        df_src = hourly.reset_index() if rule is None else resample(hourly, rule)
        m_full, out, trades = evaluate(df_src, cfg, f"{label} FULL 2018-hoy")
        results[f"{label}_full"] = m_full
        trades.to_csv(f"results/trades/trades_simple_trend_{label}.csv", index=False)

        train = df_src[df_src["DATETIME"] < "2023-01-01"].reset_index(drop=True)
        test = df_src[df_src["DATETIME"] >= "2023-01-01"].reset_index(drop=True)
        m_train, _, _ = evaluate(train, cfg, f"{label} TRAIN 2018-2022")
        m_test, _, _ = evaluate(test, cfg, f"{label} TEST 2023-hoy")
        results[f"{label}_oos_train"] = m_train
        results[f"{label}_oos_test"] = m_test

    with open("results/simple_trend_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    main()
