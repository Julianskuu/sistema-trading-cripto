import os, sys, json
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from indicators import add_all_indicators
from backtest import BacktestConfig, run_backtest, compute_metrics
from simple_trend import simple_trend_signals


def load(path):
    df = pd.read_csv(path)
    df["DATETIME"] = pd.to_datetime(df["DATETIME"])
    return df


def bh(df):
    return (df["CLOSE"].iloc[-1] / df["CLOSE"].iloc[0] - 1.0) * 100


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
    cfg = BacktestConfig()
    results = {}
    for name, path in [("ETH", "data/ethusdt_daily.csv"), ("BNB", "data/bnbusdt_daily.csv")]:
        df = load(path)
        m_full, out, trades = evaluate(df, cfg, f"{name} FULL 2018-hoy (diario, solo SMA200)")
        results[f"{name}_full"] = m_full
        trades.to_csv(f"results/trades/trades_simple_trend_{name}.csv", index=False)

        train = df[df["DATETIME"] < "2023-01-01"].reset_index(drop=True)
        test = df[df["DATETIME"] >= "2023-01-01"].reset_index(drop=True)
        m_train, _, _ = evaluate(train, cfg, f"{name} TRAIN 2018-2022")
        m_test, _, _ = evaluate(test, cfg, f"{name} TEST 2023-hoy")
        results[f"{name}_oos_train"] = m_train
        results[f"{name}_oos_test"] = m_test

    with open("results/eth_bnb_validation.json", "w") as f:
        json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    main()
