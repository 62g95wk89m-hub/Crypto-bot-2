# Crypto Bot Demo 1.0 — iPhone + Telegram

**SOLO PAPER TRADING.** Questo progetto non invia ordini reali e non richiede chiavi API di exchange o credenziali Deblock.

## Cosa fa
- Legge candele pubbliche BTC/EUR a 15 minuti tramite CCXT.
- Calcola EMA20, EMA50 e RSI14.
- Simula acquisti/vendite con capitale virtuale iniziale di 100 EUR.
- Simula commissioni (0,10% per lato) e slippage (0,05% per lato).
- Usa stop loss 1%, take profit 2%, rischio teorico 0,5% del capitale e limite giornaliero 1,5%.
- Invia notifiche Telegram se sono configurate le variabili d'ambiente.

I parametri sono ipotesi di test, non una strategia validata né una promessa di rendimento. Il test non è una prova che la strategia funzionerà in futuro.

## Avvio da iPhone con Replit
1. Apri Replit nel browser dell'iPhone e crea un nuovo progetto Python.
2. Carica `crypto_bot_demo.py` e `requirements.txt` (oppure copia i contenuti nei file).
3. Apri la Shell e installa le dipendenze:
   `pip install -r requirements.txt`
4. Crea un bot Telegram parlando con `@BotFather`:
   - invia `/newbot`
   - segui le istruzioni e conserva il token in modo privato.
5. Recupera il tuo chat ID:
   - apri il bot appena creato su Telegram e premi Start;
   - invia un messaggio qualsiasi;
   - apri nel browser `https://api.telegram.org/bot<TUO_TOKEN>/getUpdates`
   - cerca `message` → `chat` → `id`.
   - Non condividere l'URL, il token o la risposta con nessuno.
6. In Replit, aggiungi questi Secrets/Environment Variables:
   - `TELEGRAM_BOT_TOKEN` = token BotFather
   - `TELEGRAM_CHAT_ID` = il tuo chat ID
7. Avvia il programma con:
   `python crypto_bot_demo.py`

Se non configuri Telegram, il bot funziona comunque e scrive gli eventi nei log.

## Importante
- Non inserire seed phrase, password Deblock, chiavi private o credenziali bancarie.
- Non aggiungere chiavi API di trading: questo codice non ne ha bisogno e non esegue ordini.
- Un processo Replit gratuito potrebbe non restare attivo continuamente; la disponibilità dipende dal piano e dalle regole correnti del servizio.
- La simulazione usa dati OHLCV e ipotesi semplificate. Stop e target toccati nella stessa candela vengono trattati in modo prudente (stop prima).
- Controlla le commissioni effettive e la disponibilità del mercato BTC/EUR sull'exchange dati prima di interpretare i risultati.
- Il bot non garantisce profitti né assenza di perdite. Non passare al trading reale sulla base di pochi giorni di simulazione.

## Personalizzazione
Variabili opzionali:
- `SYMBOL` (default `BTC/EUR`)
- `EXCHANGE_ID` (default `binance`)
- `STARTING_EUR` (default `100`)
