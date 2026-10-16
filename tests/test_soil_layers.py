import numpy as np
import pandas as pd
import pytest
import xarray as xr

from wiemip_registry import core


def _layered(level="levgrnd", depths=(0.05, 0.3, 1.0), units="m"):
    time = pd.date_range("1850-01-01", periods=2, freq="MS")
    data = np.zeros((2, 2, 1, len(depths) if depths is not None else 3))
    da = xr.DataArray(
        data,
        dims=("time", "lat", "lon", level),
        coords={"time": time, "lat": [60.0, 61.0], "lon": [0.0]},
    )
    if depths is not None:
        da = da.assign_coords({level: (level, list(depths), {"units": units})})
    return da


def _file():
    return core.WIEFile("CLM", "1pctCO2", "bgc", "stable", "soilT", _adapter=None)


def test_level_dim_renamed_to_soil_keeping_depths():
    da = _file()._standardize_layers(_layered())
    assert "soil" in da.dims and "levgrnd" not in da.dims
    assert da["soil"].values.tolist() == [0.05, 0.3, 1.0]
    assert da["soil"].attrs["units"] == "m"


def test_raises_with_no_level_dim():
    da = _layered().isel(levgrnd=0, drop=True)
    with pytest.raises(ValueError, match="exactly one level dim"):
        _file()._standardize_layers(da)


def test_raises_with_two_level_dims():
    da = _layered().expand_dims(pool=["a", "b"])
    with pytest.raises(ValueError, match="exactly one level dim"):
        _file()._standardize_layers(da)


def test_raises_without_depth_coord():
    with pytest.raises(ValueError, match="no depth coordinate"):
        _file()._standardize_layers(_layered(depths=None))


def test_raises_unless_units_m():
    with pytest.raises(ValueError, match="units"):
        _file()._standardize_layers(_layered(units="layer"))


def test_raises_unless_depth_increases():
    with pytest.raises(ValueError, match="increase"):
        _file()._standardize_layers(_layered(depths=(1.0, 0.3, 0.05)))


def test_float32_depths_come_back_exact_float64():
    float32_depths = np.array([0.05, 0.15, 0.4], dtype="float32")
    da = _file()._standardize_layers(_layered(depths=float32_depths))
    assert da["soil"].dtype == "float64"
    assert da["soil"].values.tolist() == [0.05, 0.15, 0.4]
    assert da["soil"].attrs["units"] == "m"


class _StubAdapter(core.WIEAdapter):
    model = "STUB"
    LAYERED_VARIABLES = {"soilT"}

    def __init__(self, da):
        self.da = da

    def one_pct_path(self, simulation, forcing, factorial, variable):
        return "/nonexistent.nc"

    def read(self, experiment, simulation, forcing, factorial, variable):
        return self.da

    def _compute_weights(self):
        raise NotImplementedError


def test_read_standardizes_listed_variables_only(monkeypatch):
    monkeypatch.setattr(core.WIEFile, "exists", lambda self: True)
    adapter = _StubAdapter(_layered())
    listed = core.WIEFile("STUB", "1pctCO2", "bgc", "stable", "soilT", _adapter=adapter)
    unlisted = core.WIEFile(
        "STUB", "1pctCO2", "bgc", "stable", "cSoilLayers", _adapter=adapter
    )
    assert "soil" in listed.read().dims
    assert "levgrnd" in unlisted.read().dims


def test_calculate_alt_matches_function_alt():
    time = pd.date_range("1850-01-01", periods=24, freq="MS")
    temps = np.empty((24, 3, 1, 3))
    for t in range(24):
        july = t % 12 == 6
        temps[t, :, 0, 0] = [275.0, 271.0, 270.0] if july else [270.0, 270.0, 270.0]
        temps[t, :, 0, 1] = [270.0, 270.0, 270.0]
        temps[t, :, 0, 2] = [280.0, 280.0, 280.0]
    da = xr.DataArray(
        temps,
        dims=("time", "soil", "lat", "lon"),
        coords={
            "time": time,
            "soil": [0.5, 1.5, 2.5],
            "lat": [65.0],
            "lon": [0.0, 1.0, 2.0],
        },
    )
    alt = core.calculate_alt(da)
    assert alt.name == "alt"
    assert alt.dims == ("year", "lat", "lon")
    np.testing.assert_allclose(alt.values[:, 0, :], [[0.9625, 0.0, 2.5]] * 2)
