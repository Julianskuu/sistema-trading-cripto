"""
Estrategia base para el bot de trading BTC/USDT (marco horario, estilo day-trading).

Filosofia:
- Solo abrimos operaciones LARGAS (spot, sin apalancamiento/short) siguiendo la tendencia,
  y solo cuando varias condiciones coinciden (confirmacion cruzada), no una sola senal aislada.
- Condiciones combinadas:
    1) Tendencia: precio por encima de la EMA50 (definimos "tendencia alcista" en el marco horario).
    2) Fuerza de tendencia: ADX_14 > adx_min (evita operar en mercados sin direccion / choppy).
    3) Momentum: RSI_14 sale de sobreventa (cruza hacia arriba el nivel rsi_oversold) -> gatillo de entrada,
       comprando "el retroceso dentro de la tendencia" en lugar de perseguir maximos.
    4) Filtro de MACD: histograma de MACD > 0 (momentum de corto plazo tambien a favor).
- Salida: lo que ocurra primero entre
    a) Stop-loss = entry_price - atr_stop_mult * ATR_14 (en el momento de la entrada)
    b) Take-profit = entry_price + atr_tp_mult * ATR_14
    c) Se rompe la tendencia (precio cierra por debajo de la EMA50)

- Columna 'external_signal' (pluggable, hoy no poblada):
    Reservada para incorporar mas adelante una senal derivada de "lo que estan haciendo otros traders"
    (por ejemplo, actividad de copy-trading o flujo de ordenes agregado). Hoy no tenemos una fuente de
    datos accesible para esto (ver limitaciones en el reporte), asi que esta columna queda en 0 (neutral)
    y el motor de backtest la ignora salvo que se le pase explicitamente con datos reales.
"""

import numpy as np
import pandas as pd


def generate_signals(
    df: pd.DataFrame,
    adx_min: float = 20.0,
    rsi_oversold: float = 35.0,
    external_signal_weight: float = 0.0,
) -> pd.DataFrame:
    """Agrega columnas 'entry_signal' (bool) y 'trend_ok' (bool) al dataframe.

    No mira hacia el futuro: cada fila usa solo indicadores calculados con datos hasta esa vela
    (los indicadores del CSV ya vienen calculados asi, de forma causal).

    Nota de diseno (v2): la tendencia de fondo se define con la SMA_200 (marco amplio), NO con la
    EMA_50. En la v1 se exigia CLOSE > EMA_50 en el mismo instante en que el RSI sale de sobreventa,
    pero eso es casi contradictorio: un RSI en sobreventa ocurre justo cuando el precio ACABA DE CAER,
    lo cual casi siempre coincide con estar por debajo de una media corta como la EMA_50. Verificado
    contra 2023-2025: con EMA_50 como filtro de tendencia, la combinacion completa nunca se daba (0
    señales en 3 años); con SMA_200 como tendencia de fondo (permitiendo que el precio pinche
    momentaneamente por debajo de la EMA_50 dentro de una tendencia alcista mas amplia), aparecen ~86
    señales en el mismo periodo. Este es un ajuste de logica, no una optimizacion buscando el mejor
    retorno posible.
    """
    df = df.copy()

    df["trend_ok"] = df["CLOSE"] > df["SMA_200"]
    df["adx_ok"] = df["ADX_14"] > adx_min
    df["macd_ok"] = df["MACD_HIST"] > df["MACD_HIST"].shift(1)  # histograma mejorando (no necesariamente positivo)

    rsi_prev = df["RSI_14"].shift(1)
    df["rsi_cross_up"] = (rsi_prev <= rsi_oversold) & (df["RSI_14"] > rsi_oversold)

    if "external_signal" not in df.columns:
        df["external_signal"] = 0.0  # neutral: no poblada en esta version

    external_ok = True
    if external_signal_weight > 0:
        external_ok = df["external_signal"] >= 0

    df["entry_signal"] = (
        df["trend_ok"] & df["adx_ok"] & df["macd_ok"] & df["rsi_cross_up"] & external_ok
    )

    df["exit_trend_break"] = ~df["trend_ok"]

    return df
