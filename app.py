import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

BASE = "https://fapi.binance.com"
st.set_page_config(page_title="Futures Crowd Scanner", page_icon="🐋", layout="wide")
st.title("🐋 Binance Futures — Kalabalık Tarayıcı")
st.caption("Ücretsiz, salt-okuma piyasa verileri. Emir açmaz; sinyal garanti değildir.")

st.sidebar.header("Tarama ayarları")
scan_all = st.sidebar.checkbox("Hacim filtresini geçen tüm USDT perpetual coinleri tara", value=True)
min_volume = st.sidebar.number_input("Minimum 24s hacim (USDT)", min_value=0, value=2_000_000, step=500_000)
symbols_raw = st.sidebar.text_input("Özel semboller (virgülle)", "AINUSDT,BTCUSDT,ETHUSDT", disabled=scan_all)
period = st.sidebar.selectbox("Long/Short ve OI periyodu", ["5m", "15m", "1h"], index=1)
auto_scan = st.sidebar.checkbox("Otomatik sürekli tarama", value=True)
refresh_seconds = st.sidebar.selectbox("Yenileme aralığı (saniye)", [30, 60, 90, 120], index=1, disabled=not auto_scan)
run = st.sidebar.button("Şimdi tara", type="primary")

if auto_scan:
    st_autorefresh(interval=int(refresh_seconds) * 1000, key="futures_scanner_refresh")

st.info("Yüksek Long/Short oranı tek başına ters işlem sinyali değildir. Funding, OI ve fiyat hareketini birlikte değerlendir.")

@st.cache_data(ttl=60)
def discover_symbols(min_quote_volume):
    exchange = requests.get(BASE + "/fapi/v1/exchangeInfo", timeout=20)
    exchange.raise_for_status()
    info = exchange.json()
    valid = {s["symbol"] for s in info["symbols"]
             if s.get("status") == "TRADING" and s.get("contractType") == "PERPETUAL"
             and s.get("quoteAsset") == "USDT"}
    tickers = requests.get(BASE + "/fapi/v1/ticker/24hr", timeout=20)
    tickers.raise_for_status()
    return sorted(t["symbol"] for t in tickers.json()
                  if t.get("symbol") in valid and float(t.get("quoteVolume", 0)) >= min_quote_volume)

