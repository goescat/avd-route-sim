import pytest

from route_sim import EmulatorConsole, EmulatorConsoleError, build_route, haversine_m, interpolate


class FakeSocket:
    """Stands in for a real TCP socket to the emulator console."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, n):
        return self.replies.pop(0) if self.replies else b""

    def settimeout(self, timeout):
        pass

    def close(self):
        pass


class TestHaversine:
    def test_zero_distance_for_same_point(self):
        assert haversine_m(25.0, 121.0, 25.0, 121.0) == pytest.approx(0.0, abs=1e-6)

    def test_one_degree_latitude_is_about_111km(self):
        d = haversine_m(0.0, 0.0, 1.0, 0.0)
        assert d == pytest.approx(111195, rel=0.01)


class TestBuildRoute:
    def test_rejects_fewer_than_two_points(self):
        with pytest.raises(ValueError):
            build_route([(25.0, 121.0)])

    def test_rejects_empty_points(self):
        with pytest.raises(ValueError):
            build_route([])

    def test_accumulates_distance_across_segments(self):
        points = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]
        route, total = build_route(points)
        assert [p["dist"] for p in route] == [0.0, route[1]["dist"], total]
        assert route[1]["dist"] < total
        assert total == pytest.approx(route[1]["dist"] * 2, rel=0.01)


class TestInterpolate:
    def test_clamps_to_start_when_before_route(self):
        route, _ = build_route([(0.0, 0.0), (0.0, 2.0)])
        assert interpolate(route, -100) == (0.0, 0.0)

    def test_clamps_to_end_when_past_route(self):
        route, total = build_route([(0.0, 0.0), (0.0, 2.0)])
        assert interpolate(route, total + 1000) == (0.0, 2.0)

    def test_midpoint_is_linearly_interpolated(self):
        route, total = build_route([(0.0, 0.0), (0.0, 2.0)])
        lat, lon = interpolate(route, total / 2)
        assert lat == pytest.approx(0.0, abs=1e-9)
        assert lon == pytest.approx(1.0, abs=0.01)


class TestEmulatorConsole:
    def test_geo_fix_sends_longitude_before_latitude(self):
        console = EmulatorConsole(5554)
        console.sock = FakeSocket([b"OK\r\n"])
        console.geo_fix(25.033000, 121.565400)
        sent = console.sock.sent[-1].decode()
        assert sent.startswith("geo fix 121.565400 25.033000")

    def test_geo_fix_raises_on_ko_reply(self):
        console = EmulatorConsole(5554)
        console.sock = FakeSocket([b"KO: bad params\r\n"])
        with pytest.raises(EmulatorConsoleError):
            console.geo_fix(25.0, 121.0)
