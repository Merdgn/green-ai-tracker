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
            animation: false,
            scales: {
                x: { ticks: { color: "#ccc" }},
                y: { ticks: { color: "#ccc" }}
            }
        }
    });
}

function startLiveCharts(runId) {

    cpuChart = createChart(document.getElementById("cpuChart"), "CPU (%)", "#ff6384");
    gpuChart = createChart(document.getElementById("gpuChart"), "GPU (%)", "#36a2eb");
    ramChart = createChart(document.getElementById("ramChart"), "RAM (MB)", "#ffcd56");
    powerChart = createChart(document.getElementById("powerChart"), "Güç (W)", "#4bc0c0");

    setInterval(async () => {
    const res = await fetch(`/runs/${runId}/live`);
    const data = await res.json();

    if (!data.metrics) return;

    cpuChart.data.labels = data.metrics.map(m => m.time);
    gpuChart.data.labels = data.metrics.map(m => m.time);
    ramChart.data.labels = data.metrics.map(m => m.time);
    powerChart.data.labels = data.metrics.map(m => m.time);

    cpuChart.data.datasets[0].data = data.metrics.map(m => m.cpu);
    gpuChart.data.datasets[0].data = data.metrics.map(m => m.gpu);
    ramChart.data.datasets[0].data = data.metrics.map(m => m.ram);
    powerChart.data.datasets[0].data = data.metrics.map(m => m.power);

    cpuChart.update();
    gpuChart.update();
    ramChart.update();
    powerChart.update();
}, 1000);

}
