"""Unit tests for FIRIntersectionEngine deduplication and merging methods.

Tests _haversine_m, _deduplicate_intersections, and _merge_adjacent_same_fir
implementations for intersection deduplication and segment merging.

Validates Requirements: 7.5, 7.6, 19.1, 19.2
"""

import pytest

from src.services.fir_intersection_engine import FIRIntersectionEngine


@pytest.fixture
def engine():
    return FIRIntersectionEngine()


def _make_segment(
    icao_code: str,
    entry_lat: float = 50.0,
    entry_lon: float = 0.0,
    exit_lat: float = 51.0,
    exit_lon: float = 1.0,
    distance_km: float = 100.0,
    distance_nm: float = 54.0,
    route_fraction: float = 0.5,
    segment_geojson: dict | None = None,
) -> dict:
    """Helper to build a segment dict matching PostGIS intersection output."""
    return {
        "icao_code": icao_code,
        "fir_name": f"{icao_code} FIR",
        "country": "Test",
        "country_code": "TS",
        "segment_geojson": segment_geojson,
        "segment_distance_km": distance_km,
        "segment_distance_nm": distance_nm,
        "entry_lat": entry_lat,
        "entry_lon": entry_lon,
        "exit_lat": exit_lat,
        "exit_lon": exit_lon,
        "route_fraction": route_fraction,
    }


# ---------------------------------------------------------------------------
# _haversine_m
# ---------------------------------------------------------------------------
class TestHaversineM:
    """Tests for the _haversine_m static method."""

    def test_same_point_returns_zero(self):
        assert FIRIntersectionEngine._haversine_m(51.0, 0.0, 51.0, 0.0) == 0.0

    def test_known_short_distance(self):
        """Two points ~5 m apart should return roughly 5 m."""
        # ~0.000045 degrees latitude ≈ 5 m
        dist = FIRIntersectionEngine._haversine_m(51.0, 0.0, 51.000045, 0.0)
        assert 4.0 < dist < 6.0

    def test_symmetry(self):
        d1 = FIRIntersectionEngine._haversine_m(40.0, -74.0, 51.0, -0.5)
        d2 = FIRIntersectionEngine._haversine_m(51.0, -0.5, 40.0, -74.0)
        assert abs(d1 - d2) < 0.01


