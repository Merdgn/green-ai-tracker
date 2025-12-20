# Green AI Tracker — Yapay Zekâ Modellerinin Enerji/Emisyon Takip Sistemi

## 1. Proje Özeti
Green AI Tracker; makine öğrenmesi / derin öğrenme eğitimi sırasında oluşan **CPU, GPU, RAM ve güç tüketimi** metriklerini toplayıp, bu metriklerden **enerji (kWh)** ve **karbon emisyonu (kg CO₂e)** tahmini yapan ve sonuçları web arayüzünde raporlayan bir izleme sistemidir.

Sistem, “run” (eğitim çalışması) kavramı üzerinden ilerler:
- Her eğitim başlatıldığında yeni bir **Run** oluşturulur.
- Eğitim boyunca belirli aralıklarla metrikler toplanır ve API’ye gönderilir.
- Eğitim sonunda Run durdurulur; **enerji/emisyon hesaplaması** yapılarak veritabanına kaydedilir.
- Dashboard ve Run Detay sayfalarından raporlar izlenir.

---

## 2. Temel Özellikler
- **Run Yönetimi:** Run başlatma, run detay görüntüleme, run durdurma
- **Canlı Metrikler:** CPU/GPU/RAM/Güç ölçümleri
- **Enerji & Emisyon Hesabı:** kWh ve kg CO₂e çıktıları
- **Dashboard:**
  - toplam kullanıcı/cihaz/run/metrik
  - toplam emisyon (kg CO₂e)
  - model başına ortalama enerji (kWh)
  - en çok emisyon üreten model
  - popüler model
- **Web Arayüz (UI):** Dashboard, monitor, run detay, liste ekranları
- **API Dokümantasyonu:** FastAPI ile otomatik Swagger (OpenAPI)

---

## 3. Kullanılan Teknolojiler
**Backend**
- Python
- FastAPI
- SQLAlchemy (ORM)
- PostgreSQL (veri tabanı)

**Client (Eğitim/Tespit Scripti)**
- Python
- psutil (CPU/RAM ölçümü)
- NVIDIA NVML (GPU güç ve kullanım ölçümü)
- requests (API iletişimi)

**Frontend**
- Jinja2 Template (HTML)
- Bootstrap (UI bileşenleri)
- Chart.js (grafikler)
- JavaScript (canlı veri çekme)

---

## 4. Proje Klasör Yapısı (Özet)
Proje iki ana parçadan oluşur:

- `app/` : FastAPI sunucusu (API + UI)
- `client/` : Eğitim scripti (ör. MNIST) + metrik gönderimi

Örnek (genel):
- `app/main.py` : FastAPI giriş noktası
- `app/models.py` : ORM tabloları (User, Device, Run, Metric, Emission)
- `app/routes/` : endpoint’ler (runs, metrics, dashboard, monitor, auth, devices, emissions)
- `app/templates/` : HTML sayfaları (dashboard, run_detail, monitor vb.)
- `app/static/js/` : canlı grafik ve izleme scriptleri
- `client/train_model.py` : eğitimi başlatır + metrikleri API’ye yollar

---

## 5. Kurulum ve Çalıştırma (Adım Adım)

### 5.1. Ön Koşullar
- Python 3.10+ (önerilir)
- PostgreSQL (çalışır durumda olmalı)
-  NVIDIA GPU varsa NVML ile GPU güç/usage ölçümü aktif olur

> Not: Veritabanı bağlantı ayarları `app/database.py` içinde tanımlıdır. PostgreSQL kullanıcı/şifre/db bilgileri kendi ortamına göre uyarlanmalıdır.

---

## 5. Kurulum ve Çalıştırma (Adım Adım)

### 5.2. Sanal Ortam (venv) Oluşturma ve Aktif Etme

**Windows (PowerShell):**
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 5.3. Backend Bağımlılıklarını Kurma
Proje kök dizinindeyken:
```bash
pip install -r app/requirements.txt
```
---

## 6. Sistemi Çalıştırma

### 6.1. Backend’i Başlatma
```bash
uvicorn app.main:app --reload
```

### 6.2. Client (Eğitim + Metrik Gönderimi) Çalıştırma
Yeni bir terminalde:
```bash
cd client
python train_model.py
```
---