// app/static/js/run_live.js
let cpuChart, gpuChart, ramChart, powerChart;

function createChart(ctx, label, color) {
    return new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [{
                label: label,
                data: [],
                borderColor: color,
                borderWidth: 2,
                tension: 0.2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            scales: {
                x: {
                    ticks: { color: "#666" }
                },
                y: {
                    ticks: { color: "#666" },
                    beginAtZero: true
                }
            },
            plugins: {
                legend: {
                    display: true
                }
            }
        }
    });
}

function startLiveCharts(runId) {

    cpuChart   = createChart(document.getElementById("cpuChart"),   "CPU (%)",       "#ff6384");
    gpuChart   = createChart(document.getElementById("gpuChart"),   "GPU (%)",       "#36a2eb");
    ramChart   = createChart(document.getElementById("ramChart"),   "RAM (MB)",      "#ffcd56");
    powerChart = createChart(document.getElementById("powerChart"), "Güç (W)",       "#4bc0c0");

    // Her saniye backend'den metrikleri çek
    setInterval(async () => {
        try {
            const res  = await fetch(`/runs/${runId}/live`);
            if (!res.ok) {
                console.error("Live metrics isteği hata:", res.status);
                return;
            }

            const data = await res.json();
            if (!data.metrics || !data.metrics.length) {
                return;
            }

            // Zaman etiketleri
            const labels = data.metrics.map(m => m.time);

            cpuChart.data.labels   = labels;
            gpuChart.data.labels   = labels;
            ramChart.data.labels   = labels;
            powerChart.data.labels = labels;

            cpuChart.data.datasets[0].data   = data.metrics.map(m => m.cpu);
            gpuChart.data.datasets[0].data   = data.metrics.map(m => m.gpu);
            ramChart.data.datasets[0].data   = data.metrics.map(m => m.ram);
            powerChart.data.datasets[0].data = data.metrics.map(m => m.power);

            cpuChart.update();
            gpuChart.update();
            ramChart.update();
            powerChart.update();
        } catch (err) {
            console.error("Live metrics okunamadı:", err);
        }
    }, 1000);
}