# ---------------------------------------------------------------------------
# _deduplicate_intersections
# ---------------------------------------------------------------------------
class TestDeduplicateIntersections:
    """Tests for _deduplicate_intersections method.

    Validates Requirements: 19.1, 19.2
    """

    def test_empty_list(self, engine):
        assert engine._deduplicate_intersections([]) == []

    def test_single_intersection_unchanged(self, engine):
        seg = _make_segment("EGTT")
        result = engine._deduplicate_intersections([seg])
        assert len(result) == 1
        assert result[0]["icao_code"] == "EGTT"

    def test_distinct_intersections_preserved(self, engine):
        """Two intersections with different entry/exit points are kept."""
        seg_a = _make_segment("EGTT", entry_lat=50.0, entry_lon=0.0,
                              exit_lat=51.0, exit_lon=1.0, route_fraction=0.1)
        seg_b = _make_segment("LFFF", entry_lat=48.0, entry_lon=2.0,
                              exit_lat=47.0, exit_lon=3.0, route_fraction=0.5)
        result = engine._deduplicate_intersections([seg_a, seg_b])
        assert len(result) == 2

    def test_duplicate_within_tolerance_merged(self, engine):
        """Two intersections with entry/exit within 10m are merged."""
        seg_a = _make_segment("EGTT", entry_lat=50.0, entry_lon=0.0,
                              exit_lat=51.0, exit_lon=1.0,
                              distance_km=100.0, distance_nm=54.0,
                              route_fraction=0.1)
        # Offset by ~3m (well within 10m tolerance)
        seg_b = _make_segment("EGTT", entry_lat=50.000003, entry_lon=0.0,
                              exit_lat=51.000003, exit_lon=1.0,
                              distance_km=50.0, distance_nm=27.0,
                              route_fraction=0.11)
        result = engine._deduplicate_intersections([seg_a, seg_b])
        assert len(result) == 1
        # Distances should be summed
        assert result[0]["segment_distance_km"] == pytest.approx(150.0)
        assert result[0]["segment_distance_nm"] == pytest.approx(81.0)

    def test_duplicate_outside_tolerance_kept(self, engine):
        """Two intersections with entry/exit > 10m apart are kept separate."""
        seg_a = _make_segment("EGTT", entry_lat=50.0, entry_lon=0.0,
                              exit_lat=51.0, exit_lon=1.0, route_fraction=0.1)
        # Offset by ~1km — well outside 10m tolerance
        seg_b = _make_segment("EGTT", entry_lat=50.01, entry_lon=0.0,
                              exit_lat=51.01, exit_lon=1.0, route_fraction=0.2)
        result = engine._deduplicate_intersections([seg_a, seg_b])
        assert len(result) == 2

    def test_entry_within_but_exit_outside_not_merged(self, engine):
        """If entry points are close but exit points are far, no merge."""
        seg_a = _make_segment("EGTT", entry_lat=50.0, entry_lon=0.0,
                              exit_lat=51.0, exit_lon=1.0, route_fraction=0.1)
        seg_b = _make_segment("EGTT", entry_lat=50.000003, entry_lon=0.0,
                              exit_lat=52.0, exit_lon=2.0, route_fraction=0.2)
        result = engine._deduplicate_intersections([seg_a, seg_b])
        assert len(result) == 2

    def test_three_duplicates_merged_to_one(self, engine):
        """Three near-identical intersections collapse to one."""
        base = _make_segment("EGTT", entry_lat=50.0, entry_lon=0.0,
                             exit_lat=51.0, exit_lon=1.0,
                             distance_km=30.0, distance_nm=16.2)
        dup1 = _make_segment("EGTT", entry_lat=50.0000001, entry_lon=0.0,
                             exit_lat=51.0000001, exit_lon=1.0,
                             distance_km=20.0, distance_nm=10.8)
        dup2 = _make_segment("EGTT", entry_lat=50.0000002, entry_lon=0.0,
                             exit_lat=51.0000002, exit_lon=1.0,
                             distance_km=10.0, distance_nm=5.4)
        result = engine._deduplicate_intersections([base, dup1, dup2])
        assert len(result) == 1
        assert result[0]["segment_distance_km"] == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# _merge_adjacent_same_fir
