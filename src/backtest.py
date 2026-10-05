"""Motor de backtesting simple (long-only, un activo, una posicion a la vez).

Supuestos explicitos (documentados tambien en el reporte):
- Ejecucion sin look-ahead: la senal se calcula con el cierre de la vela t, la entrada se ejecuta
  al OPEN de la vela t+1 (no podemos comprar exactamente al precio que genero la senal).
- Comision: fee_rate por lado (entrada y salida), tipo spot Binance (0.1% = 0.001 por defecto).
- Slippage: se suma un slippage_bps adicional al precio de entrada/salida (peor para nosotros).
- Gestion de riesgo: se arriesga risk_per_trade del equity actual en cada operacion, calculado
  contra la distancia al stop-loss (ATR). Sin apalancamiento: el tamano de posicion nunca supera
  el 100% del equity disponible.
- Si en la misma vela se tocan stop-loss y take-profit, se asume que el stop-loss se ejecuta
  primero (supuesto conservador).
"""

from dataclasses import dataclass, field
import numpy as np
import pandas as pd


@dataclass
class BacktestConfig:
    initial_capital: float = 1000.0
    fee_rate: float = 0.001        # 0.1% por lado
    slippage_bps: float = 5.0      # 0.05% adicional en contra
    risk_per_trade: float = 0.02   # 2% del equity arriesgado por operacion
    atr_stop_mult: float = 1.5
    atr_tp_mult: float = 3.0


def run_backtest(df: pd.DataFrame, cfg: BacktestConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.reset_index(drop=True)
    n = len(df)

    cash = cfg.initial_capital  # efectivo NO invertido (separado de la posicion)
    equity_curve = np.empty(n)
    equity_curve[:] = np.nan

    in_position = False
    entry_price = stop_price = tp_price = 0.0
    position_btc = 0.0
    entry_idx = -1

    trades = []
    slip = cfg.slippage_bps / 10_000.0

    for i in range(n):
        row = df.iloc[i]

        if in_position:
            low, high, close = row["LOW"], row["HIGH"], row["CLOSE"]
            exit_price = None
            reason = None

            if low <= stop_price:
                exit_price = stop_price * (1 - slip)
                reason = "stop_loss"
            elif high >= tp_price:
                exit_price = tp_price * (1 - slip)
                reason = "take_profit"
            elif row["exit_trend_break"]:
                exit_price = close * (1 - slip)
                reason = "trend_break"

            if exit_price is not None:
                proceeds = position_btc * exit_price
                fee = proceeds * cfg.fee_rate
                cash += proceeds - fee  # el efectivo que ya teniamos aparte se conserva
                equity = cash
                trades.append({
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "entry_time": df.iloc[entry_idx]["DATETIME"],
                    "exit_time": row["DATETIME"],
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "reason": reason,
                    "pnl_pct": (exit_price / entry_price) - 1.0,
                    "equity_after": equity,
                })
                in_position = False
                position_btc = 0.0
            else:
                equity = cash + position_btc * close  # mark-to-market para la curva de equity

        if not in_position and row["entry_signal"] and i + 1 < n:
            nxt = df.iloc[i + 1]
            entry_price = nxt["OPEN"] * (1 + slip)
            atr = row["ATR_14"]
            if atr <= 0 or np.isnan(atr):
                equity_curve[i] = cash
                continue

            stop_price = entry_price - cfg.atr_stop_mult * atr
            tp_price = entry_price + cfg.atr_tp_mult * atr
            risk_amount = cash * cfg.risk_per_trade
            stop_dist = entry_price - stop_price
            if stop_dist <= 0:
                equity_curve[i] = cash
                continue

            btc_by_risk = risk_amount / stop_dist
            btc_by_capital = cash / entry_price  # no leverage
            position_btc = min(btc_by_risk, btc_by_capital)

            notional = position_btc * entry_price
            fee = notional * cfg.fee_rate
            cash -= (notional + fee)  # el resto (no invertido) se queda en cash
            entry_idx = i + 1
            in_position = True

        equity_curve[i] = cash + (position_btc * row["CLOSE"] if in_position else 0.0)

    df_out = df.copy()
    df_out["equity"] = equity_curve
    trades_df = pd.DataFrame(trades)
    return df_out, trades_df


def compute_metrics(df: pd.DataFrame, trades: pd.DataFrame, cfg: BacktestConfig) -> dict:
    equity = df["equity"].ffill().fillna(cfg.initial_capital)
    total_return = equity.iloc[-1] / cfg.initial_capital - 1.0

    days = (pd.to_datetime(df["DATETIME"].iloc[-1]) - pd.to_datetime(df["DATETIME"].iloc[0])).days
    years = max(days / 365.25, 1e-9)
    cagr = (equity.iloc[-1] / cfg.initial_capital) ** (1 / years) - 1.0

    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_drawdown = drawdown.min()

    daily_equity = equity.groupby(pd.to_datetime(df["DATETIME"]).dt.date).last()
    daily_returns = daily_equity.pct_change().dropna()
    sharpe = (
        (daily_returns.mean() / daily_returns.std()) * np.sqrt(365)
        if daily_returns.std() > 0
        else float("nan")
    )

    n_trades = len(trades)
    if n_trades > 0:
        wins = trades[trades["pnl_pct"] > 0]
        losses = trades[trades["pnl_pct"] <= 0]
        win_rate = len(wins) / n_trades
        avg_win = wins["pnl_pct"].mean() if len(wins) else 0.0
        avg_loss = losses["pnl_pct"].mean() if len(losses) else 0.0
        gross_win = (wins["pnl_pct"] * cfg.initial_capital).sum() if len(wins) else 0.0
        gross_loss = -(losses["pnl_pct"] * cfg.initial_capital).sum() if len(losses) else 0.0
        profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf")
    else:
        win_rate = avg_win = avg_loss = profit_factor = float("nan")

    return {
        "total_return_pct": total_return * 100,
        "cagr_pct": cagr * 100,
        "max_drawdown_pct": max_drawdown * 100,
        "sharpe_ratio": sharpe,
        "num_trades": n_trades,
        "win_rate_pct": win_rate * 100 if n_trades else float("nan"),
        "avg_win_pct": avg_win * 100,
        "avg_loss_pct": avg_loss * 100,
        "profit_factor": profit_factor,
        "final_equity": equity.iloc[-1],
        "years_tested": years,
    }
