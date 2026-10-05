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


def year_slices(df, warmup_days=210):
    """Cada 'ventana' es un año calendario, pero se le pasa al motor el historico
    completo hasta ese punto (para que la SMA_200 este bien calculada, sin 'huecos'
    al inicio de cada año), y luego se mide el resultado SOLO dentro de ese año."""
    years = sorted(df["DATETIME"].dt.year.unique())
    out = {}
    for y in years:
        year_start = pd.Timestamp(f"{y}-01-01")
        year_end = pd.Timestamp(f"{y}-12-31")
        window = df[df["DATETIME"] <= year_end].reset_index(drop=True)
        if len(window) < warmup_days + 5:
            continue
        out[y] = (window, year_start, year_end)
    return out


def evaluate_year(df_full, year_start, year_end, cfg):
    df = add_all_indicators(df_full)
    df = simple_trend_signals(df)
    out, trades = run_backtest(df, cfg)

    mask = (out["DATETIME"] >= year_start) & (out["DATETIME"] <= year_end)
    if mask.sum() < 2:
        return None
    sub = out[mask]
    start_equity = sub["equity"].ffill().iloc[0]
    # si no hay equity previa dentro del año (ffill desde afuera), usar la de la fila anterior a la ventana
    prior = out[out["DATETIME"] < year_start]
    if len(prior):
        start_equity = prior["equity"].ffill().iloc[-1]
    end_equity = sub["equity"].ffill().iloc[-1]
    year_return_pct = (end_equity / start_equity - 1.0) * 100 if start_equity > 0 else float("nan")

    price_start = df_full[df_full["DATETIME"] < year_start]["CLOSE"]
    price_start = price_start.iloc[-1] if len(price_start) else sub["CLOSE"].iloc[0]
    price_end = sub["CLOSE"].iloc[-1]
    bh_year_pct = (price_end / price_start - 1.0) * 100

    year_trades = trades[(trades["exit_time"] >= str(year_start)) & (trades["exit_time"] <= str(year_end))] if len(trades) else trades
    return {
        "strategy_pct": round(year_return_pct, 2),
        "buy_hold_pct": round(bh_year_pct, 2),
        "num_trades_closed_in_year": int(len(year_trades)) if len(trades) else 0,
    }


def main():
    cfg = BacktestConfig()
    all_results = {}
    for name, path in [("BTC", "data/bitcoin_hourly_indicators.csv"),
                         ("ETH", "data/ethusdt_daily.csv"),
                         ("BNB", "data/bnbusdt_daily.csv")]:
        if name == "BTC":
            raw = pd.read_csv(path, usecols=["DATETIME", "OPEN", "HIGH", "CLOSE", "LOW", "VOLUME"])
            raw["DATETIME"] = pd.to_datetime(raw["DATETIME"])
            raw = raw[raw["DATETIME"] >= "2018-01-01"].set_index("DATETIME")
            daily = pd.DataFrame({
                "OPEN": raw["OPEN"].resample("1D").first(),
                "HIGH": raw["HIGH"].resample("1D").max(),
                "LOW": raw["LOW"].resample("1D").min(),
                "CLOSE": raw["CLOSE"].resample("1D").last(),
                "VOLUME": raw["VOLUME"].resample("1D").sum(),
            }).dropna().reset_index()
        else:
            daily = load(path)

        yearly = {}
        for y, (window, ystart, yend) in year_slices(daily).items():
            res = evaluate_year(window, ystart, yend, cfg)
            if res:
                yearly[str(y)] = res
        all_results[name] = yearly
        print(f"\n=== {name}: retorno por año calendario (estrategia vs buy&hold) ===")
        for y, r in yearly.items():
            print(f"  {y}: estrategia {r['strategy_pct']:+.1f}%   buy&hold {r['buy_hold_pct']:+.1f}%   ({r['num_trades_closed_in_year']} operaciones cerradas ese año)")

    with open("results/walk_forward_yearly.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)


if __name__ == "__main__":
    main()
