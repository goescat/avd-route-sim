"""Local web tool: draw a route on a map, then replay it as GPS updates to
an Android emulator (AVD) at a chosen movement speed."""

from flask import Flask, jsonify, render_template, request

from route_sim import EmulatorConsole, EmulatorConsoleError, RouteSimulator

app = Flask(__name__)

_sim: RouteSimulator | None = None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/start", methods=["POST"])
def start():
    global _sim
    if _sim is not None and _sim.is_alive():
        return jsonify({"ok": False, "error": "已有模擬正在執行，請先停止"}), 409

    data = request.get_json(force=True)
    points = data.get("points") or []
    speed_kmh = float(data.get("speed_kmh", 5))
    port = int(data.get("port", 5554))
    interval_s = float(data.get("interval_s", 1))
    loop = bool(data.get("loop", False))

    if len(points) < 2:
        return jsonify({"ok": False, "error": "路徑至少需要 2 個點"}), 400
    if speed_kmh <= 0:
        return jsonify({"ok": False, "error": "速度必須大於 0"}), 400

    try:
        _sim = RouteSimulator(points, speed_kmh, port, interval_s, loop=loop)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    _sim.start()
    return jsonify({"ok": True})


@app.route("/api/set_point", methods=["POST"])
def set_point():
    if _sim is not None and _sim.is_alive():
        return jsonify({"ok": False, "error": "路徑模擬正在執行中，請先停止再設定單點定位"}), 409

    data = request.get_json(force=True)
    try:
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "座標格式錯誤"}), 400
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return jsonify({"ok": False, "error": "座標超出範圍"}), 400
    port = int(data.get("port", 5554))

    console = EmulatorConsole(port)
    try:
        console.connect()
        console.geo_fix(lat, lon)
    except EmulatorConsoleError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    finally:
        console.close()

    return jsonify({"ok": True, "lat": lat, "lon": lon})


@app.route("/api/stop", methods=["POST"])
def stop():
    global _sim
    if _sim is not None and _sim.is_alive():
        _sim.stop()
    return jsonify({"ok": True})


@app.route("/api/status")
def status():
    if _sim is None:
        return jsonify({"status": "idle"})
    return jsonify(_sim.status())


if __name__ == "__main__":
    # 5000 is taken by macOS AirPlay Receiver (ControlCenter) by default.
    app.run(debug=True, port=8765)
