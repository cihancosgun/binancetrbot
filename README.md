# 🚀 Binance TR Otomatik Al-Sat Botu (Paper Trading & Canlı Mod)

Bu bot; Binance TR üzerinde belirlediğiniz bütçe ve parametrelerle anlık canlı tahtayı ve piyasa radarını izleyerek otomatik al-sat işlemleri gerçekleştirir. Risk almadan önce **15-20 dakikalık (veya dilediğiniz sürede) sanal bütçeli (paper trading / test modu)** koşular yaparak algoritma performansını ölçebilir, sonuçları inceleyip parametreleri optimize ettikten sonra tek bir parametre ile güvenle **gerçek hesaba (live mod)** geçebilirsiniz.

---

## 🌟 Temel Özellikler

1. **Ayrıştırılmış Test ve Canlı Mod Yapılandırması:**
   - **Test Modu (`config.test.yaml`):** 10.000 TL sanal bütçe ile risk almadan stratejileri dener, API anahtarı gerektirmez.
   - **Canlı Mod (`config.live.yaml`):** Binance TR API üzerinden gerçek spot emirleri iletir.
   - Çalıştırırken `--mode test` veya `--mode live` parametresi ile anında geçiş yapılabilir.

2. **Git & Güvenlik Koruması:**
   - Gerçek API anahtarlarınızı içeren `config.yaml`, `config.live.yaml` ve `config.test.yaml` dosyaları `.gitignore` ile korunur, Git'e asla yüklenmez.
   - Git deposu için örnek şablonlar sunulur (`config.test.example.yaml`, `config.live.example.yaml`, `config.example.yaml`).

3. **Otomatik Piyasa Radarı & Dinamik Sepet:**
   - `symbol: "AUTO"` seçildiğinde piyasadaki en hareketli ve hacimli coinleri anlık olarak tarar.
   - Belirlenen hedef coin sayısına göre (örn: 5 farklı coin) dinamik portföy sepeti yönetimi yapar.

4. **Gelişmiş Risk & Kâr Yönetimi:**
   - **Kâr Al (Take Profit %):** Hedef kâr seviyesinde otomatik satış.
   - **Zarar Kes (Stop Loss %):** Beklenmedik düşüşlerde sermayeyi korumak için satış.
   - **İz Süren Stop (Trailing Stop %):** Fiyat zirveye ulaşıp gerilediğinde kârı kilitler.
   - **Cooldown:** İşlemler arası aşırı al-satı engelleyen bekleme sayacı.

5. **Hazır ve Gelişmiş Stratejiler:**
   - **Adaptive Market Regime (Hibrit Piyasa Rejimi - Önerilen):** Trend ve yatay piyasaları dinamik tespit ederek RSI + Bollinger + EMA + Hacim kombinasyonu uygular.
   - **RSI + Bollinger Scalper:** Dip seviyelerden (aşırı satım) alıp üst bantta satar.
   - **Momentum EMA:** Trend yönünde işlem açar.
   - **Grid Micro Scalper:** Mikro geri çekilmelerde seri al-sat fırsatları yakalar.

6. **Modern Canlı Web Kontrol Paneli & Otomatik Raporlama:**
   - Canlı piyasa radarı, açık pozisyonlar, sanal/gerçek bakiye takibi.
   - Test bitiminde `reports/` klasörüne otomatik HTML karne ve JSON dökümü.

---

## 📦 Kurulum ve İlk Ayarlar

Proje Python 3.10+ ve sanal ortam (`venv`) ile tam uyumludur.

```bash
# 1. Sanal ortam oluşturma ve etkinleştirme
python -m venv .venv

# Windows Powershell / CMD:
.venv\Scripts\activate

# 2. Gereksinimleri yükleme:
pip install -r requirements.txt

# 3. Yapılandırma dosyalarını örneklerden oluşturma:
# Test modu için:
Copy-Item config.test.example.yaml config.test.yaml
# Canlı mod için (API anahtarlarınızı bu dosyaya yazacaksınız):
Copy-Item config.live.example.yaml config.live.yaml
```

---

## 🖥️ Çalıştırma ve Mod Geçişleri

Botu başlatırken `--mode` parametresi ile kolayca test veya canlı mod arasında geçiş yapabilirsiniz:

