import numpy as np
import pytest
import xarray as xr

from wiemip_registry import core
from wiemip_registry.ELM.convert import ELM


def _upload(tmp_path, monkeypatch, variable, value, units):
    path = tmp_path / f"{variable}.nc"
    xr.Dataset(
        {
            variable: (
                ("time", "lat", "lon"),
                np.full((2, 1, 1), value),
                {"units": units},
            )
        },
        coords={
            "time": ("time", [31.0, 59.0], {"units": "days since 1850-01-01 00:00:00"}),
            "lat": [70.0],
            "lon": [0.0],
        },
    ).to_netcdf(path)
    monkeypatch.setattr(ELM, "path", lambda self, *args: str(path))


def _read(variable):
    return core.WIEFile(
        "ELM", "1pctCO2", "cou", "ukesm", variable, _adapter=ELM(), factorial="baseline"
    ).read()


def test_burnt_area_gains_the_timestep_and_becomes_percent(tmp_path, monkeypatch):
    _upload(tmp_path, monkeypatch, "burntArea", 1e-4, "1")
    da = _read("burntArea")
    assert float(da.isel(time=0, lat=0, lon=0)) == pytest.approx(18.0)
    assert da.attrs["units"] == "%"


def test_burnt_area_total_gains_the_timestep_and_stays_percent(tmp_path, monkeypatch):
    _upload(tmp_path, monkeypatch, "burntareaTotal", 1e-2, "%")
    da = _read("burntareaTotal")
    assert float(da.isel(time=0, lat=0, lon=0)) == pytest.approx(18.0)
    assert da.attrs["units"] == "%"


def test_peat_is_read_as_uploaded(tmp_path, monkeypatch):
    _upload(tmp_path, monkeypatch, "burntareapeatTotal", 18.0, "%")
    da = _read("burntareapeatTotal")
    assert float(da.isel(time=0, lat=0, lon=0)) == pytest.approx(18.0)
    assert da.attrs["units"] == "%"
