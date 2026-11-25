import os
from datetime import datetime
import pandas as pd
import pytz
import requests
import yfinance as yf

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

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
BATCH_SIZE = 55


def get_ist_now() -> datetime:
    return datetime.now(pytz.timezone("Asia/Kolkata"))


def send_telegram(message: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in GitHub Secrets.")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    max_len = 3800
    lines = message.split("\n")
    chunks = []
    current = ""

    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)

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


def classify_stock(symbol: str, stock_df: pd.DataFrame):
    df = stock_df.dropna(subset=["High", "Low", "Close", "Volume"]).copy()
    if df.empty or len(df) < 3:
        return None

    # முதல் 3 ஐந்து-நிமிட கேண்டில்கள் (9:15 - 9:30 AM Opening Range)
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

    # Bullish அல்லது Bearish திசை மற்றும் பிரேக்அவுட் சதவீதம்
    is_bullish = ltp > orb_high and ltp > vwap_val
    is_bearish = ltp < orb_low and ltp < vwap_val

    if is_bullish:
        side = "🟢 BUY"
        breakout_pct = ((ltp - orb_high) / orb_high) * 100.0 if orb_high > 0 else 0.0
    elif is_bearish:
        side = "🔴 SELL"
        breakout_pct = ((orb_low - ltp) / orb_low) * 100.0 if orb_low > 0 else 0.0
    else:
        side = "⚪ RANGE"
        breakout_pct = 0.0

    info = {
        "name": clean_name,
        "side": side,
        "ltp": ltp,
        "vwap": vwap_val,
        "vol_ratio": vol_ratio,
        "breakout_pct": breakout_pct
    }

    # 4 நிலைகளாகப் பிரித்தல்
    if (is_bullish or is_bearish) and vol_ratio >= 2.0 and breakout_pct >= 0.5:
        tier = "very_good"
    elif (is_bullish or is_bearish) and vol_ratio >= 1.5:
        tier = "good"
    elif (is_bullish or is_bearish) and vol_ratio >= 1.1:
        tier = "medium"
    else:
        tier = "low"

    return tier, info


def format_item(item: dict, compact: bool = False) -> str:
    if compact:
        return (
            f"• <b>{item['name']}</b> ({item['side']}) | "
            f"₹{item['ltp']:.1f} | Vol: {item['vol_ratio']:.1f}x"
        )
    return (
        f"{item['side']} <b>{item['name']}</b> — "
        f"LTP: ₹{item['ltp']:.2f} | VWAP: ₹{item['vwap']:.2f} | "
        f"Move: {item['breakout_pct']:.2f}% | Vol: <b>{item['vol_ratio']:.1f}x</b>"
    )


def scan_fno_stocks() -> None:
    now_ist = get_ist_now()
    buckets = {
        "very_good": [],
        "good": [],
        "medium": [],
        "low": []
    }

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

                    res = classify_stock(symbol, stock_df)
                    if res:
                        tier, info = res
                        buckets[tier].append(info)
                except Exception as sym_err:
                    print(f"[SKIP] {symbol}: {sym_err}")
        except Exception as batch_err:
            print(f"[BATCH ERROR] {batch_err}")

    # அதிக வால்யூம் அடிப்படையில் வரிசைப்படுத்தல்
    for key in buckets:
        buckets[key].sort(key=lambda x: x["vol_ratio"], reverse=True)

    date_str = now_ist.strftime("%d-%b-%Y %I:%M %p IST")
    lines = [
        f"📊 <b>F&O Momentum Tier Report ({len(FNO_STOCKS)} Stocks)</b>",
        f"🕒 {date_str}",
        ""
    ]

    # 1. Very Good Momentum
    lines.append(f"<b>1️⃣ VERY GOOD MOMENTUM ({len(buckets['very_good'])})</b>")
    if buckets["very_good"]:
        lines.extend(format_item(x) for x in buckets["very_good"][:15])
    else:
        lines.append("• இல்லை (None)")
    lines.append("")

    # 2. Good Momentum
    lines.append(f"<b>2️⃣ GOOD MOMENTUM ({len(buckets['good'])})</b>")
    if buckets["good"]:
        lines.extend(format_item(x) for x in buckets["good"][:15])
    else:
        lines.append("• இல்லை (None)")
    lines.append("")

    # 3. Medium Momentum
    lines.append(f"<b>3️⃣ MEDIUM MOMENTUM ({len(buckets['medium'])})</b>")
    if buckets["medium"]:
        lines.extend(format_item(x, compact=True) for x in buckets["medium"][:15])
    else:
        lines.append("• இல்லை (None)")
    lines.append("")

    # 4. Low Momentum (Top 10 by Volume only to avoid message spam)
    lines.append(f"<b>4️⃣ LOW MOMENTUM (Total: {len(buckets['low'])} | Top 10 Vol)</b>")
    if buckets["low"]:
        lines.extend(format_item(x, compact=True) for x in buckets["low"][:10])
    else:
        lines.append("• இல்லை (None)")

    send_telegram("\n".join(lines).strip())


if __name__ == "__main__":
    scan_fno_stocks()
