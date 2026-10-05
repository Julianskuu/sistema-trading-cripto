# Backtest v1 — Estrategia técnica BTC/USDT (horario) — 2026-09-13

## Resumen ejecutivo

Se construyó y probó contra 8.7 años de datos históricos horarios de BTC (2018 a hoy) una estrategia
long-only basada en indicadores técnicos (tendencia + momentum + fuerza de tendencia). **Resultado: la
estrategia perdió -55% del capital en el periodo completo, mientras que simplemente comprar y mantener
BTC (buy & hold) habría generado +466%.** Es decir, en su forma actual, el sistema no solo no gana dinero
de forma consistente, sino que le va peor que no hacer nada.

Esto no es un resultado "malo" en el sentido de que el ejercicio haya fallado — es exactamente para esto
que sirve el backtesting: para descubrir esto con dinero ficticio, no con dinero real. **Recomendación:
no llevar esta versión a producción ni a paper trading todavía.**

## Qué se construyó

- **Datos**: velas horarias de BTC/USD desde 2010 hasta hoy (recientes hasta 2026-09-13), con 70+
  indicadores técnicos pre-calculados (medias móviles, RSI, MACD, ADX, ATR, Bollinger Bands, etc.),
  obtenidos de un dataset público (ver "Fuente de datos" abajo).
- **Estrategia (long-only, un activo, una posición a la vez)**:
  - Entrada: tendencia de fondo alcista (precio > SMA_200) **y** ADX_14 > 20 (mercado con tendencia,
    no lateral) **y** MACD histograma mejorando **y** RSI_14 saliendo de sobreventa (cruza hacia arriba
    el nivel 35) — es decir, comprar un retroceso dentro de una tendencia alcista más amplia.
  - Salida: lo primero que ocurra entre stop-loss (1.5×ATR bajo el precio de entrada), take-profit
    (3×ATR sobre el precio de entrada), o ruptura de tendencia (cierre por debajo de la SMA_200).
  - Gestión de riesgo: se arriesga 2% del capital disponible por operación (tamaño de posición calculado
    contra la distancia al stop), sin apalancamiento.
- **Motor de backtesting**: simula comisión (0.1% por lado) y slippage (0.05% adicional), ejecuta la
  entrada en la apertura de la vela siguiente a la señal (para no "ver el futuro"), y por defecto asume
  que si en una misma vela se tocan el stop y el take-profit, se ejecuta primero el stop (supuesto
  conservador).

## Un bug real que se encontró y corrigió en el camino

La primera versión del motor de backtesting no llevaba por separado el "efectivo no invertido": cuando
el tamaño de posición usaba menos del 100% del capital (por el cálculo de riesgo), esa porción no
invertida se perdía silenciosamente al cerrar cada operación. Esto hacía ver pérdidas ~2-5 veces más
grandes de lo real (el resultado inicial daba -99.99% de pérdida total, claramente irreal). Se corrigió
llevando un balance de "cash" separado de la posición. Se documenta esto por transparencia: **todo
backtest debe revisarse con esta clase de escepticismo antes de confiar en sus números.**

## Resultados

| Periodo | Retorno estrategia | Buy & Hold BTC | Máx. drawdown estrategia | # Operaciones | Win rate | Profit factor |
|---|---|---|---|---|---|---|
| **2018 – hoy (completo, 8.7 años)** | **-55.1%** | **+466.5%** | -56.1% | 240 | 25.8% | 0.86 |
| 2018-2019 (bajista/lateral) | -24.1% | -46.9% | -27.6% | 55 | 25.5% | 0.61 |
| 2020-2021 (alcista fuerte) | -2.7% | +556.3% | -17.4% | 61 | 31.1% | 1.28 |
| 2022 (crash) | -19.1% | -64.5% | -19.6% | 25 | 12.0% | 0.21 |
| 2023-2025 (recuperación/alcista) | -17.5% | +433.7% | -21.1% | 78 | 28.2% | 1.00 |
| 2026 (parcial) | -8.9% | -11.9% | -10.9% | 21 | 19.0% | 0.58 |

Ver `results/equity_curve.png` para el gráfico (equity en escala log vs. buy & hold, y drawdown).

## Lectura honesta de los resultados

