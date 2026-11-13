"""A per-PFT variable uploaded per m2 of PFT is weighted by its run's landCoverFrac."""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from wiemip_registry import core
from wiemip_registry.CLASSIC.convert import CLASSIC
from wiemip_registry.JSBACH.convert import JSBACH
from wiemip_registry.JULES.convert import JULES

LAT, LON = [-10.0, 50.0], [0.0]
CELL_AREA = np.array([[100.0], [10.0]])  # m2, (lat, lon)

# landCoverFrac: annual, classes 1-3 (3 = bare ground), dims (time, lat, lon, type)
FRACTION = np.array(
    [
        [[[0.5, 0.3, 0.2]], [[0.1, 0.9, 0.0]]],  # 1850
        [[[0.4, 0.4, 0.2]], [[0.2, 0.8, 0.0]]],  # 1851
    ]
)


def _land_cover_fraction():
    return xr.DataArray(
        FRACTION,
        dims=("time", "lat", "lon", "type"),
        coords={
            "time": pd.to_datetime(["1850-07-02", "1851-07-02"]),
            "lat": LAT,
            "lon": LON,
            "type": [1, 2, 3],
        },
        name="landCoverFrac",
    )


def _monthly_per_pft(years=(1850, 1851)):
    """Two PFTs, monthly, every value 2.0 for PFT 1 and 3.0 for PFT 2."""
    time = pd.to_datetime(
        [f"{year}-{month:02d}-16" for year in years for month in range(1, 13)]
    )
    values = np.empty((len(time), 2, 1, 2))
    values[..., 0] = 2.0
    values[..., 1] = 3.0
    return xr.DataArray(
        values,
        dims=("time", "lat", "lon", "pft"),
        coords={"time": time, "lat": LAT, "lon": LON, "pft": [1, 2]},
        name="gpppft",
    )


class _StubAdapter(core.WIEAdapter):
    model = "STUB"
    PER_PFT_AREA = {"gpppft"}

    def __init__(self, per_pft):
        self.per_pft = per_pft

    def one_pct_path(self, simulation, forcing, factorial, variable):
        return "/nonexistent.nc"

    def read(self, experiment, simulation, forcing, factorial, variable):
        return _land_cover_fraction() if variable == "landCoverFrac" else self.per_pft

    def _compute_weights(self):
        return xr.DataArray(
            CELL_AREA, dims=("lat", "lon"), coords={"lat": LAT, "lon": LON}
        )


def _wiefile(variable, per_pft):
    return core.WIEFile(
        "STUB", "1pctCO2", "cou", "ukesm", variable, _adapter=_StubAdapter(per_pft)
    )


@pytest.fixture(autouse=True)
def _every_file_exists(monkeypatch):
    monkeypatch.setattr(core.WIEFile, "exists", lambda self: True)


def test_sum_is_each_pfts_contribution_with_its_own_years_fractions():
    per_pft = _monthly_per_pft()
    total = _wiefile("gpppft", per_pft).weighted_dataarray(per_pft).sum(("lat", "lon"))
    assert total.dims == ("time", "pft")
    # value x cell area x fraction, summed over the two cells
    pft_1_1850 = 2.0 * (100.0 * 0.5 + 10.0 * 0.1)
    pft_2_1850 = 3.0 * (100.0 * 0.3 + 10.0 * 0.9)
    pft_1_1851 = 2.0 * (100.0 * 0.4 + 10.0 * 0.2)
    pft_2_1851 = 3.0 * (100.0 * 0.4 + 10.0 * 0.8)
    np.testing.assert_allclose(
        total.sel(time="1850").values, [[pft_1_1850, pft_2_1850]] * 12
    )
    np.testing.assert_allclose(
        total.sel(time="1851").values, [[pft_1_1851, pft_2_1851]] * 12
    )


def test_mean_is_over_the_pfts_own_area():
    per_pft = _monthly_per_pft()
    # PFT 1 is 2.0 in the first cell and 8.0 in the second
    per_pft.values[:, 1, 0, 0] = 8.0
    mean = _wiefile("gpppft", per_pft).weighted_dataarray(per_pft).mean(("lat", "lon"))
    expected_1850 = (2.0 * 100.0 * 0.5 + 8.0 * 10.0 * 0.1) / (100.0 * 0.5 + 10.0 * 0.1)
    np.testing.assert_allclose(
        mean.sel(time="1850", pft=1).values, [expected_1850] * 12
    )


def test_latitude_band_slice_keeps_only_its_cells():
    per_pft = _monthly_per_pft()
    band = per_pft.sel(lat=slice(30, 90))
    total = _wiefile("gpppft", per_pft).weighted_dataarray(band).sum(("lat", "lon"))
    np.testing.assert_allclose(
        total.sel(time="1850").values, [[2.0 * 10.0 * 0.1, 3.0 * 10.0 * 0.9]] * 12
    )


def test_unlisted_variable_keeps_the_cell_weights():
    per_pft = _monthly_per_pft()
    total = _wiefile("laipft", per_pft).weighted_dataarray(per_pft).sum(("lat", "lon"))
    np.testing.assert_allclose(total.isel(time=0).values, [2.0 * 110.0, 3.0 * 110.0])


def test_year_without_fractions_raises():
    per_pft = _monthly_per_pft(years=(1851, 1852))
    with pytest.raises(ValueError, match="no fractions for \\[1852\\]"):
        _wiefile("gpppft", per_pft).weighted_dataarray(per_pft)


def test_pft_missing_from_land_cover_fraction_raises():
    per_pft = _monthly_per_pft().assign_coords(pft=[1, 7])
    with pytest.raises(KeyError):
        _wiefile("gpppft", per_pft).weighted_dataarray(per_pft)


def _grid(values):
    return xr.DataArray(
        np.array(values), dims=("lat", "lon"), coords={"lat": LAT, "lon": LON}
    )


def test_default_takes_land_cover_fraction_as_a_fraction_of_land(monkeypatch):
    # cell area x land fraction, as weights() returns it
    monkeypatch.setattr(JULES, "weights", lambda self: _grid([[100.0], [5.0]]))
    area = JULES().pft_area(_grid([[0.5], [0.2]]))
    np.testing.assert_allclose(area.values, [[50.0], [1.0]])


def test_classic_takes_land_cover_fraction_as_a_fraction_of_the_grid_cell(monkeypatch):
    # second cell is half ocean: its weight is 5 m2 but its cell area is 10 m2
    monkeypatch.setattr(CLASSIC, "weights", lambda self: _grid([[100.0], [5.0]]))
    monkeypatch.setattr(CLASSIC, "_cell_area", lambda self: _grid([[100.0], [10.0]]))
    area = CLASSIC().pft_area(_grid([[0.5], [0.2]]))
    np.testing.assert_allclose(area.values, [[50.0], [2.0]])


def test_jsbach_lists_the_fluxes_and_not_the_stocks():
    assert {
        "gpppft",
        "npppft",
        "rhpft",
        "nbppft",
        "fN2Opft",
        "burntareaPft",
    } <= JSBACH.PER_PFT_AREA
    assert (
        not {"cVegpft", "cSoilpft", "cLitterpft", "nVegpft", "nLitterpft"}
        & JSBACH.PER_PFT_AREA
    )
