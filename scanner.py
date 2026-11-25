import os
from datetime import datetime
import pandas as pd
import pytz
import requests
import yfinance as yf

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# All 218 F&O symbols formatted with .NS suffix for NSE on Yahoo Finance
RAW_FNO_SYMBOLS = [
    "360ONE", "ABB", "APLAPOLLO", "AUBANK", "ACUTAAS",
    "ADANIENSOL", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER",
    "ABCAPITAL", "ALKEM", "AMBER", "AMBUJACEM", "ANANDRATHI",
    "ANGELONE", "APARINDS", "APOLLOHOSP", "ASHOKLEY", "ASIANPAINT",
    "ASTRAL", "ATHERENERG", "AUROPHARMA", "DMART", "AXISBANK",
    "BSE", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BANDHANBNK",
    "BANKBARODA", "BANKINDIA", "MAHABANK", "BDL", "BEL",
    "BHARATFORG", "BHEL", "BPCL", "BHARTIARTL", "BIOCON",
    "BLUESTARCO", "BOSCHLTD", "BRITANNIA", "CGPOWER", "CANBK",
    "CDSL", "CHOLAFIN", "CIPLA", "CUB", "COALINDIA",
    "COCHINSHIP", "COFORGE", "COLPAL", "CAMS", "CONCOR",
    "COROMANDEL", "CROMPTON", "CUMMINSIND", "DLF", "DABUR",
    "DATAPATTNS", "DELHIVERY", "DIVISLAB", "DIXON", "DRREDDY",
    "ETERNAL", "EICHERMOT", "FORCEMOT", "NYKAA", "FORTIS",
    "GAIL", "GVT&D", "GMRAIRPORT", "GLENMARK", "GODFRYPHLP",
    "GODREJCP", "GODREJPROP", "GRASIM", "HCLTECH", "HDFCAMC",
    "HDFCBANK", "HDFCLIFE", "HAVELLS", "HEROMOTOCO", "HINDALCO",
    "HAL", "HINDPETRO", "HINDUNILVR", "HINDZINC", "POWERINDIA",
    "HYUNDAI", "ICICIBANK", "ICICILIFE", "ICICIGI", "IDFCFIRSTB",
    "ITC", "INDIANB", "IOC", "IRFC", "INDUSTOWER",
    "INDUSINDBK", "NAUKRI", "INFY", "INOXWIND", "INDIGO",
    "JINDALSTEL", "JSWENERGY", "JSWSTEEL", "JIOFIN", "JUBLFOOD",
    "KEI", "KPITTECH", "KALYANKJIL", "KARURVYSYA", "KAYNES",
    "KFINTECH", "KOTAKBANK", "LTF", "LICHSGFIN", "LTM",
    "LT", "LAURUSLABS", "LICI", "LODHA", "LUPIN",
    "M&M", "MANAPPURAM", "MANKIND", "MARICO", "MARUTI",
    "MFSL", "MAXHEALTH", "MAZDOCK", "MOTILALOFS", "MPHASIS",
    "MCX", "MUTHOOTFIN", "NBCC", "NHPC", "NMDC",
    "NTPC", "NATIONALUM", "NAVINFLUOR", "NESTLEIND", "NAM-INDIA",
    "OBEROIRLTY", "ONGC", "OIL", "PAYTM", "OFSS",
    "POLICYBZR", "PGEL", "PIIND", "PNBHOUSING", "PAGEIND",
    "PATANJALI", "PERSISTENT", "PETRONET", "PIDILITIND", "POLYCAB",
    "PFC", "POWERGRID", "PREMIERENE", "PRESTIGE", "PNB",
    "RBLBANK", "RECLTD", "RADICO", "RVNL", "RELIANCE",
    "SAGILITY", "SBICARD", "SBILIFE", "SHREECEM", "SRF",
    "MOTHERSON", "SHRIRAMFIN", "ENRIN", "SIEMENS", "SOLARINDS",
    "SONACOMS", "SBIN", "SAIL", "SUNPHARMA", "SUPREMEIND",
    "SUZLON", "SWIGGY", "SYRMA", "TATACONSUM", "TVSMOTOR",
    "TCS", "TATAELXSI", "TMPV", "TATAPOWER", "TATASTEEL",
    "TECHM", "FEDERALBNK", "INDHOTEL", "PHOENIXLTD", "TITAN",
    "TORNTPHARM", "TRENT", "TIINDIA", "UNOMINDA", "UPL",
    "UJJIVANSFB", "ULTRACEMCO", "UNIONBANK", "UNITDSPR", "VBL",
    "VEDL", "VMM", "IDEA", "VOLTAS", "WAAREEENER",
    "WIPRO", "YESBANK", "ZYDUSLIFE"
]