- La estrategia **sí amortigua pérdidas en mercados bajistas/crash** (2018-19 y 2022: pierde menos que
  simplemente sostener BTC). Eso es el comportamiento esperado de un sistema que sale cuando la tendencia
  se rompe.
- Pero **destruye valor en los mercados alcistas fuertes** (2020-21 y 2023-25), que es justamente donde
  BTC ha generado casi todo su retorno histórico — el sistema entra y sale demasiadas veces (whipsaw),
  pagando comisiones y perdiendo las tendencias grandes por salir con la ruptura de SMA_200 o por
  golpear el stop en retrocesos normales dentro de la tendencia.
- **Neto: en 8.7 años el sistema pierde dinero, en términos absolutos y muchísimo más en términos
  relativos frente a no operar.** Con un win rate de 25.8% y profit factor de 0.86 (por debajo de 1), la
  estrategia tiene actualmente una expectativa negativa por operación.

## Limitaciones importantes (léelas antes de sacar conclusiones)

1. **No es validación fuera de muestra**: los parámetros (ADX>20, RSI 35, ATR×1.5/×3) se fijaron por
   lógica de diseño, no se optimizaron buscando el mejor resultado — pero tampoco se validaron con una
   partición entrenamiento/prueba real. Si se empiezan a ajustar parámetros mirando estos mismos
   resultados para "mejorarlos", se cae en sobreajuste (overfitting): un sistema que luce bien en el
   pasado exacto que ya conocemos, pero que no tiene por qué funcionar en datos nuevos.
2. **Fuente de datos**: el CSV usado viene de CryptoCompare (vía un dataset público), no directamente de
   Binance — los precios de BTC/USD entre exchanges son muy similares pero no idénticos. No se pudo usar
   la API de Binance directamente por la restricción de red descrita abajo.
3. **Supuestos de ejecución optimistas**: se asume que siempre se puede ejecutar exactamente al precio
   de stop/take-profit sin importar el tamaño de la orden (sin impacto de mercado), lo cual en la
   realidad —sobre todo en movimientos rápidos— no siempre se cumple.
4. **Un solo activo, un marco temporal**: no se probaron otros pares, ni otros timeframes (4h, diario),
   ni combinaciones de varias señales ponderadas — hay bastante espacio de diseño sin explorar todavía.
5. **La señal de "otros traders" no está implementada**: el código deja un lugar reservado
   (`external_signal`) para eso, pero hoy no hay una fuente de datos accesible para poblarla (ver abajo).

## Próximos pasos que se plantearon en ese momento

(Nota: los pasos 2 y 3 se hicieron después; ver el README.)

1. **No usar esta versión con dinero real ni siquiera en paper trading todavía** — el backtest dice que
   pierde contra no hacer nada.
2. Explorar variantes: separar "cuándo entrar" de "cuándo salir" de forma menos rígida, probar otros
   timeframes (4h/diario, menos ruido/whipsaw), o comparar contra una regla mucho más simple (ej. solo
   SMA_50/SMA_200 cross, sin tantos filtros) como referencia.
3. Hacer validación fuera de muestra real: ajustar parámetros solo con una parte del histórico (ej.
   2018-2022) y probar "a ciegas" en el resto (2023-hoy), para saber si el ajuste generaliza.
4. Diseñar cómo incorporar señales de otros traders de forma confiable (hoy no resuelto ni con fuente de
   datos definida).

## Archivos de este backtest

- `src/strategy.py` — reglas de la estrategia.
- `src/backtest.py` — motor de backtesting (con el fix de contabilidad de cash).
- `src/run_backtest.py` — script que corre todo y genera el reporte.
- `data/bitcoin_hourly_indicators.csv` — datos históricos usados (~150MB, no incluidos; ver README).
- `results/trades_full_period.csv` — registro de las 240 operaciones del periodo completo.
- `results/metrics_by_period.json` — métricas en formato JSON.
- `results/equity_curve.png` — gráfico de equity y drawdown.

## Fuente de datos

Dataset público "Bitcoin Technical Indicators Dataset" (actualizado diariamente), sourced from
CryptoCompare API — https://github.com/mouadja02/bitcoin-technical-indicators-dataset
