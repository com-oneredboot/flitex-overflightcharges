"""Unit tests for FIRIntersectionEngine._adjust_for_dateline.

Tests date line handling logic that shifts coordinates ±360° to maintain
geometric continuity for routes crossing the International Date Line.

Validates Requirements: 18.1, 18.2
"""

import pytest

from src.services.fir_intersection_engine import FIRIntersectionEngine


@pytest.fixture
def engine():
    return FIRIntersectionEngine()


class TestAdjustForDateline:
    """Tests for _adjust_for_dateline method."""

    def test_empty_list_returns_empty(self, engine):
        assert engine._adjust_for_dateline([]) == []

    def test_single_point_returns_unchanged(self, engine):
        coords = [(139.7, 35.7)]
        result = engine._adjust_for_dateline(coords)
        assert result == [(139.7, 35.7)]

    def test_no_crossing_returns_unchanged(self, engine):
        """Route within one hemisphere — no adjustment needed."""
        coords = [(-73.78, 40.64), (-0.46, 51.47)]  # JFK → LHR
        result = engine._adjust_for_dateline(coords)
        assert result == coords

    def test_eastbound_crossing_tokyo_to_la(self, engine):
        """Tokyo (lon=139.7) → LA (lon=-118.2) crosses the date line eastbound.

        The jump is ~258° which exceeds 180°, so LA's longitude should be
        shifted +360 to 241.8 for continuity.
        """
        coords = [(139.7, 35.7), (-118.2, 33.9)]
        result = engine._adjust_for_dateline(coords)
        assert result[0] == (139.7, 35.7)
        assert result[1] == pytest.approx((-118.2 + 360.0, 33.9))

    def test_westbound_crossing_la_to_tokyo(self, engine):
        """LA (lon=-118.2) → Tokyo (lon=139.7) crosses the date line westbound.

        The jump is ~258° which exceeds 180°, so Tokyo's longitude should be
        shifted -360 to -220.3 for continuity.
        """
        coords = [(-118.2, 33.9), (139.7, 35.7)]
        result = engine._adjust_for_dateline(coords)
        assert result[0] == (-118.2, 33.9)
        assert result[1] == pytest.approx((139.7 - 360.0, 35.7))

    def test_multi_point_route_with_crossing(self, engine):
        """Multi-waypoint Pacific route crossing the date line once."""
        coords = [
            (139.7, 35.7),   # Tokyo
            (170.0, 40.0),   # mid-Pacific (east of Tokyo)
            (-170.0, 45.0),  # just past the date line
            (-150.0, 50.0),  # continuing east
        ]
        result = engine._adjust_for_dateline(coords)
        # First two points unchanged
        assert result[0] == (139.7, 35.7)
        assert result[1] == (170.0, 40.0)
        # Third point shifted +360 for continuity (170 → -170 is a 340° jump)
        assert result[2] == pytest.approx((190.0, 45.0))
        # Fourth point also shifted +360
        assert result[3] == pytest.approx((210.0, 50.0))

    def test_consecutive_longitudes_stay_continuous(self, engine):
        """After adjustment, no consecutive longitude pair should jump > 180°."""
        coords = [
            (150.0, 30.0),
            (170.0, 35.0),
            (-170.0, 40.0),
            (-150.0, 45.0),
        ]
        result = engine._adjust_for_dateline(coords)
        for i in range(1, len(result)):
            delta = abs(result[i][0] - result[i - 1][0])
            assert delta <= 180.0, (
                f"Longitude jump {delta}° between points {i-1} and {i} exceeds 180°"
            )

    def test_latitudes_preserved(self, engine):
        """Date line adjustment must not alter latitude values."""
        coords = [(139.7, 35.7), (-118.2, 33.9)]
        result = engine._adjust_for_dateline(coords)
        assert result[0][1] == 35.7
        assert result[1][1] == 33.9

    def test_no_crossing_large_but_under_180(self, engine):
        """A 170° longitude difference should NOT trigger adjustment."""
        coords = [(10.0, 50.0), (-160.0, 50.0)]  # 170° apart
        result = engine._adjust_for_dateline(coords)
        assert result == coords
