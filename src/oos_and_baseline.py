import os, sys, json
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategy import generate_signals
from backtest import BacktestConfig, run_backtest, compute_metrics

DATA_PATH = "data/bitcoin_hourly_indicators.csv"

def load_data():
    df = pd.read_csv(DATA_PATH)
    df["DATETIME"] = pd.to_datetime(df["DATETIME"])
    return df

def bh(df, cap):
    return (df["CLOSE"].iloc[-1] / df["CLOSE"].iloc[0] - 1.0) * 100

def run_on(df, cfg):
    sig = generate_signals(df.reset_index(drop=True))
    out, trades = run_backtest(sig, cfg)
    m = compute_metrics(out, trades, cfg)
    m["buy_hold_pct"] = bh(df, cfg.initial_capital)
    return m

def simple_sma_cross_signals(df):
    df = df.copy()
    df["trend_ok"] = df["SMA_50"] > df["SMA_200"]
    prev = df["trend_ok"].shift(1).fillna(False)
    df["entry_signal"] = df["trend_ok"] & (~prev)  # cruce hacia arriba de SMA50 sobre SMA200
    df["exit_trend_break"] = ~df["trend_ok"]
    df["ATR_14"] = df["ATR_14"]  # ya existe
    return df

def main():
    df = load_data()
    df = df[df["DATETIME"] >= "2018-01-01"].reset_index(drop=True)
    cfg = BacktestConfig()

    print("=========== 1) VALIDACION FUERA DE MUESTRA ===========")
    train = df[df["DATETIME"] < "2023-01-01"].reset_index(drop=True)
    test = df[df["DATETIME"] >= "2023-01-01"].reset_index(drop=True)

    m_train = run_on(train, cfg)
    m_test = run_on(test, cfg)
    print("TRAIN (2018-2022):", json.dumps(m_train, indent=2, default=str))
    print("TEST  (2023-hoy, no se toco nada al ajustar):", json.dumps(m_test, indent=2, default=str))

    print("\n=========== 2) BASELINE SIMPLE: CRUCE SMA50/SMA200 ===========")
    sma_df = simple_sma_cross_signals(df)
    out, trades = run_backtest(sma_df, cfg)
    m_sma = compute_metrics(out, trades, cfg)
    m_sma["buy_hold_pct"] = bh(df, cfg.initial_capital)
    print(json.dumps(m_sma, indent=2, default=str))

    results = {
        "out_of_sample": {"train_2018_2022": m_train, "test_2023_hoy": m_test},
        "baseline_sma_cross": m_sma,
    }
    with open("results/oos_and_baseline.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

if __name__ == "__main__":
    main()
