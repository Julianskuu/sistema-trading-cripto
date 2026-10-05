#!/usr/bin/env python3
"""
paper_trader.py — Bot de paper trading BTC/USDT sobre Binance Spot TESTNET.

Estrategia: SMA_200 diaria, long-only, sin filtros (la misma validada en el
backtest del proyecto "IA trading").
  - CLOSE diario > SMA_200 diaria -> COMPRADO/LARGO (mantener/entrar en BTC)
  - CLOSE diario < SMA_200 diaria -> FUERA/EFECTIVO (mantener/salir a USDT)

Este script está pensado para correr UNA VEZ AL DÍA (vía launchd, ver instalar_launchd.sh), después del
cierre de la vela diaria (00:05 UTC aprox). Cada corrida:
  1. Trae las últimas ~250 velas diarias de BTCUSDT desde el mercado REAL de
     Binance (endpoint público, solo datos, no requiere autenticación ni
     toca ninguna cuenta) -- el testnet no tiene suficiente historial diario
     para calcular una SMA_200, así que el precio/historial se lee del
     mercado real y las ÓRDENES se ejecutan en el testnet (dinero falso).
  2. Calcula la SMA_200 y la señal de hoy.
  3. Si la señal cambió respecto al último estado guardado -> ejecuta la orden
     de mercado correspondiente en testnet (comprar todo el USDT disponible,
     o vender todo el BTC disponible).
  4. Si no cambió, no hace nada (solo registra el día en el log).
  5. Guarda todo en trade_log.csv y actualiza state.json.

IMPORTANTE: las ÓRDENES corren contra TESTNET (dinero falso). No toca tu
cuenta real de Binance en ningún momento -- las credenciales de testnet son
distintas y separadas de tus API keys reales. Solo la LECTURA del precio
histórico usa el endpoint público del mercado real (sin login, sin keys,
sin poder operar nada ahí).

Uso:
    python3 paper_trader.py                # corrida normal (ejecuta orden si corresponde)
    python3 paper_trader.py --dry-run       # solo calcula y muestra, no ordena ni guarda estado
    python3 paper_trader.py --force         # ignora el chequeo de "ya corrió hoy" (para pruebas)
"""

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv es opcional; si no está, se usan variables de entorno del sistema

# El Python 3.9 del sistema en macOS usa LibreSSL y urllib3 muestra un warning
# (NotOpenSSLWarning) en cada corrida. Es inofensivo; lo silenciamos para que
# el log quede limpio.
warnings.filterwarnings("ignore", message=".*OpenSSL.*")

import requests
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException, BinanceRequestException

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

SYMBOL = "BTCUSDT"
BASE_ASSET = "BTC"
QUOTE_ASSET = "USDT"
SMA_PERIOD = 200
KLINES_LIMIT = 250  # margen extra sobre SMA_PERIOD por si faltan velas

# Red: Binance a veces tarda en responder (el 2026-09 hubo 2 fallos por
# ReadTimeout con el timeout por defecto de 10s). Timeout más largo +
# reintentos con espera creciente SOLO para lecturas (nunca para órdenes).
REQUEST_TIMEOUT = 30          # segundos por request
REINTENTOS = 4                # intentos totales por lectura
ESPERA_BASE_SEG = 10          # espera 10s, 20s, 40s entre intentos
ERRORES_RED = (requests.exceptions.RequestException, BinanceRequestException,
               BinanceAPIException, OSError)

SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE = SCRIPT_DIR / "state.json"
LOG_FILE = SCRIPT_DIR / "trade_log.csv"

LOG_HEADERS = [
    "timestamp_utc", "fecha_vela", "close", "sma_200", "distancia_pct",
    "senal", "senal_previa", "cambio_senal", "accion", "precio_ejecucion",
    "cantidad", "usdt_libre_despues", "btc_libre_despues", "order_id", "nota",
]


def log_row(row: dict) -> None:
    is_new = not LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_HEADERS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_signal": None, "last_run_date": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def con_reintentos(fn, descripcion: str):
    """Ejecuta una LECTURA a Binance con reintentos. No usar para órdenes:
    reintentar una orden tras un timeout podría duplicarla."""
    for intento in range(1, REINTENTOS + 1):
        try:
            return fn()
        except ERRORES_RED as e:
            if intento == REINTENTOS:
                raise
            espera = ESPERA_BASE_SEG * 2 ** (intento - 1)
            print(f"[{descripcion}] intento {intento}/{REINTENTOS} falló "
                  f"({type(e).__name__}); reintento en {espera}s", file=sys.stderr)
            time.sleep(espera)


