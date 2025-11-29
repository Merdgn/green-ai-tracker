# app/routes/monitor.py
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import psutil
import json

router = APIRouter()

@router.get("/monitor", response_class=HTMLResponse)
def monitor_page():
    html = """
    <html>
    <head>
        <title>System Monitor</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>

    <body style="background:#0f172a; color:white; font-family:Arial;">
        <h1>🖥 Sistem Canlı İzleme Paneli</h1>
        <hr>

        <canvas id="cpuChart" width="400" height="150"></canvas>
        <canvas id="ramChart" width="400" height="150"></canvas>

        <script>
            let cpuData = [];
            let ramData = [];
            let labels = [];

            const cpuCtx = document.getElementById('cpuChart').getContext('2d');
            const ramCtx = document.getElementById('ramChart').getContext('2d');

            const cpuChart = new Chart(cpuCtx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'CPU (%)',
                        data: cpuData,
                        borderColor: 'lime',
                        borderWidth: 2
                    }]
                },
            });

            const ramChart = new Chart(ramCtx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'RAM (MB)',
                        data: ramData,
                        borderColor: 'cyan',
                        borderWidth: 2
                    }]
                },
            });

            function updateCharts() {
                fetch('/monitor/data')
                    .then(r => r.json())
                    .then(data => {
                        const time = new Date().toLocaleTimeString();
                        labels.push(time);

                        cpuData.push(data.cpu);
                        ramData.push(data.ram);

                        if (labels.length > 20) {
                            labels.shift();
                            cpuData.shift();
                            ramData.shift();
                        }

                        cpuChart.update();
                        ramChart.update();
                    });
            }

            setInterval(updateCharts, 1500);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)


@router.get("/monitor/data")
def monitor_data():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().used // (1024 * 1024)
    return {"cpu": cpu, "ram": ram}
