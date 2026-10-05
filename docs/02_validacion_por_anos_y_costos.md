# Validación por años + costos reales (comisiones + impuestos) — 2026-09-13

## 1) Desempeño año por año (walk-forward por ventanas anuales)

En vez de un solo split train/test, se midió el resultado calendario por año (2018-2026), usando en
cada punto todo el histórico disponible hasta ahí (sin mirar el futuro).

### BTC
| Año | Estrategia | Buy & Hold | Operaciones cerradas |
|---|---|---|---|
| 2018 | +0.0% | -72.1% | 0 |
| 2019 | +18.0% | +91.7% | 18 |
| 2020 | +47.2% | +303.3% | 26 |
| 2021 | **-12.2%** | +59.5% | 29 |
| 2022 | +0.0% | -64.2% | 0 |
| 2023 | +25.6% | +155.8% | 21 |
| 2024 | +24.0% | +120.9% | 28 |
| 2025 | -11.4% | -6.3% | 28 |
| 2026 (parcial) | +3.1% | -11.7% | 1 |

### ETH
| Año | Estrategia | Buy & Hold |
|---|---|---|
| 2018 | +0.0% | -82.6% |
| 2019 | +2.5% | -1.7% |
| 2020 | +24.3% | +470.2% |
| 2021 | +32.9% | +399.2% |
| 2022 | -3.3% | -67.5% |
| 2023 | +13.4% | +90.8% |
| 2024 | +9.9% | +46.3% |
| 2025 | +4.0% | -11.0% |
| 2026 (parcial) | +2.5% | -15.2% |

### BNB
| Año | Estrategia | Buy & Hold |
|---|---|---|
| 2018 | -3.7% | -27.7% |
| 2019 | +12.1% | +124.5% |
| 2020 | +0.6% | +172.4% |
| 2021 | +36.4% | +1268.9% |
| 2022 | -4.0% | -51.8% |
| 2023 | +5.5% | +26.6% |
| 2024 | +1.4% | +125.2% |
| 2025 | +4.7% | +23.1% |
| 2026 (parcial) | +4.6% | -16.0% |

**Lectura honesta**: el patrón se repite año tras año y activo tras activo — protege fuerte en los años de
crash (2018, 2022) y se queda corto en los años de subida explosiva (2020, 2021, 2024). El único año
realmente malo es **BTC 2021 (-12.2%)**, con una racha de whipsaw durante la corrección de mediados de
2021 (mayo-julio) que generó varias entradas/salidas seguidas con pérdida. 2025 también fue flojo en BTC
(-11.4%) en un año lateral/bajista. No es un patrón perfecto, pero es consistente y explicable, no errático.

## 2) Costos reales: comisiones (ya incluidas) + impuestos (nuevo)

**Comisiones y slippage**: el backtest YA incluye 0.1% de comisión por lado (estándar de Binance spot sin
descuento por pagar con BNB; con ese descuento sería 0.075%, así que si algo el backtest es ligeramente
conservador) más 0.05% de slippage adicional en contra. No hay ningún costo oculto de este lado.

**Impuestos en Colombia** (esto no es asesoría fiscal):
según la normativa vigente, las ganancias de trading frecuente de criptomonedas (activos mantenidos menos
de 2 años, que es el caso de esta estrategia) tributan como **renta ordinaria** en la declaración de renta,
a tarifa progresiva de hasta 35-39% según el total de ingresos del año (salario + trading combinados) —
NO como "ganancia ocasional" al 15% fijo, esa tarifa favorable solo aplica si se mantiene el activo 2 años
o más. Además, desde la Resolución 000240 de 2025, exchanges registrados como Binance ya reportan
directamente las operaciones a la DIAN.

Ejemplo ilustrativo sobre la ganancia bruta de 8.7 años (ya neta de comisiones):

| Activo | Ganancia bruta (post-comisiones) | Neta con 19% de impuesto | Neta con 35% de impuesto |
|---|---|---|---|
| BTC | +117.2% ($1172) | +94.9% ($949) | +76.2% ($762) |
| ETH | +117.6% ($1176) | +95.2% ($952) | +76.4% ($764) |
| BNB | +66.5% ($665) | +53.8% ($538) | +43.2% ($432) |

(0%, 19% y 35% son solo puntos de referencia: la tarifa real depende de los ingresos totales del año
de cada persona y debe verificarse con un contador.)

**Conclusión de esta ronda**: incluso después de comisiones e impuestos ilustrativos, el sistema sigue
dando retorno neto positivo en los tres activos sobre 8.7 años — pero la rentabilidad "real, en el bolsillo"
es notablemente menor que el número bruto del backtest, y hay que declarar y pagar sobre cada ganancia
realizada, no solo al final.
