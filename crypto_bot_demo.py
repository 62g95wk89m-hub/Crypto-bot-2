"""
Crypto Bot Demo 1.0 — PAPER TRADING ONLY
BTC/EUR, 15m candles, EMA20/EMA50 + RSI14.
No real orders are ever sent. Do not add exchange API keys.
"""

import os
import time
import logging
from datetime import datetime, timezone, date

import ccxt
import pandas as pd
import requests

# ---------- CONFIG ----------
SYMBOL = os.getenv("SYMBOL", "BTC/EUR")
TIMEFRAME = "15m"
STARTING_EUR = float(os.getenv("STARTING_EUR", "100"))
RISK_PER_TRADE = 0.005       # 0.5% of current equity
MAX_NOTIONAL_FRACTION = 0.50 # use at most 50% of equity per simulated position
DAILY_LOSS_LIMIT = 0.015     # stop opening trades after -1.5% daily realized P&L
STOP_PCT = 0.010             # 1.0%
TAKE_PROFIT_PCT = 0.020      # 2.0%
FEE_RATE = 0.001             # assumed 0.10% each side; replace with actual venue fees
SLIPPAGE_RATE = 0.0005       # assumed 0.05% each side
POLL_SECONDS = 60
EXCHANGE_ID = os.getenv("EXCHANGE_ID", "binance")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("crypto-paper-bot")


def notify(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.info("Telegram non configurato: %s", message.replace("\n", " | "))
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=15,
        )
        response.raise_for_status()
    except Exception as exc:
        log.warning("Invio Telegram non riuscito: %s", exc)


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

    delta = df["close"].diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = losses.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-12)
    df["rsi14"] = 100 - (100 / (1 + rs))
    return df