# ---------------------------------------------------------------------------
class TestMergeAdjacentSameFir:
    """Tests for _merge_adjacent_same_fir method.

    Validates Requirements: 7.5, 7.6
    """

    def test_empty_list(self, engine):
        assert engine._merge_adjacent_same_fir([]) == []

    def test_single_segment_unchanged(self, engine):
        seg = _make_segment("EGTT", distance_km=100.0)
        result = engine._merge_adjacent_same_fir([seg])
        assert len(result) == 1
        assert result[0]["icao_code"] == "EGTT"

    def test_different_firs_not_merged(self, engine):
        """[FIR_A, FIR_B] stays as two segments."""
        seg_a = _make_segment("EGTT", entry_lat=50.0, exit_lat=51.0,
                              distance_km=100.0, route_fraction=0.1)
        seg_b = _make_segment("LFFF", entry_lat=51.0, exit_lat=52.0,
                              distance_km=80.0, route_fraction=0.5)
        result = engine._merge_adjacent_same_fir([seg_a, seg_b])
        assert len(result) == 2
        assert result[0]["icao_code"] == "EGTT"
        assert result[1]["icao_code"] == "LFFF"

    def test_adjacent_same_fir_merged(self, engine):
        """[FIR_A, FIR_A] → [FIR_A(merged)]."""
        seg1 = _make_segment("EGTT", entry_lat=50.0, entry_lon=0.0,
                             exit_lat=50.5, exit_lon=0.5,
                             distance_km=60.0, distance_nm=32.4,
                             route_fraction=0.1)
        seg2 = _make_segment("EGTT", entry_lat=50.5, entry_lon=0.5,
                             exit_lat=51.0, exit_lon=1.0,
                             distance_km=60.0, distance_nm=32.4,
                             route_fraction=0.2)
        result = engine._merge_adjacent_same_fir([seg1, seg2])
        assert len(result) == 1
        merged = result[0]
        assert merged["icao_code"] == "EGTT"
        # Entry from first, exit from last
        assert merged["entry_lat"] == 50.0
        assert merged["entry_lon"] == 0.0
        assert merged["exit_lat"] == 51.0
        assert merged["exit_lon"] == 1.0
        # Distances summed
        assert merged["segment_distance_km"] == pytest.approx(120.0)
        assert merged["segment_distance_nm"] == pytest.approx(64.8)

    def test_reentry_preserved(self, engine):
        """[FIR_A, FIR_A, FIR_B, FIR_A] → [FIR_A(merged), FIR_B, FIR_A].

        The last FIR_A is a legitimate re-entry and must NOT be merged
        with the first FIR_A.
        """
        seg_a1 = _make_segment("EGTT", distance_km=60.0, distance_nm=32.4,
                               route_fraction=0.1)
        seg_a2 = _make_segment("EGTT", distance_km=40.0, distance_nm=21.6,
                               route_fraction=0.2)
        seg_b = _make_segment("LFFF", distance_km=80.0, distance_nm=43.2,
                              route_fraction=0.5)
        seg_a3 = _make_segment("EGTT", distance_km=50.0, distance_nm=27.0,
                               route_fraction=0.8)

        result = engine._merge_adjacent_same_fir([seg_a1, seg_a2, seg_b, seg_a3])
        assert len(result) == 3
        assert result[0]["icao_code"] == "EGTT"
        assert result[0]["segment_distance_km"] == pytest.approx(100.0)  # merged
        assert result[1]["icao_code"] == "LFFF"
        assert result[2]["icao_code"] == "EGTT"
        assert result[2]["segment_distance_km"] == pytest.approx(50.0)  # re-entry, not merged

    def test_three_adjacent_same_fir_merged(self, engine):
        """[A, A, A] → [A(merged)] with all distances summed."""
        segs = [
            _make_segment("EGTT", distance_km=30.0, distance_nm=16.2,
                          entry_lat=50.0, exit_lat=50.3, route_fraction=0.1),
            _make_segment("EGTT", distance_km=30.0, distance_nm=16.2,
                          entry_lat=50.3, exit_lat=50.6, route_fraction=0.2),
            _make_segment("EGTT", distance_km=30.0, distance_nm=16.2,
                          entry_lat=50.6, exit_lat=51.0, route_fraction=0.3),
        ]
        result = engine._merge_adjacent_same_fir(segs)
        assert len(result) == 1
        assert result[0]["segment_distance_km"] == pytest.approx(90.0)
        assert result[0]["entry_lat"] == 50.0
        assert result[0]["exit_lat"] == 51.0

    def test_noise_segment_discarded(self, engine):
        """A segment shorter than 50m (0.05 km) is discarded after merge."""
        seg = _make_segment("EGTT", distance_km=0.04, distance_nm=0.02)
        result = engine._merge_adjacent_same_fir([seg])
        assert len(result) == 0

    def test_noise_after_merge_discarded(self, engine):
        """If merging two tiny segments still results in < 50m, discard."""
        seg1 = _make_segment("EGTT", distance_km=0.02, distance_nm=0.01,
                             route_fraction=0.1)
        seg2 = _make_segment("EGTT", distance_km=0.02, distance_nm=0.01,
                             route_fraction=0.2)
        result = engine._merge_adjacent_same_fir([seg1, seg2])
        assert len(result) == 0

    def test_original_segments_not_mutated(self, engine):
        """Merging should not mutate the input segment dicts."""
        seg1 = _make_segment("EGTT", distance_km=60.0, distance_nm=32.4,
                             route_fraction=0.1)
        seg2 = _make_segment("EGTT", distance_km=40.0, distance_nm=21.6,
                             route_fraction=0.2)
        original_km = seg1["segment_distance_km"]
        engine._merge_adjacent_same_fir([seg1, seg2])
        assert seg1["segment_distance_km"] == original_km

    def test_mixed_sequence_complex(self, engine):
        """[A, B, B, C, A, A] → [A, B(merged), C, A(merged)]."""
        segs = [
            _make_segment("EGTT", distance_km=100.0, distance_nm=54.0, route_fraction=0.1),
            _make_segment("LFFF", distance_km=50.0, distance_nm=27.0, route_fraction=0.2),
            _make_segment("LFFF", distance_km=50.0, distance_nm=27.0, route_fraction=0.3),
            _make_segment("EDGG", distance_km=70.0, distance_nm=37.8, route_fraction=0.5),
            _make_segment("EGTT", distance_km=40.0, distance_nm=21.6, route_fraction=0.7),
            _make_segment("EGTT", distance_km=30.0, distance_nm=16.2, route_fraction=0.8),
        ]
        result = engine._merge_adjacent_same_fir(segs)
        assert len(result) == 4
        assert [r["icao_code"] for r in result] == ["EGTT", "LFFF", "EDGG", "EGTT"]
        assert result[1]["segment_distance_km"] == pytest.approx(100.0)  # LFFF merged
        assert result[3]["segment_distance_km"] == pytest.approx(70.0)   # EGTT re-entry merged