def notificar_mac(titulo: str, mensaje: str) -> None:
    """Notificación nativa de macOS (no hace nada en otros sistemas)."""
    if sys.platform != "darwin":
        return
    titulo = titulo.replace('"', "'")
    mensaje = mensaje.replace('"', "'")
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "{mensaje}" with title "{titulo}" sound name "Glass"'],
                       check=False, timeout=10)
    except Exception:
        pass


def round_step_size(quantity: float, step_size: str) -> float:
    """Redondea una cantidad hacia abajo al step size que exige Binance (LOT_SIZE)."""
    step = float(step_size)
    precision = int(round(-math.log10(step))) if step < 1 else 0
    return math.floor(quantity / step) * step if precision >= 0 else quantity


def get_client() -> Client:
    api_key = os.environ.get("BINANCE_TESTNET_API_KEY")
    api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET")
    if not api_key or not api_secret:
        sys.exit(
            "Faltan BINANCE_TESTNET_API_KEY / BINANCE_TESTNET_API_SECRET.\n"
            "Definilas como variables de entorno o en un archivo .env junto a este script."
        )
    return Client(api_key, api_secret, testnet=True,
                  requests_params={"timeout": REQUEST_TIMEOUT})


def get_market_data_client() -> Client:
    """Cliente sin autenticar contra el mercado REAL de Binance, solo para
    datos públicos (klines). No requiere API key/secret y no puede operar
    nada -- el testnet no guarda suficiente historial diario para la SMA_200."""
    return Client(requests_params={"timeout": REQUEST_TIMEOUT})


def fetch_daily_data(market_client: Client):
    klines = market_client.get_klines(
        symbol=SYMBOL, interval=Client.KLINE_INTERVAL_1DAY, limit=KLINES_LIMIT
    )
    # Cada kline: [open_time, open, high, low, close, volume, close_time, ...]
    closes = [float(k[4]) for k in klines]
    close_times = [k[6] for k in klines]

    # La última vela puede estar en curso (todavía no cerró) -> la descartamos
    # y usamos la última vela completa, igual que en la señal diaria del proyecto.
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if close_times[-1] > now_ms:
        closes = closes[:-1]
        close_times = close_times[:-1]

    if len(closes) < SMA_PERIOD:
        sys.exit(f"No hay suficientes velas diarias para calcular SMA_{SMA_PERIOD} (hay {len(closes)}).")

    last_close = closes[-1]
    sma_200 = sum(closes[-SMA_PERIOD:]) / SMA_PERIOD
    last_close_time = datetime.fromtimestamp(close_times[-1] / 1000, tz=timezone.utc)

    return last_close, sma_200, last_close_time


def get_free_balance(client: Client, asset: str) -> float:
    bal = con_reintentos(lambda: client.get_asset_balance(asset=asset), f"balance {asset}")
    return float(bal["free"]) if bal else 0.0