FNO_STOCKS = [f"{s.strip()}.NS" for s in dict.fromkeys(RAW_FNO_SYMBOLS) if s.strip()]

VOLUME_MULTIPLIER = 1.3
BATCH_SIZE = 55


def get_ist_now() -> datetime:
    return datetime.now(pytz.timezone("Asia/Kolkata"))


def send_telegram(message: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError(
            "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in GitHub Secrets."
        )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    # Telegram hard limit is 4096 characters per message
    max_len = 3900
    chunks = [message[i:i + max_len] for i in range(0, len(message), max_len)] or [message]

    for chunk in chunks:
        payload = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3.0
    cum_volume = df["Volume"].cumsum()
    cum_volume_safe = cum_volume.replace(0, float("nan"))
    cum_pv = (typical_price * df["Volume"]).cumsum()
    return cum_pv / cum_volume_safe


def evaluate_stock_df(symbol: str, stock_df: pd.DataFrame):
    df = stock_df.dropna(subset=["High", "Low", "Close", "Volume"]).copy()
    if df.empty or len(df) < 3:
        return None

    # First three 5-min candles (~9:15 AM to 9:30 AM opening range)
    orb_df = df.iloc[:3]
    orb_high = float(orb_df["High"].max())
    orb_low = float(orb_df["Low"].min())

    df["VWAP"] = compute_vwap(df)

    latest = df.iloc[-1]
    ltp = float(latest["Close"])
    vwap_val = float(latest["VWAP"]) if pd.notna(latest["VWAP"]) else ltp

    latest_vol = float(latest["Volume"])
    avg_vol = float(df["Volume"].mean())
    vol_ratio = (latest_vol / avg_vol) if avg_vol > 0 else 0.0

    clean_name = symbol.replace(".NS", "")

    if ltp > orb_high and ltp > vwap_val and vol_ratio >= VOLUME_MULTIPLIER:
        return (
            "bullish",
            f"🟢 <b>{clean_name}</b>\n"
            f"   LTP: ₹{ltp:.2f} | VWAP: ₹{vwap_val:.2f}\n"
            f"   ORB High: ₹{orb_high:.2f} | Vol: {vol_ratio:.1f}x"
        )

    if ltp < orb_low and ltp < vwap_val and vol_ratio >= VOLUME_MULTIPLIER:
        return (
            "bearish",
            f"🔴 <b>{clean_name}</b>\n"
            f"   LTP: ₹{ltp:.2f} | VWAP: ₹{vwap_val:.2f}\n"
            f"   ORB Low: ₹{orb_low:.2f} | Vol: {vol_ratio:.1f}x"
        )

    return None


def scan_fno_stocks() -> None:
    now_ist = get_ist_now()
    bullish_signals = []
    bearish_signals = []

    for i in range(0, len(FNO_STOCKS), BATCH_SIZE):
        batch = FNO_STOCKS[i:i + BATCH_SIZE]
        try:
            data = yf.download(
                tickers=" ".join(batch),
                period="1d",
                interval="5m",
                group_by="ticker",
                threads=True,
                progress=False,
                auto_adjust=False
            )
            if data is None or data.empty:
                continue

            for symbol in batch:
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        if symbol not in data.columns.get_level_values(0):
                            continue
                        stock_df = data[symbol]
                    else:
                        stock_df = data

                    result = evaluate_stock_df(symbol, stock_df)
                    if result:
                        direction, formatted = result
                        if direction == "bullish":
                            bullish_signals.append(formatted)
                        else:
                            bearish_signals.append(formatted)
                except Exception as sym_err:
                    print(f"[SYMBOL SKIP] {symbol}: {sym_err}")

        except Exception as batch_err:
            print(f"[BATCH ERROR] {batch[0]}..{batch[-1]}: {batch_err}")

    date_str = now_ist.strftime("%d-%b-%Y %I:%M %p IST")
    lines = [
        f"📌 <b>F&O Intraday Scan ({len(FNO_STOCKS)} Stocks)</b>",
        f"🕒 {date_str}",
        ""
    ]

    if bullish_signals:
        lines.append(f"<b>📈 Bullish Setups ({len(bullish_signals)}):</b>")
        lines.extend(bullish_signals)
        lines.append("")

    if bearish_signals:
        lines.append(f"<b>📉 Bearish Setups ({len(bearish_signals)}):</b>")
        lines.extend(bearish_signals)
        lines.append("")

    if not bullish_signals and not bearish_signals:
        lines.append("No qualifying ORB + VWAP + Volume signals found in this scan.")

    final_message = "\n".join(lines).strip()
    send_telegram(final_message)


if __name__ == "__main__":
    scan_fno_stocks()
