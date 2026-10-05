import os, sys, json
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from indicators import add_all_indicators
from strategy import generate_signals
from backtest import BacktestConfig, run_backtest, compute_metrics

DATA_PATH = "data/bitcoin_hourly_indicators.csv"


def load_hourly():
    df = pd.read_csv(DATA_PATH, usecols=["DATETIME", "OPEN", "HIGH", "CLOSE", "LOW", "VOLUME"])
    df["DATETIME"] = pd.to_datetime(df["DATETIME"])
    df = df[df["DATETIME"] >= "2018-01-01"].set_index("DATETIME")
    return df


def resample(df, rule):
    out = pd.DataFrame({
        "OPEN": df["OPEN"].resample(rule).first(),
        "HIGH": df["HIGH"].resample(rule).max(),
        "LOW": df["LOW"].resample(rule).min(),
        "CLOSE": df["CLOSE"].resample(rule).last(),
        "VOLUME": df["VOLUME"].resample(rule).sum(),
    }).dropna()
    out = out.reset_index()
    return out


def bh(df):
    return (df["CLOSE"].iloc[-1] / df["CLOSE"].iloc[0] - 1.0) * 100


def evaluate(df, cfg, label):
    df = add_all_indicators(df)
    df = generate_signals(df)
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

    df_4h = resample(hourly, "4h")
    m4, out4, tr4 = evaluate(df_4h, cfg, "4H (2018-hoy)")
    results["4h_full"] = m4

    df_1d = resample(hourly, "1D")
    m1d, out1d, tr1d = evaluate(df_1d, cfg, "1D (2018-hoy)")
    results["1d_full"] = m1d

    # out-of-sample tambien en 4h y 1d
    for label, df_src in [("4h", df_4h), ("1d", df_1d)]:
        train = df_src[df_src["DATETIME"] < "2023-01-01"].reset_index(drop=True)
        test = df_src[df_src["DATETIME"] >= "2023-01-01"].reset_index(drop=True)
        m_train, _, _ = evaluate(train, cfg, f"{label} TRAIN 2018-2022")
        m_test, _, _ = evaluate(test, cfg, f"{label} TEST 2023-hoy")
        results[f"{label}_oos_train"] = m_train
        results[f"{label}_oos_test"] = m_test

    with open("results/multi_timeframe_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    tr4.to_csv("results/trades/trades_4h_full.csv", index=False)
    tr1d.to_csv("results/trades/trades_1d_full.csv", index=False)


if __name__ == "__main__":
    main()
