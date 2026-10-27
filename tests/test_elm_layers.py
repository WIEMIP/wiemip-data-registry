import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.ELM.convert import _SOIL_LAYER_DEPTHS, ELM


def _upload(tmp_path, monkeypatch, variable, level):
    path = tmp_path / f"{variable}.nc"
    xr.Dataset(
        {
            variable: (
                ("time", level, "lat", "lon"),
                np.ones((2, 15, 1, 1), dtype="float32"),
            )
        },
        coords={
            "time": ("time", [31.0, 59.0], {"units": "days since 1850-01-01 00:00:00"}),
            level: (level, np.float32(_SOIL_LAYER_DEPTHS), {"units": "m"}),
            "lat": [70.0],
            "lon": [0.0],
        },
    ).to_netcdf(path)
    monkeypatch.setattr(ELM, "path", lambda self, *args: str(path))


def _standardized(variable):
    da = ELM().read("1pctCO2", "cou", "ukesm", "baseline", variable)
    return core.WIEFile(
        "ELM", "1pctCO2", "cou", "ukesm", variable, _adapter=None
    )._standardize_layers(da)


def test_levgrnd_gets_the_node_depths(tmp_path, monkeypatch):
    _upload(tmp_path, monkeypatch, "soilT", "levgrnd")
    da = _standardized("soilT")
    assert da["soil"].values.tolist() == list(_SOIL_LAYER_DEPTHS)


def test_levdcmp_gets_the_node_depths(tmp_path, monkeypatch):
    _upload(tmp_path, monkeypatch, "cSoilLayers", "levdcmp")
    da = _standardized("cSoilLayers")
    assert da["soil"].values.tolist() == list(_SOIL_LAYER_DEPTHS)
    assert da["soil"].attrs["units"] == "m"
