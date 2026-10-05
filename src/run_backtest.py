import os, sys
import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategy import generate_signals
from backtest import BacktestConfig, run_backtest, compute_metrics

DATA_PATH = "data/bitcoin_hourly_indicators.csv"
REPORTS_DIR = "results"

def load_data(start="2018-01-01"):
    df = pd.read_csv(DATA_PATH)
    df["DATETIME"] = pd.to_datetime(df["DATETIME"])
    df = df[df["DATETIME"] >= start].reset_index(drop=True)
    return df

def buy_and_hold(df, initial_capital):
    start_price = df["CLOSE"].iloc[0]
    end_price = df["CLOSE"].iloc[-1]
    return (end_price / start_price - 1.0) * 100, initial_capital * (end_price / start_price)

def period_slices(df):
    periods = {
        "2018-2019 (bear/lateral)": ("2018-01-01", "2019-12-31"),
        "2020-2021 (bull)": ("2020-01-01", "2021-12-31"),
        "2022 (bear/crash)": ("2022-01-01", "2022-12-31"),
        "2023-2025 (recuperacion/bull)": ("2023-01-01", "2025-12-31"),
        "2026 YTD": ("2026-01-01", "2026-12-31"),
    }
    out = {}
    for name, (s, e) in periods.items():
        sub = df[(df["DATETIME"] >= s) & (df["DATETIME"] <= e)]
        if len(sub) > 200:
            out[name] = sub.reset_index(drop=True)
    return out

def main():
    df = load_data()
    df = generate_signals(df)
    cfg = BacktestConfig()

    df_out, trades = run_backtest(df, cfg)
    metrics = compute_metrics(df_out, trades, cfg)
    bh_return_pct, bh_final = buy_and_hold(df, cfg.initial_capital)

    print("=== RESULTADO GLOBAL (2018 - hoy) ===")
    print(json.dumps(metrics, indent=2, default=str))
    print(f"Buy & Hold: {bh_return_pct:.1f}% -> equity final {bh_final:.2f}")

    trades.to_csv(f"{REPORTS_DIR}/trades_full_period.csv", index=False)

    # Metricas por sub-periodo
    per_period = {}
    for name, sub in period_slices(df).items():
        sub_signals = generate_signals(sub)
        sub_out, sub_trades = run_backtest(sub_signals, cfg)
        m = compute_metrics(sub_out, sub_trades, cfg)
        bh_p, _ = buy_and_hold(sub, cfg.initial_capital)
        m["buy_hold_return_pct"] = bh_p
        per_period[name] = m
        print(f"\n=== {name} ===")
        print(json.dumps(m, indent=2, default=str))

    with open(f"{REPORTS_DIR}/metrics_by_period.json", "w") as f:
        json.dump({"global": metrics, "buy_and_hold_global_pct": bh_return_pct, "by_period": per_period}, f, indent=2, default=str)

    # --- Graficos ---
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})

    ax1 = axes[0]
    ax1.plot(df_out["DATETIME"], df_out["equity"].ffill(), label="Estrategia", color="#2563eb", linewidth=1.2)
    bh_curve = cfg.initial_capital * (df["CLOSE"] / df["CLOSE"].iloc[0])
    ax1.plot(df["DATETIME"], bh_curve, label="Buy & Hold BTC", color="#9ca3af", linewidth=1.0, linestyle="--")
    ax1.set_yscale("log")
    ax1.set_ylabel("Equity (USD, escala log)")
    ax1.set_title("Backtest BTC/USDT horario (2018-presente): estrategia vs. buy & hold")
    ax1.legend()
    ax1.grid(alpha=0.3)

    equity_filled = df_out["equity"].ffill().fillna(cfg.initial_capital)
    running_max = equity_filled.cummax()
    drawdown = (equity_filled - running_max) / running_max * 100
    ax2 = axes[1]
    ax2.fill_between(df_out["DATETIME"], drawdown, 0, color="#dc2626", alpha=0.4)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Fecha")
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{REPORTS_DIR}/equity_curve.png", dpi=150)
    print(f"\nGrafico guardado en {REPORTS_DIR}/equity_curve.png")

if __name__ == "__main__":
    main()
