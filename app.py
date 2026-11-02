import time
import requests
import pandas as pd
import streamlit as st

BASE = "https://fapi.binance.com"
st.set_page_config(page_title="Futures Crowd Scanner", page_icon="🐋", layout="wide")
st.title("🐋 Binance Futures — Kalabalık Tarayıcı")
st.caption("Ücretsiz, salt-okuma piyasa verileri. Emir açmaz; sinyal garanti değildir.")

st.sidebar.header("Tarama ayarları")
symbols_raw = st.sidebar.text_input("Semboller (virgülle)", "AINUSDT,BTCUSDT,ETHUSDT")
period = st.sidebar.selectbox("Long/Short ve OI periyodu", ["5m", "15m", "1h"], index=1)
run = st.sidebar.button("Verileri tara", type="primary")

st.info("Yüksek Long/Short oranı tek başına ters işlem sinyali değildir. Funding, OI ve fiyat hareketini birlikte değerlendir.")

def get_json(path, params=None):
    r = requests.get(BASE + path, params=params, timeout=12)
    r.raise_for_status()
    return r.json()

def fetch_symbol(symbol, period):
    # Public Binance USDⓈ-M futures endpoints
    ticker = get_json("/fapi/v1/ticker/24hr", {"symbol": symbol})
    ratio = get_json("/futures/data/globalLongShortAccountRatio",
                     {"symbol": symbol, "period": period, "limit": 1})
    oi_hist = get_json("/futures/data/openInterestHist",
                       {"symbol": symbol, "period": period, "limit": 2})
    funding = get_json("/fapi/v1/fundingRate", {"symbol": symbol, "limit": 1})
    klines = get_json("/fapi/v1/klines", {"symbol": symbol, "interval": period, "limit": 3})

    ls = float(ratio[-1]["longShortRatio"]) if ratio else None
    long_pct = float(ratio[-1]["longAccount"]) * 100 if ratio else None
    short_pct = float(ratio[-1]["shortAccount"]) * 100 if ratio else None
    oi_change = None
    if len(oi_hist) >= 2:
        before = float(oi_hist[-2]["sumOpenInterest"])
        after = float(oi_hist[-1]["sumOpenInterest"])
        if before:
            oi_change = (after / before - 1) * 100
    funding_rate = float(funding[-1]["fundingRate"]) * 100 if funding else None
    closes = [float(k[4]) for k in klines]
    price_change = ((closes[-1] / closes[-2]) - 1) * 100 if len(closes) >= 2 and closes[-2] else None
    price = float(ticker["lastPrice"])
    vol = float(ticker["quoteVolume"])

    # Basic contextual labels, not automated trading advice
    signal = "TEYİT YOK"
    reason = "Göstergeler net bir squeeze senaryosu oluşturmuyor."
    if ls is not None and oi_change is not None and price_change is not None:
        if ls <= 0.70 and price_change > 0 and oi_change > 0:
            signal = "SHORT SQUEEZE İZLE"
            reason = "Short ağırlığı yüksek; fiyat ve OI artıyor. Kırılımın kalıcılığını kontrol et."
        elif ls >= 1.40 and price_change < 0 and oi_change > 0:
            signal = "LONG SQUEEZE İZLE"
            reason = "Long ağırlığı yüksek; fiyat düşerken OI artıyor. Destek kırılımını kontrol et."
        elif ls <= 0.70 and price_change < 0:
            signal = "SHORT KALABALIK — DİKKAT"
            reason = "Short ağırlığı yüksek ama fiyat aşağı gidiyor; kalabalık tek başına ters sinyal değil."
        elif ls >= 1.40 and price_change > 0:
            signal = "LONG KALABALIK — DİKKAT"
            reason = "Long ağırlığı yüksek ama fiyat yukarı gidiyor; trend devam edebilir."
    return {
        "Coin": symbol, "Fiyat": price, "24s Hacim (USDT)": vol,
        "Long %": long_pct, "Short %": short_pct, "L/S oranı": ls,
        f"OI değişim ({period}) %": oi_change,
        f"Fiyat değişim ({period}) %": price_change,
        "Funding %": funding_rate, "İzleme": signal, "Not": reason
    }

if run:
    symbols = list(dict.fromkeys(s.strip().upper() for s in symbols_raw.split(",") if s.strip()))
    if not symbols:
        st.error("En az bir sembol yaz. Örnek: AINUSDT,BTCUSDT")
    else:
        rows, errors = [], []
        progress = st.progress(0)
        for i, symbol in enumerate(symbols):
            try:
                rows.append(fetch_symbol(symbol, period))
            except Exception as e:
                errors.append(f"{symbol}: {e}")
            progress.progress((i + 1) / len(symbols))
            time.sleep(0.15)
        if rows:
            df = pd.DataFrame(rows)
            st.subheader("Tarama sonuçları")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("CSV indir", df.to_csv(index=False).encode("utf-8-sig"),
                               "futures_crowd_scan.csv", "text/csv")
        if errors:
            st.warning("Bazı semboller alınamadı:\n\n" + "\n".join(errors))
else:
    st.markdown("""
### Başlamak için
1. Sol tarafta sembolleri yaz (ör. `AINUSDT,BTCUSDT,ETHUSDT`).
2. Periyodu seç.
3. **Verileri tara** düğmesine bas.

**Okuma notu:** L/S oranı Binance'ın global hesap oranıdır; bütün piyasanın eksiksiz pozisyon verisi değildir. OI değişimi ve fiyat değişimi bağlam sağlar. Tüm sinyalleri demo/araştırma amaçlı kullan; kaldıraçlı işlemlerde likidasyon riski yüksektir.
""")