class PaperBot:
    def __init__(self):
        exchange_class = getattr(ccxt, EXCHANGE_ID)
        self.exchange = exchange_class({"enableRateLimit": True})
        self.cash = STARTING_EUR
        self.position = None
        self.last_candle_ts = None
        self.day = date.today()
        self.day_start_equity = STARTING_EUR
        self.realized_today = 0.0
        self.trades = 0
        self.wins = 0
        self.losses = 0
        self.halted_today = False

    def equity(self, mark_price=None):
        value = self.cash
        if self.position and mark_price:
            value += self.position["qty"] * mark_price
        return value

    def fetch_data(self):
        rows = self.exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=120)
        if not rows or len(rows) < 60:
            raise RuntimeError("Dati OHLCV insufficienti.")
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        # L'ultima candela può essere ancora in formazione: viene esclusa.
        df = df.iloc[:-1].copy()
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return indicators(df).dropna().reset_index(drop=True)

    def roll_day_if_needed(self):
        today = date.today()
        if today != self.day:
            self.day = today
            self.day_start_equity = self.equity()
            self.realized_today = 0.0
            self.halted_today = False
            notify(f"Nuovo giorno demo. Equity iniziale: €{self.day_start_equity:.2f}")

    def enter(self, candle):
        close = float(candle.close)
        entry = close * (1 + SLIPPAGE_RATE)
        equity = self.equity(close)
        risk_eur = equity * RISK_PER_TRADE
        stop_distance = entry * STOP_PCT
        qty_by_risk = risk_eur / stop_distance
        max_notional = equity * MAX_NOTIONAL_FRACTION
        qty_by_capital = max_notional / entry
        qty = min(qty_by_risk, qty_by_capital)

        gross = qty * entry
        fee = gross * FEE_RATE
        total_cost = gross + fee
        if qty <= 0 or total_cost > self.cash:
            log.info("Segnale BUY ignorato: liquidità demo insufficiente.")
            return

        self.cash -= total_cost
        self.position = {
            "qty": qty,
            "entry": entry,
            "entry_fee": fee,
            "stop": entry * (1 - STOP_PCT),
            "target": entry * (1 + TAKE_PROFIT_PCT),
            "opened_at": candle.datetime.isoformat(),
        }
        notify(
            "🟢 PAPER BUY — nessun ordine reale\n"
            f"{SYMBOL} | ingresso €{entry:.2f}\n"
            f"Quantità: {qty:.8f} BTC\n"
            f"Stop: €{self.position['stop']:.2f} | Target: €{self.position['target']:.2f}\n"
            f"Commissione simulata: €{fee:.4f}"
        )
        log.info("PAPER BUY %.8f %s a %.2f", qty, SYMBOL, entry)

    def exit_position(self, raw_exit, reason):
        p = self.position
        exit_price = raw_exit * (1 - SLIPPAGE_RATE)
        gross_proceeds = p["qty"] * exit_price
        exit_fee = gross_proceeds * FEE_RATE
        self.cash += gross_proceeds - exit_fee

        pnl = (gross_proceeds - exit_fee) - (p["qty"] * p["entry"]) - p["entry_fee"]
        self.realized_today += pnl
        self.trades += 1
        if pnl >= 0:
            self.wins += 1
        else:
            self.losses += 1

        self.position = None
        notify(
            f"{'✅' if pnl >= 0 else '🔴'} PAPER SELL — {reason}\n"
            f"{SYMBOL} | uscita €{exit_price:.2f}\n"
            f"Risultato netto stimato: {'+' if pnl >= 0 else ''}€{pnl:.2f}\n"
            f"Saldo demo: €{self.cash:.2f}"
        )
        log.info("PAPER SELL pnl=%.4f reason=%s cash=%.2f", pnl, reason, self.cash)

    def process_candle(self, candle, previous):
        self.roll_day_if_needed()
        ts = int(candle.timestamp)
        if self.last_candle_ts == ts:
            return
        self.last_candle_ts = ts

        close = float(candle.close)
        high = float(candle.high)
        low = float(candle.low)
        ema20 = float(candle.ema20)
        ema50 = float(candle.ema50)
        rsi = float(candle.rsi14)

        # Conservative intrabar rule: if stop and target are both touched,
        # assume stop first because candle data does not reveal event order.
        if self.position:
            stop = self.position["stop"]
            target = self.position["target"]
            if low <= stop:
                self.exit_position(stop, "stop loss")
            elif high >= target:
                self.exit_position(target, "take profit")
            elif ema20 < ema50 or rsi < 45:
                self.exit_position(close, "segnale di uscita trend/RSI")

        daily_limit_eur = self.day_start_equity * DAILY_LOSS_LIMIT
        if self.realized_today <= -daily_limit_eur:
            if not self.halted_today:
                self.halted_today = True
                notify(
                    "⛔ BOT IN PAUSA per oggi\n"
                    f"Limite perdita giornaliera demo raggiunto: €{self.realized_today:.2f}"
                )

        if (
            self.position is None
            and not self.halted_today
            and ema20 > ema50
            and 50 <= rsi <= 65
            and close > ema20
        ):
            self.enter(candle)

        log.info(
            "Candle %s close=%.2f EMA20=%.2f EMA50=%.2f RSI=%.1f "
            "cash=%.2f position=%s dayPnL=%.2f",
            candle.datetime, close, ema20, ema50, rsi,
            self.cash, bool(self.position), self.realized_today
        )

    def run(self):
        notify(
            "🤖 Crypto Bot Demo 1.0 avviato\n"
            f"Mercato: {SYMBOL} | timeframe: {TIMEFRAME}\n"
            f"Capitale virtuale: €{STARTING_EUR:.2f}\n"
            "Modalità PAPER TRADING: nessun ordine reale."
        )
        log.info("Avviato. Modalità esclusivamente demo.")
        while True:
            try:
                df = self.fetch_data()
                if len(df) >= 2:
                    self.process_candle(df.iloc[-1], df.iloc[-2])
            except KeyboardInterrupt:
                notify("⏸ Crypto Bot Demo fermato manualmente.")
                break
            except Exception as exc:
                log.exception("Errore nel ciclo: %s", exc)
                notify(f"⚠️ Errore bot demo: {type(exc).__name__}: {exc}")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    PaperBot().run()
