import numpy as np
import pytest
import xarray as xr

from wiemip_registry.CARDAMOM_JPL.convert import CARDAMOM_JPL


def _upload(tmp_path, monkeypatch, attrs):
    path = tmp_path / "tveg.nc"
    time = xr.DataArray(
        [15.0],
        dims="time",
        attrs={"units": "days since 1850-01-01", "calendar": "noleap"},
    )
    xr.Dataset(
        {
            "tveg": (
                ("time", "latitude", "longitude"),
                np.full((1, 1, 1), 2e-5, dtype="float32"),
                attrs,
            )
        },
        coords={"time": time, "latitude": [10.5], "longitude": [20.5]},
    ).to_netcdf(path)
    monkeypatch.setattr(CARDAMOM_JPL, "path", lambda self, *args: str(path))


def test_capital_unit_attribute_is_read_as_units(tmp_path, monkeypatch):
    _upload(tmp_path, monkeypatch, {"Unit": "kg m-2 s-1"})
    da = CARDAMOM_JPL().read("1pctCO2", "bgc", "stable", "baseline", "tveg")
    assert da.attrs["units"] == "kg m-2 s-1"
    assert float(da.isel(time=0, lat=0, lon=0)) == pytest.approx(2e-5)


def test_file_without_unit_attribute_gets_no_units(tmp_path, monkeypatch):
    _upload(tmp_path, monkeypatch, {})
    da = CARDAMOM_JPL().read("1pctCO2", "bgc", "stable", "baseline", "tveg")
    assert "units" not in da.attrs
