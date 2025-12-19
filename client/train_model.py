import time
import psutil
import requests
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms
import json
import os

# ======================================
# 🔧 CONFIG.json OKU
# ======================================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

API_URL = "http://127.0.0.1:8000"
EMAIL = CONFIG.get("email", "")
API_KEY = CONFIG["api_key"]
MODEL_NAME = "pytorch-mnist-demo"

# ======================================
# 🔌 GPU İSTATİSTİĞİ İÇİN NVML (NVIDIA)
# ======================================
NVML_AVAILABLE = False
GPU_HANDLE = None

def init_nvml():
    global NVML_AVAILABLE, GPU_HANDLE
    try:
        import pynvml
        pynvml.nvmlInit()

        # İstersen env'den GPU index seçebil:
        # set NVML_GPU_INDEX=0
        gpu_index = int(os.getenv("NVML_GPU_INDEX", "0"))

        GPU_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
        name = pynvml.nvmlDeviceGetName(GPU_HANDLE)
        NVML_AVAILABLE = True
        print(f"✅ NVML yüklendi, GPU ölçümü aktif. (index={gpu_index}, name={name})")
    except Exception as e:
        GPU_HANDLE = None
        NVML_AVAILABLE = False
        print("⚠️ NVML kullanılamıyor, GPU ölçümü devre dışı:", e)

def estimate_gpu_power(gpu_util):
    GPU_TDP = 60.0  # RTX 3050 Laptop için (yaklaşık)
    return (gpu_util / 100.0) * GPU_TDP

def get_gpu_stats():
    """
    NVML util bazen çok kısa iş yüklerinde 0 dönebilir.
    O yüzden iki hızlı örnek alıp max seçiyoruz.
    """
    if not NVML_AVAILABLE or GPU_HANDLE is None:
        return 0.0, 0.0

    try:
        import pynvml

        util1 = float(pynvml.nvmlDeviceGetUtilizationRates(GPU_HANDLE).gpu)
        power1 = float(pynvml.nvmlDeviceGetPowerUsage(GPU_HANDLE) / 1000.0)

        time.sleep(0.05)  # 50ms
        util2 = float(pynvml.nvmlDeviceGetUtilizationRates(GPU_HANDLE).gpu)
        power2 = float(pynvml.nvmlDeviceGetPowerUsage(GPU_HANDLE) / 1000.0)

        util = max(util1, util2)
        power_w = max(power1, power2)
        return util, power_w
    except Exception:
        # NVML hata verirse tahmini güçle dön
        util = 0.0
        try:
            import pynvml
            util = float(pynvml.nvmlDeviceGetUtilizationRates(GPU_HANDLE).gpu)
        except Exception:
            util = 0.0
        return util, float(estimate_gpu_power(util))

# ======================================
# 1) LOGIN → JWT TOKEN AL
# ======================================
def login():
    resp = requests.post(
        f"{API_URL}/auth/login",
        json={
            "name": "Miray",   # API'nizde name ile login var
            "api_key": API_KEY
        }
    )

    if resp.status_code != 200:
        print("❌ Login başarısız:", resp.text)
        raise SystemExit(1)

    token = resp.json()["access_token"]
    print("🔑 Login başarılı!")
    return {"Authorization": f"Bearer {token}"}

# ======================================
# 2) RUN BAŞLAT
# ======================================
def start_run(headers):
    resp = requests.post(
        f"{API_URL}/runs/",
        json={"model_name": MODEL_NAME},
        headers=headers
    )

    print("📌 /runs RAW:", resp.text)

    data = resp.json()
    run_id = data["id"]

    print(f"🚀 Run başladı → ID: {run_id}")
    return run_id

# ======================================
# 3) METRİK GÖNDER
# ======================================
def send_metric(run_id, headers):
    """
    ÖNEMLİ: GPU util'i okumadan önce 0.3s beklemek GPU'yu kaçırıyordu.
    Bu yüzden CPU ölçümünü bloklamıyoruz.
    """
    # GPU ölçümünü ÖNCE al (beklemesiz)
    if torch.cuda.is_available():
        # CUDA işlerini bitirip ölçüme yakınlaştırır
        torch.cuda.synchronize()

    gpu_util, gpu_watt = get_gpu_stats()

    # CPU ölçümünü bloklamadan al
    cpu = psutil.cpu_percent(interval=0.0)  # 0.0 -> beklemez
    mem_used = psutil.virtual_memory().used / 1024 / 1024

    payload = {
        "run_id": run_id,
        "cpu_util": float(cpu),
        "gpu_util": float(gpu_util),
        "gpu_power_w": float(gpu_watt),
        "mem_used_mb": float(mem_used),
    }

    r = requests.post(
        f"{API_URL}/metrics/",
        json=payload,
        headers=headers
    )

    if r.status_code not in (200, 201):
        print("⚠️ Metrik hatası:", r.status_code, r.text)
    else:
        print("📡 Metrik gönderildi:", payload)

# ======================================
# 4) MODEL EĞİT
# ======================================
class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.flatten = nn.Flatten()
        self.fc1 = nn.Linear(28 * 28, 128)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.flatten(x)
        x = self.relu(self.fc1(x))
        return self.fc2(x)

def train_model(run_id, headers):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🖥️ Eğitim cihazı: {device}")

    # CUDA ise cuDNN optimizasyonu
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True

    transform = transforms.Compose([transforms.ToTensor()])
    dataset = datasets.MNIST(root="./data", train=True, download=True, transform=transform)

    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=256,   # biraz büyütmek GPU'yu daha görünür yapar
        shuffle=True,
        num_workers=0,
        pin_memory=(device.type == "cuda")
    )

    model = Net().to(device)
    loss_fn = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    EPOCHS = 10
    print("🧠 Eğitim başlıyor...")

    # CPU percent'i ilk çağrıda daha sağlıklı almak için prime
    psutil.cpu_percent(interval=None)

    for epoch in range(EPOCHS):
        for i, (x, y) in enumerate(loader):
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)

            optimizer.zero_grad()
            out = model(x)
            loss = loss_fn(out, y)
            loss.backward()
            optimizer.step()

            if i % 100 == 0:
                print(f"Epoch {epoch+1}/{EPOCHS} | Loss: {loss.item():.4f}")
                send_metric(run_id, headers)

    print("🎉 Eğitim bitti!")
    return model

# ======================================
# 5) RUN STOP + EMISSION
# ======================================
def finish_run(run_id, headers):
    r = requests.post(f"{API_URL}/runs/{run_id}/stop", headers=headers)
    print("⏹ Run durduruldu:", r.status_code)

    r2 = requests.post(f"{API_URL}/emissions/recalc/{run_id}", headers=headers)
    print("🌱 Emisyon hes.", r2.status_code, r2.text)

# ======================================
# MAIN
# ======================================
if __name__ == "__main__":
    init_nvml()
    headers = login()
    run_id = start_run(headers)
    train_model(run_id, headers)
    finish_run(run_id, headers)