def get_lot_step_size(client: Client, symbol: str) -> str:
    info = con_reintentos(lambda: client.get_symbol_info(symbol), "info símbolo")
    for f in info["filters"]:
        if f["filterType"] == "LOT_SIZE":
            return f["stepSize"]
    return "0.00001"  # fallback conservador


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Solo calcula y muestra, no ejecuta ni guarda estado")
    parser.add_argument("--force", action="store_true", help="Ignora el chequeo de 'ya corrió hoy'")
    args = parser.parse_args()

    state = load_state()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not args.force and state.get("last_run_date") == today_str:
        # launchd lo ejecuta cada hora; solo avisamos si lo corrés a mano en la terminal.
        if sys.stdout.isatty():
            print(f"Ya corrió hoy ({today_str}). Usá --force si querés forzar otra corrida.")
        return

    print(f"=== Corrida {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ===")

    try:
        client = con_reintentos(get_client, "conexión testnet")
        market_client = con_reintentos(get_market_data_client, "conexión mercado real")
        close, sma_200, vela_fecha = con_reintentos(lambda: fetch_daily_data(market_client), "velas diarias")
    except ERRORES_RED as e:
        # No se guarda estado: la próxima ejecución (en ~1 hora) lo vuelve a intentar.
        print(f"ERROR: no se pudo conectar a Binance tras {REINTENTOS} intentos "
              f"({type(e).__name__}: {e}). Se reintenta en la próxima ejecución.", file=sys.stderr)
        sys.exit(1)

    distancia_pct = (close - sma_200) / sma_200 * 100
    senal = "COMPRADO" if close > sma_200 else "FUERA"
    senal_previa = state.get("last_signal")
    cambio = senal_previa is not None and senal != senal_previa

    print(f"Vela: {vela_fecha.date()} | Close: {close:.2f} | SMA_200: {sma_200:.2f} "
          f"({distancia_pct:+.2f}%) | Señal: {senal} | Previa: {senal_previa} | Cambió: {cambio}")

    if cambio and not args.dry_run:
        que_hacer = ("Regla real: vender el 50% de tu BTC a USDT." if senal == "FUERA"
                     else "Regla real: recomprar BTC con el USDT de la venta.")
        notificar_mac(f"CAMBIO DE SEÑAL BTC: {senal}",
                      f"Cierre {close:,.0f} vs SMA200 {sma_200:,.0f} ({distancia_pct:+.1f}%). {que_hacer}")

    accion = "NINGUNA"
    precio_ejecucion = ""
    cantidad = ""
    order_id = ""
    nota = ""

    if args.dry_run:
        nota = "dry-run: no se ejecutó ninguna orden ni se guardó estado"
        print(nota)
    else:
        # Solo operamos si la señal cambió (o si es la primera corrida, para
        # arrancar alineados con la señal actual).
        primera_corrida = senal_previa is None
        if cambio or primera_corrida:
            try:
                if senal == "COMPRADO":
                    usdt_libre = get_free_balance(client, QUOTE_ASSET)
                    if usdt_libre < 10:
                        nota = f"USDT libre insuficiente para comprar ({usdt_libre:.2f})"
                        print(nota)
                    else:
                        order = client.order_market_buy(symbol=SYMBOL, quoteOrderQty=round(usdt_libre, 2))
                        accion = "COMPRA"
                        order_id = order.get("orderId", "")
                        fills = order.get("fills", [])
                        if fills:
                            precio_ejecucion = fills[0]["price"]
                        cantidad = order.get("executedQty", "")
                        print(f"Orden de COMPRA ejecutada: {order}")
                else:  # FUERA -> vender todo el BTC
                    btc_libre = get_free_balance(client, BASE_ASSET)
                    step_size = get_lot_step_size(client, SYMBOL)
                    qty = round_step_size(btc_libre, step_size)
                    if qty <= 0:
                        nota = f"BTC libre insuficiente para vender ({btc_libre})"
                        print(nota)
                    else:
                        order = client.order_market_sell(symbol=SYMBOL, quantity=qty)
                        accion = "VENTA"
                        order_id = order.get("orderId", "")
                        fills = order.get("fills", [])
                        if fills:
                            precio_ejecucion = fills[0]["price"]
                        cantidad = order.get("executedQty", "")
                        print(f"Orden de VENTA ejecutada: {order}")
            except (BinanceAPIException, BinanceOrderException) as e:
                nota = f"Error ejecutando orden: {e}"
                print(nota, file=sys.stderr)
        else:
            nota = "Señal sin cambios, no se opera"
            print(nota)

        state["last_signal"] = senal
        state["last_run_date"] = today_str
        save_state(state)

    usdt_despues = ""
    btc_despues = ""
    if not args.dry_run:
        try:
            usdt_despues = get_free_balance(client, QUOTE_ASSET)
            btc_despues = get_free_balance(client, BASE_ASSET)
        except Exception:
            pass

    log_row({
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "fecha_vela": vela_fecha.date().isoformat(),
        "close": f"{close:.2f}",
        "sma_200": f"{sma_200:.2f}",
        "distancia_pct": f"{distancia_pct:.2f}",
        "senal": senal,
        "senal_previa": senal_previa or "",
        "cambio_senal": cambio,
        "accion": accion,
        "precio_ejecucion": precio_ejecucion,
        "cantidad": cantidad,
        "usdt_libre_despues": usdt_despues,
        "btc_libre_despues": btc_despues,
        "order_id": order_id,
        "nota": nota,
    })


if __name__ == "__main__":
    main()
