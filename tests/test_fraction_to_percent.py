import numpy as np
import pandas as pd
import xarray as xr

from wiemip_registry import core


def _fraction():
    time = pd.date_range("1850-01-01", periods=2, freq="MS")
    return xr.DataArray(
        np.full((2, 1, 1), 0.25, dtype="float32"),
        dims=("time", "lat", "lon"),
        coords={"time": time, "lat": [60.0], "lon": [0.0]},
        attrs={"units": "fraction", "long_name": "Burnt Area Fraction"},
        name="burntArea",
    )


class _StubAdapter(core.WIEAdapter):
    model = "STUB"
    FRACTION_TO_PERCENT = {"burntArea"}

    def __init__(self, da):
        self.da = da

    def one_pct_path(self, simulation, forcing, factorial, variable):
        return "/nonexistent.nc"

    def read(self, experiment, simulation, forcing, factorial, variable):
        return self.da

    def _compute_weights(self):
        raise NotImplementedError


def test_listed_variable_comes_back_in_percent(monkeypatch):
    monkeypatch.setattr(core.WIEFile, "exists", lambda self: True)
    adapter = _StubAdapter(_fraction())
    da = core.WIEFile(
        "STUB", "1pctCO2", "bgc", "stable", "burntArea", _adapter=adapter
    ).read()
    assert da.values.tolist() == [[[25.0]], [[25.0]]]
    assert da.dtype == "float32"
    assert da.attrs == {"units": "%", "long_name": "Burnt Area Fraction"}
    assert da.name == "burntArea"


def test_unlisted_variable_is_untouched(monkeypatch):
    monkeypatch.setattr(core.WIEFile, "exists", lambda self: True)
    adapter = _StubAdapter(_fraction())
    da = core.WIEFile(
        "STUB", "1pctCO2", "bgc", "stable", "burntareaTotal", _adapter=adapter
    ).read()
    assert da.values.tolist() == [[[0.25]], [[0.25]]]
    assert da.attrs["units"] == "fraction"
