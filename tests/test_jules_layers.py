import numpy as np
import pandas as pd
import xarray as xr

from wiemip_registry import core
from wiemip_registry.JULES.convert import _SOIL_LAYER_DEPTHS, JULES


def test_jules_overshoot_sclayer_gets_the_soil_depths(tmp_path, monkeypatch):
    path = tmp_path / "cSoilLayers.nc"
    xr.Dataset(
        {
            "cSoilLayers": (
                ("time", "sclayer", "latitude", "longitude"),
                np.ones((2, 10, 1, 1), dtype="float32"),
            )
        },
        coords={
            "time": pd.date_range("2024-01-01", periods=2, freq="YS"),
            "sclayer": np.arange(1, 11),
            "latitude": [70.0],
            "longitude": [0.0],
        },
    ).to_netcdf(path)
    monkeypatch.setattr(JULES, "path", lambda self, *args: str(path))

    da = JULES().read("overshoot", "hl", "ukesm", "baseline", "cSoilLayers")
    soil = core.WIEFile(
        "JULES", "overshoot", "hl", "ukesm", "cSoilLayers", _adapter=None
    )._standardize_layers(da)
    assert soil["soil"].values.tolist() == list(_SOIL_LAYER_DEPTHS)
    assert soil["soil"].attrs["units"] == "m"
