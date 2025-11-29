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
            animation: false,
            responsive: true,
            scales: {
                x: { ticks: { color: "#999" } },
                y: { ticks: { color: "#999" } }
            }
        }
    });
}

function startMonitor() {

    cpuChart = createChart(document.getElementById("cpuChart"), "CPU (%)", "#ff6384");
    gpuChart = createChart(document.getElementById("gpuChart"), "GPU (%)", "#36a2eb");
    ramChart = createChart(document.getElementById("ramChart"), "RAM (MB)", "#ffcd56");
    powerChart = createChart(document.getElementById("powerChart"), "Güç (W)", "#4bc0c0");

    setInterval(async () => {
        const res = await fetch("/monitor/live");
        const data = await res.json();

        const time = new Date().toLocaleTimeString();

        cpuChart.data.labels.push(time);
        gpuChart.data.labels.push(time);
        ramChart.data.labels.push(time);
        powerChart.data.labels.push(time);

        cpuChart.data.datasets[0].data.push(data.cpu);
        gpuChart.data.datasets[0].data.push(data.gpu);
        ramChart.data.datasets[0].data.push(data.ram);
        powerChart.data.datasets[0].data.push(data.power);

        cpuChart.update();
        gpuChart.update();
        ramChart.update();
        powerChart.update();
    }, 1000);
}