# ---------------------------------------------------------------------------
# _calculate_gc_distance
# ---------------------------------------------------------------------------
class TestCalculateGcDistance:
    """Tests for _calculate_gc_distance method.

    Validates Requirements: 9.1, 9.2
    """

    def test_same_point_returns_zero(self, engine):
        """GC distance between identical points is zero."""
        km, nm = engine._calculate_gc_distance((51.0, 0.0), (51.0, 0.0))
        assert km == 0.0
        assert nm == 0.0

    def test_known_distance_london_to_paris(self, engine):
        """London (51.5074, -0.1278) to Paris (48.8566, 2.3522) ≈ 343 km."""
        km, nm = engine._calculate_gc_distance(
            (51.5074, -0.1278), (48.8566, 2.3522)
        )
        assert 335.0 < km < 355.0
        assert 180.0 < nm < 192.0

    def test_returns_km_and_nm(self, engine):
        """Result tuple contains (km, nm) with correct ratio."""
        km, nm = engine._calculate_gc_distance((40.0, -74.0), (51.0, -0.5))
        # 1 nm = 1.852 km
        assert km == pytest.approx(nm * 1.852, rel=1e-6)

    def test_symmetry(self, engine):
        """Distance A→B equals distance B→A."""
        km1, nm1 = engine._calculate_gc_distance((40.0, -74.0), (51.0, -0.5))
        km2, nm2 = engine._calculate_gc_distance((51.0, -0.5), (40.0, -74.0))
        assert km1 == pytest.approx(km2, rel=1e-9)
        assert nm1 == pytest.approx(nm2, rel=1e-9)

    def test_short_distance(self, engine):
        """Two points ~5m apart produce small but non-zero distances."""
        km, nm = engine._calculate_gc_distance((51.0, 0.0), (51.000045, 0.0))
        assert 0.004 < km < 0.006
        assert 0.002 < nm < 0.004

    def test_antipodal_points(self, engine):
        """Points on opposite sides of Earth ≈ 20,000 km."""
        km, nm = engine._calculate_gc_distance((0.0, 0.0), (0.0, 180.0))
        assert 20_000.0 < km < 20_100.0