def get_json(path, params=None):
    r = requests.get(BASE + path, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_symbol(symbol, period):
    ticker = get_json("/fapi/v1/ticker/24hr", {"symbol": symbol})
    ratio = get_json("/futures/data/globalLongShortAccountRatio", {"symbol": symbol, "period": period, "limit": 1})
    oi_hist = get_json("/futures/data/openInterestHist", {"symbol": symbol, "period": period, "limit": 2})
    funding = get_json("/fapi/v1/fundingRate", {"symbol": symbol, "limit": 1})
    klines = get_json("/fapi/v1/klines", {"symbol": symbol, "interval": period, "limit": 3})

    ls = float(ratio[-1]["longShortRatio"]) if ratio else None
    long_pct = float(ratio[-1]["longAccount"]) * 100 if ratio else None
    short_pct = float(ratio[-1]["shortAccount"]) * 100 if ratio else None
    oi_change = None
    if len(oi_hist) >= 2:
        before, after = float(oi_hist[-2]["sumOpenInterest"]), float(oi_hist[-1]["sumOpenInterest"])
        if before:
            oi_change = (after / before - 1) * 100
    funding_rate = float(funding[-1]["fundingRate"]) * 100 if funding else None
    closes = [float(k[4]) for k in klines]
    price_change = ((closes[-1] / closes[-2]) - 1) * 100 if len(closes) >= 2 and closes[-2] else None
    price, vol = float(ticker["lastPrice"]), float(ticker["quoteVolume"])

    signal, reason = "TEYİT YOK", "Göstergeler net bir squeeze senaryosu oluşturmuyor."
    if ls is not None and oi_change is not None and price_change is not None:
        if ls <= 0.70 and price_change > 0 and oi_change > 0:
            signal, reason = "SHORT SQUEEZE İZLE", "Short ağırlığı yüksek; fiyat ve OI artıyor. Kırılımın kalıcılığını kontrol et."
        elif ls >= 1.40 and price_change < 0 and oi_change > 0:
            signal, reason = "LONG SQUEEZE İZLE", "Long ağırlığı yüksek; fiyat düşerken OI artıyor. Destek kırılımını kontrol et."
        elif ls <= 0.70 and price_change < 0:
            signal, reason = "SHORT KALABALIK — DİKKAT", "Short ağırlığı yüksek ama fiyat aşağı gidiyor; kalabalık tek başına ters sinyal değil."
        elif ls >= 1.40 and price_change > 0:
            signal, reason = "LONG KALABALIK — DİKKAT", "Long ağırlığı yüksek ama fiyat yukarı gidiyor; trend devam edebilir."
    return {"Coin": symbol, "Fiyat": price, "24s Hacim (USDT)": vol, "Long %": long_pct,
            "Short %": short_pct, "L/S oranı": ls, f"OI değişim ({period}) %": oi_change,
            f"Fiyat değişim ({period}) %": price_change, "Funding %": funding_rate,
            "İzleme": signal, "Not": reason}

if run or auto_scan:
    try:
        if scan_all:
            with st.spinner("Binance'tan hacim filtresini geçen coinler bulunuyor..."):
                symbols = discover_symbols(float(min_volume))
        else:
            symbols = list(dict.fromkeys(s.strip().upper() for s in symbols_raw.split(",") if s.strip()))
        if not symbols:
            st.warning("Bu hacim eşiğini geçen sembol bulunamadı.")
        else:
            st.write(f"**{len(symbols)} coin** taranacak (minimum 24s hacim: **{min_volume:,.0f} USDT**).")
            if auto_scan:
                st.caption(f"⟳ Otomatik tarama açık — her {refresh_seconds} saniyede yenilenir. Bu sayfa açık kalmalı.")
            rows, errors = [], []
            progress = st.progress(0)
            status = st.empty()
            with ThreadPoolExecutor(max_workers=8) as pool:
                jobs = {pool.submit(fetch_symbol, symbol, period): symbol for symbol in symbols}
                for i, job in enumerate(as_completed(jobs), start=1):
                    symbol = jobs[job]
                    try:
                        rows.append(job.result())
                    except Exception as e:
                        errors.append(f"{symbol}: {e}")
                    progress.progress(i / len(symbols))
                    status.caption(f"İlerleme: {i}/{len(symbols)}")
            if rows:
                df = pd.DataFrame(rows).sort_values("24s Hacim (USDT)", ascending=False)
                st.subheader("Tarama sonuçları")
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.download_button("CSV indir", df.to_csv(index=False).encode("utf-8-sig"), "futures_crowd_scan.csv", "text/csv")
            if errors:
                st.warning("Bazı semboller alınamadı:\n\n" + "\n".join(errors[:30]))
    except Exception as e:
        st.error(f"Tarama başlatılamadı: {e}")
else:
    st.markdown("""
### Başlamak için
Sol tarafta **minimum 24s hacmi 2.000.000 USDT** olarak bırak. Varsayılan ayar, otomatik taramayı her 60 saniyede yeniler; istersen otomatik taramayı kapatıp **Şimdi tara** ile tek seferlik tarayabilirsin. Varsayılan ayar hacim filtresini geçen tüm USDT perpetual coinleri tarar.

**Okuma notu:** L/S oranı Binance'ın global hesap oranıdır; bütün piyasanın eksiksiz pozisyon verisi değildir. OI ve fiyat değişimi bağlam sağlar. Demo/araştırma amaçlı kullan; kaldıraçlı işlemlerde likidasyon riski yüksektir.
""")
