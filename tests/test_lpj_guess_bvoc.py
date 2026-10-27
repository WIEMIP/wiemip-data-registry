import numpy as np
import pytest
import xarray as xr

from wiemip_registry.LPJ_GUESS.convert import LPJ_GUESS


def _adapter_reading(tmp_path, monkeypatch, variable, value):
    nc = tmp_path / f"{variable}.nc"
    time = xr.DataArray([0, 1], dims="time", attrs={"units": "months since 1850-01-01"})
    xr.Dataset(
        {
            variable: (
                ("time", "lat", "lon"),
                np.full((2, 1, 1), value),
                {"units": "kg m-2 s-1"},
            )
        },
        coords={"time": time, "lat": [10.25], "lon": [20.25]},
    ).to_netcdf(nc)
    adapter = LPJ_GUESS()
    monkeypatch.setattr(adapter, "path", lambda *args: str(nc))
    return adapter


@pytest.mark.parametrize("variable", ["isopr", "terp"])
def test_bvoc_mg_is_scaled_to_kg(tmp_path, monkeypatch, variable):
    adapter = _adapter_reading(tmp_path, monkeypatch, variable, 2e-5)

    da = adapter.read("overshoot", "hist", "ukesm", None, variable)

    assert float(da.isel(time=0, lat=0, lon=0)) == pytest.approx(2e-11)
    assert da.attrs["units"] == "kg m-2 s-1"


def test_other_fluxes_are_not_scaled(tmp_path, monkeypatch):
    adapter = _adapter_reading(tmp_path, monkeypatch, "gpp", 2e-8)

    da = adapter.read("overshoot", "hist", "ukesm", None, "gpp")

    assert float(da.isel(time=0, lat=0, lon=0)) == pytest.approx(2e-8)


def test_one_pct_isopr_is_not_provisional():
    assert ("1pctCO2", "isopr") not in LPJ_GUESS().PROVISIONAL_DATA
