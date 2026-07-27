const map = L.map("map").setView([25.0330, 121.5654], 15); // Taipei 101, pan/zoom to your area
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
  maxZoom: 19,
}).addTo(map);

let points = []; // [[lat, lon], ...]
const markers = [];
const polyline = L.polyline([], { color: "#2563eb" }).addTo(map);
let posMarker = null;
let running = false;
let pollTimer = null;

let mode = "route"; // "route" | "point"
let pointMarker = null;

function setMode(newMode) {
  mode = newMode;
  document.getElementById("route-panel").classList.toggle("hidden", mode !== "route");
  document.getElementById("point-panel").classList.toggle("hidden", mode !== "point");
}

document.getElementById("mode-route").onchange = () => setMode("route");
document.getElementById("mode-point").onchange = () => setMode("point");

function updatePointMarker(lat, lon) {
  const latlng = [lat, lon];
  if (!pointMarker) {
    pointMarker = L.circleMarker(latlng, { radius: 7, color: "#f59e0b", fillOpacity: 1 }).addTo(map);
  } else {
    pointMarker.setLatLng(latlng);
  }
}

function readPointInputs() {
  const raw = document.getElementById("point-coord").value;
  const parts = raw.split(",").map((s) => parseFloat(s.trim()));
  if (parts.length !== 2 || parts.some(Number.isNaN)) return null;
  const [lat, lon] = parts;
  return { lat, lon };
}

document.getElementById("point-coord").addEventListener("change", () => {
  const p = readPointInputs();
  if (p) updatePointMarker(p.lat, p.lon);
});

document.getElementById("set-point").onclick = async () => {
  const p = readPointInputs();
  const msgEl = document.getElementById("st-point-msg");
  const errEl = document.getElementById("st-error");
  msgEl.textContent = "";
  errEl.textContent = "";
  if (!p) {
    errEl.textContent = "請輸入有效的緯度與經度";
    return;
  }
  const res = await fetch("/api/set_point", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      lat: p.lat,
      lon: p.lon,
      port: parseInt(document.getElementById("port").value, 10),
    }),
  });
  const data = await res.json();
  if (!data.ok) {
    errEl.textContent = "設定失敗: " + data.error;
    return;
  }
  updatePointMarker(data.lat, data.lon);
  msgEl.textContent = `已設定定位: ${data.lat.toFixed(6)}, ${data.lon.toFixed(6)}`;
};

function redraw() {
  polyline.setLatLngs(points);
}

function addMarker(latlng) {
  const m = L.circleMarker(latlng, { radius: 5, color: "#2563eb" }).addTo(map);
  markers.push(m);
}

map.on("click", (e) => {
  if (mode === "point") {
    document.getElementById("point-coord").value =
      `${e.latlng.lat.toFixed(7)}, ${e.latlng.lng.toFixed(7)}`;
    updatePointMarker(e.latlng.lat, e.latlng.lng);
    return;
  }
  if (running) return;
  points.push([e.latlng.lat, e.latlng.lng]);
  addMarker(e.latlng);
  redraw();
});

document.getElementById("undo").onclick = () => {
  if (running) return;
  points.pop();
  const m = markers.pop();
  if (m) map.removeLayer(m);
  redraw();
};

document.getElementById("clear").onclick = () => {
  if (running) return;
  points = [];
  markers.splice(0).forEach((m) => map.removeLayer(m));
  redraw();
};

document.getElementById("preset").onchange = (e) => {
  if (e.target.value) document.getElementById("speed").value = e.target.value;
};

document.getElementById("start").onclick = async () => {
  if (points.length < 2) {
    alert("路徑至少需要 2 個點");
    return;
  }
  const body = {
    points,
    speed_kmh: parseFloat(document.getElementById("speed").value),
    port: parseInt(document.getElementById("port").value, 10),
    interval_s: parseFloat(document.getElementById("interval").value),
    loop: document.getElementById("loop").checked,
  };
  const res = await fetch("/api/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!data.ok) {
    alert("啟動失敗: " + data.error);
    return;
  }
  running = true;
  startPolling();
};

document.getElementById("stop").onclick = async () => {
  await fetch("/api/stop", { method: "POST" });
  running = false;
  stopPolling();
};

function startPolling() {
  stopPolling();
  pollTimer = setInterval(pollStatus, 1000);
  pollStatus();
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}

async function pollStatus() {
  const res = await fetch("/api/status");
  const s = await res.json();
  document.getElementById("st-status").textContent = s.status || "idle";
  document.getElementById("st-error").textContent = s.error || "";
  document.getElementById("st-laps").textContent = s.laps || 0;
  if (s.total_m !== undefined) {
    document.getElementById("st-progress").textContent =
      `${s.traveled_m.toFixed(1)} / ${s.total_m.toFixed(1)} m (${(s.progress * 100).toFixed(0)}%)`;
  }
  if (s.lat !== undefined) {
    document.getElementById("st-latlon").textContent = `${s.lat.toFixed(6)}, ${s.lon.toFixed(6)}`;
    const latlng = [s.lat, s.lon];
    if (!posMarker) {
      posMarker = L.circleMarker(latlng, { radius: 7, color: "#dc2626", fillOpacity: 1 }).addTo(map);
    } else {
      posMarker.setLatLng(latlng);
    }
  }
  if (s.status === "done" || s.status === "stopped" || s.status === "error") {
    running = false;
    stopPolling();
  }
}
