"""
Descarga el histórico diario (2018-01-01 → hoy) de ETHUSDT y BNBUSDT desde la API
pública de Binance (sin cuenta ni API key) y lo guarda en data/ethusdt_daily.csv y
data/bnbusdt_daily.csv. Es de solo lectura: no toca ninguna cuenta ni coloca órdenes.

Uso (desde la raíz del repositorio):
    pip install requests
    python3 scripts/download_data.py
"""

import csv
import time
from datetime import datetime, timezone

import requests

SYMBOLS = ["ETHUSDT", "BNBUSDT"]
START = datetime(2018, 1, 1, tzinfo=timezone.utc)
INTERVAL = "1d"
OUT_DIR = "data"

COLUMNS = [
    "open_time", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME",
    "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
]


def fetch_symbol(symbol: str):
    start_ms = int(START.timestamp() * 1000)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    rows = []
    cursor = start_ms
    print(f"Descargando {symbol}...")
    while cursor < now_ms:
        resp = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": symbol, "interval": INTERVAL, "startTime": cursor, "limit": 1000},
            timeout=20,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        last_open_time = batch[-1][0]
        cursor = last_open_time + 24 * 60 * 60 * 1000  # siguiente dia
        print(f"  ... {len(rows)} velas hasta {datetime.fromtimestamp(last_open_time/1000, tz=timezone.utc).date()}")
        time.sleep(0.3)  # no saturar la API
        if len(batch) < 1000:
            break
    return rows


def save_csv(symbol: str, rows: list):
    path = f"{OUT_DIR}/{symbol.lower()}_daily.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["DATETIME"] + COLUMNS[1:6])
        for r in rows:
            dt = datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            writer.writerow([dt, r[1], r[2], r[3], r[4], r[5]])
    print(f"Guardado: {path} ({len(rows)} filas)")


def main():
    import os
    os.makedirs(OUT_DIR, exist_ok=True)
    for symbol in SYMBOLS:
        rows = fetch_symbol(symbol)
        save_csv(symbol, rows)
    print("\nListo. Archivos guardados en data/ethusdt_daily.csv y data/bnbusdt_daily.csv")


if __name__ == "__main__":
    main()
