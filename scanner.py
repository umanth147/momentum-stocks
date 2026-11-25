import os
from datetime import datetime
import pandas as pd
import pytz
import requests
import yfinance as yf

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Active NSE F&O / Liquid stocks (.NS suffix)
FNO_STOCKS = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS",
    "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS", "LT.NS", "ITC.NS",
    "BHARTIARTL.NS", "M&M.NS", "SUNPHARMA.NS", "HCLTECH.NS",
    "BAJFINANCE.NS", "TATASTEEL.NS", "MARUTI.NS", "WIPRO.NS", "ADANIENT.NS",
    "ASIANPAINT.NS", "TITAN.NS", "ULTRACEMCO.NS", "POWERGRID.NS", "NTPC.NS"
]

VOLUME_MULTIPLIER = 1.3


def get_ist_now() -> datetime:
    return datetime.now(pytz.timezone("Asia/Kolkata"))


def send_telegram(message: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN அல்லது TELEGRAM_CHAT_ID காலியாக உள்ளது. "
            "GitHub Repository -> Settings -> Secrets and variables -> Actions இல் சரிபார்க்கவும்."
        )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
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


def scan_fno_stocks() -> None:
    now_ist = get_ist_now()
    bullish_signals = []
    bearish_signals = []

    for symbol in FNO_STOCKS:
        try:
            df = yf.download(
                symbol,
                period="1d",
                interval="5m",
                progress=False,
                auto_adjust=False
            )

            if df is None or df.empty or len(df) < 3:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df.dropna(subset=["High", "Low", "Close", "Volume"]).copy()
            if len(df) < 3:
                continue

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
                bullish_signals.append(
                    f"🟢 <b>{clean_name}</b>\n"
                    f"   LTP: ₹{ltp:.2f} | VWAP: ₹{vwap_val:.2f}\n"
                    f"   ORB High: ₹{orb_high:.2f} | Vol: {vol_ratio:.1f}x"
                )
            elif ltp < orb_low and ltp < vwap_val and vol_ratio >= VOLUME_MULTIPLIER:
                bearish_signals.append(
                    f"🔴 <b>{clean_name}</b>\n"
                    f"   LTP: ₹{ltp:.2f} | VWAP: ₹{vwap_val:.2f}\n"
                    f"   ORB Low: ₹{orb_low:.2f} | Vol: {vol_ratio:.1f}x"
                )

        except Exception as err:
            print(f"[ERROR] {symbol}: {err}")

    date_str = now_ist.strftime("%d-%b-%Y %I:%M %p IST")
    lines = [
        "📌 <b>F&O Intraday Scan (ORB + VWAP + Vol)</b>",
        f"🕒 {date_str}",
        ""
    ]

    if bullish_signals:
        lines.append("<b>📈 Bullish Setups:</b>")
        lines.extend(bullish_signals)
        lines.append("")

    if bearish_signals:
        lines.append("<b>📉 Bearish Setups:</b>")
        lines.extend(bearish_signals)
        lines.append("")

    if not bullish_signals and not bearish_signals:
        lines.append("இன்றைய ஸ்கேனில் ORB + VWAP + Volume நிபந்தனைகளுக்கு ஏற்ப சிக்னல்கள் எதுவும் வரவில்லை.")

    final_message = "\n".join(lines).strip()
    send_telegram(final_message)


if __name__ == "__main__":
    scan_fno_stocks()
