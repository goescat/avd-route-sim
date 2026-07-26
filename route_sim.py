"""Core logic: route geometry, Android emulator console client, and the
background thread that walks a drawn path and pushes GPS fixes to an AVD."""

import math
import os
import socket
import threading
import time

EARTH_RADIUS_M = 6371000.0
AUTH_TOKEN_PATH = os.path.expanduser("~/.emulator_console_auth_token")


def haversine_m(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1, math.sqrt(a)))


def build_route(points):
    """points: list of (lat, lon). Returns list of dicts with cumulative
    distance at each waypoint, plus the total route length in meters."""
    if len(points) < 2:
        raise ValueError("路徑至少需要 2 個點")
    route = [{"lat": points[0][0], "lon": points[0][1], "dist": 0.0}]
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(points, points[1:]):
        seg = haversine_m(lat1, lon1, lat2, lon2)
        total += seg
        route.append({"lat": lat2, "lon": lon2, "dist": total})
    return route, total


def interpolate(route, target_dist):
    """Linear interpolation of lat/lon at target_dist meters along route."""
    if target_dist <= 0:
        p = route[0]
        return p["lat"], p["lon"]
    if target_dist >= route[-1]["dist"]:
        p = route[-1]
        return p["lat"], p["lon"]
    for prev, nxt in zip(route, route[1:]):
        if prev["dist"] <= target_dist <= nxt["dist"]:
            seg_len = nxt["dist"] - prev["dist"]
            frac = 0.0 if seg_len == 0 else (target_dist - prev["dist"]) / seg_len
            lat = prev["lat"] + (nxt["lat"] - prev["lat"]) * frac
            lon = prev["lon"] + (nxt["lon"] - prev["lon"]) * frac
            return lat, lon
    p = route[-1]
    return p["lat"], p["lon"]


class EmulatorConsoleError(RuntimeError):
    pass


class EmulatorConsole:
    """Minimal client for the Android emulator console (telnet-style line
    protocol on localhost:<port>, default 5554)."""

    def __init__(self, port, host="127.0.0.1", timeout=5):
        self.port = port
        self.host = host
        self.timeout = timeout
        self.sock = None

    def connect(self):
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as exc:
            raise EmulatorConsoleError(
                f"無法連線到 {self.host}:{self.port}，請確認 AVD 正在執行且 console port 正確"
            ) from exc
        self.sock.settimeout(self.timeout)
        self._read()  # banner
        if os.path.exists(AUTH_TOKEN_PATH):
            with open(AUTH_TOKEN_PATH) as f:
                token = f.read().strip()
            self._send(f"auth {token}")

    def _send(self, line):
        self.sock.sendall((line + "\r\n").encode("utf-8"))
        return self._read()

    def _read(self):
        try:
            return self.sock.recv(4096).decode("utf-8", errors="ignore")
        except socket.timeout:
            return ""

    def geo_fix(self, lat, lon):
        # NOTE: emulator console expects "geo fix <longitude> <latitude>"
        reply = self._send(f"geo fix {lon:.6f} {lat:.6f}")
        if "KO" in reply:
            raise EmulatorConsoleError(f"emulator 拒絕指令: {reply.strip()}")

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None


class RouteSimulator(threading.Thread):
    """Walks a drawn path at a constant speed, sending periodic geo fix
    updates to an AVD via the emulator console."""

    def __init__(self, points, speed_kmh, port, interval_s=1.0, loop=False):
        super().__init__(daemon=True)
        self.route, self.total_dist = build_route(points)
        self.speed_mps = speed_kmh * 1000.0 / 3600.0
        self.port = port
        self.interval_s = max(0.1, interval_s)
        self.loop = loop
        self._stop_flag = threading.Event()
        self._lock = threading.Lock()
        self._traveled = 0.0
        self._current = (self.route[0]["lat"], self.route[0]["lon"])
        self._status = "pending"  # pending -> running -> done|stopped|error
        self._error = None
        self._laps = 0

    def stop(self):
        self._stop_flag.set()

    def status(self):
        with self._lock:
            return {
                "status": self._status,
                "error": self._error,
                "traveled_m": round(self._traveled, 1),
                "total_m": round(self.total_dist, 1),
                "progress": 0 if self.total_dist == 0 else min(1.0, self._traveled / self.total_dist),
                "lat": self._current[0],
                "lon": self._current[1],
                "laps": self._laps,
            }

    def _set(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, f"_{k}", v)

    def run(self):
        console = EmulatorConsole(self.port)
        try:
            console.connect()
        except EmulatorConsoleError as exc:
            self._set(status="error", error=str(exc))
            return

        self._set(status="running")
        distance_per_tick = self.speed_mps * self.interval_s
        traveled = 0.0
        try:
            while not self._stop_flag.is_set():
                lat, lon = interpolate(self.route, traveled)
                console.geo_fix(lat, lon)
                self._set(traveled=traveled, current=(lat, lon))
                if traveled >= self.total_dist:
                    if not self.loop:
                        self._set(status="done")
                        break
                    with self._lock:
                        self._laps += 1
                    traveled = 0.0
                else:
                    traveled = min(self.total_dist, traveled + distance_per_tick)
                time.sleep(self.interval_s)
            else:
                self._set(status="stopped")
        except EmulatorConsoleError as exc:
            self._set(status="error", error=str(exc))
        finally:
            console.close()
