import app as app_module
from route_sim import EmulatorConsoleError


class FakeSim:
    def __init__(self, alive=False):
        self._alive = alive
        self.started = False

    def is_alive(self):
        return self._alive

    def start(self):
        self.started = True


class FakeConsole:
    """Stands in for route_sim.EmulatorConsole so tests never touch a socket."""

    last_instance = None

    def __init__(self, port):
        self.port = port
        self.connected = False
        self.fixed = None
        FakeConsole.last_instance = self

    def connect(self):
        self.connected = True

    def geo_fix(self, lat, lon):
        self.fixed = (lat, lon)

    def close(self):
        pass


class FailingConnectConsole(FakeConsole):
    def connect(self):
        raise EmulatorConsoleError("無法連線到 127.0.0.1:5554")


def test_index_serves_html(client):
    res = client.get("/")
    assert res.status_code == 200


class TestStart:
    def test_rejects_fewer_than_two_points(self, client):
        res = client.post("/api/start", json={"points": [[25.0, 121.0]], "speed_kmh": 5})
        assert res.status_code == 400
        assert res.get_json()["ok"] is False

    def test_rejects_zero_speed(self, client):
        res = client.post(
            "/api/start",
            json={"points": [[25.0, 121.0], [25.1, 121.1]], "speed_kmh": 0},
        )
        assert res.status_code == 400

    def test_rejects_negative_speed(self, client):
        res = client.post(
            "/api/start",
            json={"points": [[25.0, 121.0], [25.1, 121.1]], "speed_kmh": -5},
        )
        assert res.status_code == 400

    def test_rejects_when_simulation_already_running(self, client):
        app_module._sim = FakeSim(alive=True)
        res = client.post(
            "/api/start",
            json={"points": [[25.0, 121.0], [25.1, 121.1]], "speed_kmh": 5},
        )
        assert res.status_code == 409

    def test_starts_simulation_with_valid_input(self, client, monkeypatch):
        created = {}

        def fake_route_simulator(points, speed_kmh, port, interval_s, loop=False):
            sim = FakeSim()
            created["sim"] = sim
            return sim

        monkeypatch.setattr(app_module, "RouteSimulator", fake_route_simulator)
        res = client.post(
            "/api/start",
            json={"points": [[25.0, 121.0], [25.1, 121.1]], "speed_kmh": 5},
        )
        assert res.status_code == 200
        assert res.get_json()["ok"] is True
        assert created["sim"].started is True


class TestSetPoint:
    def test_rejects_non_numeric_latitude(self, client):
        res = client.post("/api/set_point", json={"lat": "abc", "lon": 121.0, "port": 5554})
        assert res.status_code == 400
        assert res.get_json()["ok"] is False

    def test_rejects_non_numeric_longitude(self, client):
        res = client.post("/api/set_point", json={"lat": 25.0, "lon": "not-a-number", "port": 5554})
        assert res.status_code == 400

    def test_rejects_missing_longitude(self, client):
        res = client.post("/api/set_point", json={"lat": 25.0, "port": 5554})
        assert res.status_code == 400

    def test_rejects_empty_body(self, client):
        res = client.post("/api/set_point", json={})
        assert res.status_code == 400

    def test_rejects_latitude_out_of_range(self, client):
        res = client.post("/api/set_point", json={"lat": 999, "lon": 121.0, "port": 5554})
        assert res.status_code == 400

    def test_rejects_longitude_out_of_range(self, client):
        res = client.post("/api/set_point", json={"lat": 25.0, "lon": -200, "port": 5554})
        assert res.status_code == 400

    def test_accepts_boundary_coordinates(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "EmulatorConsole", FakeConsole)
        res = client.post("/api/set_point", json={"lat": 90, "lon": 180, "port": 5554})
        assert res.status_code == 200
        assert res.get_json()["ok"] is True

    def test_rejects_when_route_simulation_running(self, client):
        app_module._sim = FakeSim(alive=True)
        res = client.post("/api/set_point", json={"lat": 25.0, "lon": 121.0, "port": 5554})
        assert res.status_code == 409

    def test_sends_geo_fix_on_valid_coordinates(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "EmulatorConsole", FakeConsole)
        res = client.post(
            "/api/set_point",
            json={"lat": 24.1262570, "lon": 120.5659350, "port": 5554},
        )
        data = res.get_json()
        assert res.status_code == 200
        assert data == {"ok": True, "lat": 24.1262570, "lon": 120.5659350}
        assert FakeConsole.last_instance.fixed == (24.1262570, 120.5659350)

    def test_reports_error_when_console_cannot_connect(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "EmulatorConsole", FailingConnectConsole)
        res = client.post("/api/set_point", json={"lat": 25.0, "lon": 121.0, "port": 5554})
        assert res.status_code == 400
        assert res.get_json()["ok"] is False


class TestStopAndStatus:
    def test_status_is_idle_with_no_simulation(self, client):
        res = client.get("/api/status")
        assert res.get_json()["status"] == "idle"

    def test_stop_is_a_no_op_with_no_simulation(self, client):
        res = client.post("/api/stop")
        assert res.status_code == 200
        assert res.get_json()["ok"] is True

    def test_stop_stops_a_running_simulation(self, client):
        stopped = {"called": False}

        class StoppableSim(FakeSim):
            def __init__(self):
                super().__init__(alive=True)

            def stop(self):
                stopped["called"] = True

        app_module._sim = StoppableSim()
        res = client.post("/api/stop")
        assert res.status_code == 200
        assert stopped["called"] is True
