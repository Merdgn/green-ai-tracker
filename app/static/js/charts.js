function startCharts(runId) {

    const cpuCtx = document.getElementById("cpuChart").getContext("2d");
    const gpuCtx = document.getElementById("gpuChart").getContext("2d");

    let cpuData = [];
    let gpuData = [];
    let labels = [];

    const cpuChart = new Chart(cpuCtx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: "CPU Util (%)",
                data: cpuData,
                borderColor: "blue",
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            animation: false
        }
    });

    const gpuChart = new Chart(gpuCtx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: "GPU Util (%)",
                data: gpuData,
                borderColor: "red",
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            animation: false
        }
    });

    async function fetchMetrics() {
        const url = `/metrics/by_run/${runId}`;
console.log("FETCH URL:", url);
const res = await fetch(url);


        const json = await res.json();

        if (!json || !json.length) return;

        const latest = json[json.length - 1];

        cpuData.push(latest.cpu_util);
        gpuData.push(latest.gpu_util);
        labels.push(new Date(latest.ts).toLocaleTimeString());

        if (labels.length > 20) { 
            cpuData.shift();
            gpuData.shift();
            labels.shift();
        }

        cpuChart.update();
        gpuChart.update();
    }

    fetchMetrics();
    setInterval(fetchMetrics, 3000);
}
