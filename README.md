# Binance Futures Kalabalık Tarayıcı

Bu uygulama Binance USDⓈ-M Futures public endpoints üzerinden piyasa verisi okur. Emir açmaz, API anahtarı kullanmaz.

## Yerel çalıştırma
```bash
pip install -r requirements.txt
streamlit run app.py
```
Tarayıcıda Streamlit'in gösterdiği yerel URL açılır.

## Ücretsiz şekilde web'de yayınlama
1. GitHub'da ücretsiz bir repository oluştur.
2. `app.py` ve `requirements.txt` dosyalarını repository'ye yükle.
3. Streamlit Community Cloud'a GitHub ile giriş yap.
4. **Create app** → repository, branch ve `app.py` seç → Deploy.
5. Veriler için API anahtarı gerekmez.

Ücretsiz katmanda uygulama uykuya alınabilir ve kullanım limitleri olabilir.

## Uyarı
Sinyaller yalnızca gözlem amaçlıdır; finansal tavsiye değildir. L/S ratio, OI ve fiyat değişimi tek başına pozisyon açma gerekçesi değildir. Binance API uç noktalarının kullanılabilirliği, oran limitleri ve ürün kapsamı değişebilir.
