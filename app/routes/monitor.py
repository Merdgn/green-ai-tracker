# app/routes/monitor.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse  # ← RedirectResponse eklendi
from fastapi.templating import Jinja2Templates
import psutil
import random

router = APIRouter(tags=["Monitor"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/monitor", response_class=HTMLResponse)
def monitor_page(request: Request):
    # Login değilse login sayfasına yönlendir
    if not getattr(request.state, "current_user", None):
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse("monitor.html", {"request": request})


@router.get("/monitor/live")
def monitor_live():
    """Gerçek zamanlı sistem bilgilerini JSON döndürür."""
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().used / (1024 * 1024)
    gpu = 0.0  # GPU yoksa 0 döndür
    power = random.uniform(10, 14)  # Test için fake değer

    return {
        "cpu": cpu,
        "ram": ram,
        "gpu": gpu,
        "power": power
    }