# ---------------------------------------------------------------------------
# _validate_chain_continuity
# ---------------------------------------------------------------------------
class TestValidateChainContinuity:
    """Tests for _validate_chain_continuity method.

    Validates Requirements: 7.7
    """

    def _make_crossing(
        self,
        seq: int,
        icao: str,
        entry: tuple[float, float],
        exit_pt: tuple[float, float],
    ) -> "FIRCrossingRecord":
        from src.services.fir_intersection_engine import FIRCrossingRecord
        return FIRCrossingRecord(
            sequence=seq,
            icao_code=icao,
            fir_name=f"{icao} FIR",
            country="Test",
            country_code="TS",
            entry_point=entry,
            exit_point=exit_pt,
            segment_distance_km=100.0,
            segment_distance_nm=54.0,
            gc_entry_exit_distance_km=99.0,
            gc_entry_exit_distance_nm=53.5,
            segment_geometry={"type": "LineString", "coordinates": []},
            calculation_method="postgis_geography",
        )

    def test_empty_list(self, engine):
        """No crossings → no failures."""
        assert engine._validate_chain_continuity([]) == []

    def test_single_crossing(self, engine):
        """Single crossing → no consecutive pairs → no failures."""
        c = self._make_crossing(0, "EGTT", (50.0, 0.0), (51.0, 1.0))
        assert engine._validate_chain_continuity([c]) == []

    def test_continuous_chain_no_failures(self, engine):
        """Exit of N matches entry of N+1 exactly → no failures."""
        c1 = self._make_crossing(0, "EGTT", (50.0, 0.0), (51.0, 1.0))
        c2 = self._make_crossing(1, "LFFF", (51.0, 1.0), (49.0, 2.0))
        c3 = self._make_crossing(2, "EDGG", (49.0, 2.0), (48.0, 3.0))
        assert engine._validate_chain_continuity([c1, c2, c3]) == []

    def test_small_gap_within_tolerance(self, engine):
        """Gap of ~3m (within 10m tolerance) → no failure."""
        c1 = self._make_crossing(0, "EGTT", (50.0, 0.0), (51.0, 1.0))
        # ~3m offset in latitude
        c2 = self._make_crossing(1, "LFFF", (51.000027, 1.0), (49.0, 2.0))
        assert engine._validate_chain_continuity([c1, c2]) == []

    def test_gap_exceeds_tolerance(self, engine):
        """Gap of ~1km → failure flagged."""
        c1 = self._make_crossing(0, "EGTT", (50.0, 0.0), (51.0, 1.0))
        # ~1km offset
        c2 = self._make_crossing(1, "LFFF", (51.01, 1.0), (49.0, 2.0))
        failures = engine._validate_chain_continuity([c1, c2])
        assert len(failures) == 1
        assert failures[0]["pair"] == (0, 1)
        assert failures[0]["exit_point"] == (51.0, 1.0)
        assert failures[0]["entry_point"] == (51.01, 1.0)
        assert failures[0]["gap_distance_m"] > 10.0

    def test_multiple_failures(self, engine):
        """Two gaps in a three-crossing chain → two failures."""
        c1 = self._make_crossing(0, "EGTT", (50.0, 0.0), (51.0, 1.0))
        c2 = self._make_crossing(1, "LFFF", (52.0, 1.0), (49.0, 2.0))  # gap from c1
        c3 = self._make_crossing(2, "EDGG", (50.0, 3.0), (48.0, 4.0))  # gap from c2
        failures = engine._validate_chain_continuity([c1, c2, c3])
        assert len(failures) == 2
        assert failures[0]["pair"] == (0, 1)
        assert failures[1]["pair"] == (1, 2)

    def test_failure_contains_required_fields(self, engine):
        """Each failure dict has pair, exit_point, entry_point, gap_distance_m."""
        c1 = self._make_crossing(0, "EGTT", (50.0, 0.0), (51.0, 1.0))
        c2 = self._make_crossing(1, "LFFF", (52.0, 2.0), (49.0, 3.0))
        failures = engine._validate_chain_continuity([c1, c2])
        assert len(failures) == 1
        f = failures[0]
        assert "pair" in f
        assert "exit_point" in f
        assert "entry_point" in f
        assert "gap_distance_m" in f
        assert isinstance(f["gap_distance_m"], float)
