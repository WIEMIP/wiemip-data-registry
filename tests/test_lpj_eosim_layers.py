import numpy as np
import pandas as pd
import xarray as xr

from wiemip_registry import core
from wiemip_registry.LPJ_EOSIM.convert import LPJ_EOSIM


def _upload(tmp_path, monkeypatch, variable, level, size):
    path = tmp_path / f"{variable}.nc"
    data = np.arange(size, dtype="float32")[:, None, None, None] * np.ones(
        (size, 2, 1, 1)
    )
    xr.Dataset(
        {variable: ((level, "time", "latitude", "longitude"), data.astype("float32"))},
        coords={
            level: np.arange(size),
            "time": pd.date_range("1850-01-01", periods=2, freq="MS"),
            "latitude": [70.0],
            "longitude": [0.0],
        },
    ).to_netcdf(path)
    monkeypatch.setattr(LPJ_EOSIM, "path", lambda self, *args: str(path))


def _standardized(variable):
    da = LPJ_EOSIM().read("1pctCO2", "bgc", "stable", "baseline", variable)
    return core.WIEFile(
        "LPJ_EOSIM", "1pctCO2", "bgc", "stable", variable, _adapter=None
    )._standardize_layers(da)


def test_soilT_drops_the_top_mean_and_gets_point_depths(tmp_path, monkeypatch):
    _upload(tmp_path, monkeypatch, "soilT", "pool", 9)
    da = _standardized("soilT")
    assert da["soil"].values.tolist() == [0.0, 0.1, 0.25, 0.5, 0.7, 1.0, 1.5, 2.0]
    assert da["soil"].attrs["units"] == "m"
    assert float(da.isel(soil=0, time=0).squeeze()) == 1.0


def test_soilIce_gets_the_layer_middles(tmp_path, monkeypatch):
    _upload(tmp_path, monkeypatch, "soilIce", "layer", 8)
    da = _standardized("soilIce")
    assert da["soil"].values.tolist() == [0.05, 0.15, 0.25, 0.4, 0.6, 0.85, 1.25, 1.75]
