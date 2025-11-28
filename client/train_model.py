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
with open(CONFIG_PATH, "r") as f:
    CONFIG = json.load(f)

API_URL = "http://127.0.0.1:8000"
EMAIL = CONFIG["email"]
API_KEY = CONFIG["api_key"]
MODEL_NAME = "pytorch-mnist-demo"


# ======================================
# 🔌 GPU İSTATİSTİĞİ İÇİN NVML (NVIDIA)
# ======================================
try:
    import pynvml

    pynvml.nvmlInit()
    GPU_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
    NVML_AVAILABLE = True
    print("✅ NVML yüklendi, GPU ölçümü aktif.")
except Exception as e:
    GPU_HANDLE = None
    NVML_AVAILABLE = False
    print("⚠️ NVML kullanılamıyor, GPU ölçümü devre dışı:", e)


def estimate_gpu_power(gpu_util):
    GPU_TDP = 60.0  # RTX 3050 Laptop için
    return (gpu_util / 100.0) * GPU_TDP


def get_gpu_stats():
    if NVML_AVAILABLE and GPU_HANDLE is not None:
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(GPU_HANDLE).gpu
            power_w = pynvml.nvmlDeviceGetPowerUsage(GPU_HANDLE) / 1000.0
            return float(util), float(power_w)
        except Exception:
            pass

    util = 0
    try:
        util = pynvml.nvmlDeviceGetUtilizationRates(GPU_HANDLE).gpu
    except:
        util = 0

    return float(util), float(estimate_gpu_power(util))


# ======================================
# 1) LOGIN → JWT TOKEN AL
# ======================================
def login():
    resp = requests.post(
        f"{API_URL}/auth/login",
        json={
            "name": "Miray",           # ← email değil, name kullanılacak
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
    cpu = psutil.cpu_percent(interval=0.3)
    mem_used = psutil.virtual_memory().used / 1024 / 1024
    gpu_util, gpu_watt = get_gpu_stats()

    payload = {
        "run_id": run_id,
        "cpu_util": cpu,
        "gpu_util": gpu_util,
        "gpu_power_w": gpu_watt,
        "mem_used_mb": mem_used,
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
    transform = transforms.Compose([transforms.ToTensor()])

    dataset = datasets.MNIST(
        root="./data",
        train=True,
        download=True,
        transform=transform
    )

    loader = torch.utils.data.DataLoader(dataset, batch_size=64, shuffle=True)
    model = Net()
    loss_fn = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    EPOCHS = 2  # Şimdilik düşük tut
    print("🧠 Eğitim başlıyor...")

    for epoch in range(EPOCHS):
        for i, (x, y) in enumerate(loader):
            optimizer.zero_grad()
            out = model(x)
            loss = loss_fn(out, y)
            loss.backward()
            optimizer.step()

            if i % 200 == 0:
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
    headers = login()
    run_id = start_run(headers)
    train_model(run_id, headers)
    finish_run(run_id, headers)
