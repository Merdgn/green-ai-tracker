(() => {
  let cpuChart=null, gpuChart=null, ramChart=null, powerChart=null;
  let inFlight=false;

  function createChart(canvasId, label, color, yMax=null) {
    const el=document.getElementById(canvasId);
    if (!el) return null;
    const ctx=el.getContext("2d");
    return new Chart(ctx, {
      type:"line",
      data:{ labels:[], datasets:[{ label, data:[], borderColor:color, borderWidth:2, tension:0.2, pointRadius:2 }] },
      options:{
        responsive:true, maintainAspectRatio:false, animation:false,
        scales:{
          x:{ ticks:{ color:"#666" } },
          y:{ ticks:{ color:"#666" }, suggestedMin:0, ...(yMax!==null?{suggestedMax:yMax}:{}) }
        }
      }
    });
  }

  function pushPoint(chart, label, value, maxPoints=60) {
    if (!chart) return;
    chart.data.labels.push(label);
    chart.data.datasets[0].data.push(value);
    if (chart.data.labels.length > maxPoints) {
      chart.data.labels.shift();
      chart.data.datasets[0].data.shift();
    }
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
  }

  async function tick() {
    if (inFlight) return;
    inFlight = true;
    try {
      const res = await fetch("/monitor/live", { cache:"no-store" });
      const data = await res.json();
      const t = new Date().toLocaleTimeString();

      pushPoint(cpuChart, t, Number(data.cpu ?? 0));
      pushPoint(gpuChart, t, Number(data.gpu ?? 0));
      pushPoint(ramChart, t, Number(data.ram ?? 0));
      pushPoint(powerChart, t, Number(data.power_gpu_w ?? 0)); // güç grafiğinde GPU gücü

      cpuChart?.update(); gpuChart?.update(); ramChart?.update(); powerChart?.update();

      // CO2 yazıları (kg)
      setText("co2TotalValue", (Number(data.co2_total_kg ?? 0)).toFixed(6));
      setText("co2GpuValue",   (Number(data.co2_gpu_kg ?? 0)).toFixed(6));

      // debug istersen:
      // setText("dtValue", String(data.dt_s ?? ""));
    } finally {
      inFlight = false;
    }
  }

  function startMonitor() {
    cpuChart?.destroy(); gpuChart?.destroy(); ramChart?.destroy(); powerChart?.destroy();

    cpuChart   = createChart("cpuChart",   "CPU (%)", "#ff6384", 100);
    gpuChart   = createChart("gpuChart",   "GPU (%)", "#36a2eb", 100);
    ramChart   = createChart("ramChart",   "RAM (MB)", "#ffcd56");
    powerChart = createChart("powerChart", "GPU Güç (W)", "#4bc0c0", 120);

    const loop = async () => {
      const t0 = performance.now();
      await tick().catch(()=>{});
      const elapsed = performance.now() - t0;
      const wait = Math.max(0, 1000 - elapsed);
      setTimeout(loop, wait);
    };

    loop();
  }

  document.addEventListener("DOMContentLoaded", startMonitor);
})();