### 1. Web Takip Paneli ile Çalıştırma (Önerilen)

```bash
# 🟢 Test / Simülasyon Modunda Başlatma (Varsayılan: config.test.yaml)
.venv\Scripts\python main.py --mode test

# 🔴 Gerçek Emir (Live) Modunda Başlatma (Varsayılan: config.live.yaml)
.venv\Scripts\python main.py --mode live

# 📁 Özel bir config dosyası ile başlatma:
.venv\Scripts\python main.py --config ozel_ayar.yaml
```

Ardından tarayıcınızda açın:  
👉 **http://localhost:8000** (Varsayılan Giriş: `admin` / `admin123`)

---

### 2. Terminal (CLI) Modunda Çalıştırma

Terminalden doğrudan oturum başlatmak için `--cli` bayrağını kullanabilirsiniz:

```bash
# 🟢 15 Dakikalık Test Simülasyonu
.venv\Scripts\python main.py --mode test --cli --duration 15

# 🔴 Canlı Modda Belirli Bir Parite ile Çalıştırma
.venv\Scripts\python main.py --mode live --cli --duration 30 --symbol BTC_TRY --strategy adaptive_regime
```

**Kullanılabilir Parametreler:**
- `--mode`: `test` (Simülasyon) veya `live` (Gerçek Emir)
- `--config`: Özel config yaml dosya yolu
- `--cli`: Web paneli yerine Terminal CLI modunda çalıştır
- `--duration`: Oturum süresi (dakika)
- `--strategy`: `adaptive_regime`, `rsi_bollinger`, `momentum_ema`, `grid_scalper`
- `--symbol`: `AUTO` (Radar) veya `BTC_TRY`, `USDT_TRY`, `SOL_TRY` vb.
- `--port`: Web sunucu portu (varsayılan: 8000)

---

## 🧪 Testleri Çalıştırma

Tüm mod geçişleri, simülatör, risk yönetimi ve web paneli testlerini çalıştırmak için:

```bash
.venv\Scripts\python -m pytest tests/ -v
```

---

## 🔒 Güvenlik & Git Paylaşımı

Bu proje açık kaynak veya özel Git depolarına yüklenirken API güvenliğinizi koruyacak şekilde tasarlanmıştır:

- `.gitignore` dosyası `config.yaml`, `config.live.yaml`, `config.test.yaml`, logları ve geçmiş raporları otomatik olarak hariç tutar.
- Git'e göndermek için hazır şablonlar:
  - `config.test.example.yaml`
  - `config.live.example.yaml`
  - `config.example.yaml`
- Canlı modda kullanacağınız Binance TR API anahtarlarında para çekme yetkisini **asla** işaretlemeyin; yalnızca **Spot Alım-Satım** yetkisi verin.

---

## 📁 Proje Dosya Yapısı

```
binancetr-bot/
├── config.test.example.yaml  # Git için örnek test yapılandırma şablonu
├── config.live.example.yaml  # Git için örnek canlı işlem yapılandırma şablonu
├── config.example.yaml       # Git için genel şablon
├── config.test.yaml          # Yerel test ayarlarınız (.gitignore ile korunur)
├── config.live.yaml          # Yerel canlı ayarlarınız & API Key (.gitignore ile korunur)
├── config.py                 # Dinamik konfigürasyon yöneticisi
├── bot.py                    # Ana bot koordinatörü
├── main.py                   # CLI & Web mod değiştirici başlatıcı
├── core/
│   ├── binance_client.py     # Binance TR REST istemcisi
│   ├── market_data.py        # Canlı tahta ve teknik göstergeler
│   ├── market_scanner.py     # Otomatik radar piyasa tarayıcısı
│   ├── risk_manager.py       # TP, SL, Trailing Stop, Cooldown
│   ├── simulator.py          # Sanal bakiye simülatörü
│   └── live_trader.py        # Gerçek hesap emir motoru
├── strategies/               # Ticaret stratejileri
├── reporting/                # Performans ve rapor üretici
├── web/                      # Modern Web Paneli (FastAPI, HTML/CSS/JS)
├── reports/                  # Üretilen test raporları (.gitignore ile korunur)
├── data/                     # Yerel pozisyon verileri (.gitignore ile korunur)
└── tests/                    # Birim ve entegrasyon testleri
```
