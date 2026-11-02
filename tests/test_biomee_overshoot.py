import numpy as np
import pytest
import xarray as xr

import wiemip_registry as wr
from wiemip_registry import core
from wiemip_registry.BiomeE.convert import BiomeE

ROOT = "overshoot/output/BiomeE/"


@pytest.mark.parametrize("forcing", ["ukesm", "gfdl", "ipsl"])
def test_hist_pins_the_uploaded_ukesm_token(forcing):
    f = wr.retrieve_overshoot_variable("BiomeE", forcing, "hist", "cVeg")
    assert f.path.endswith(ROOT + "BiomeE_ukesm_hist_cVeg_yr_05_noCH4.nc")


def test_hist_monthly_cadence():
    f = wr.retrieve_overshoot_variable("BiomeE", "ukesm", "hist", "gpp")
    assert f.path.endswith(ROOT + "BiomeE_ukesm_hist_gpp_mon_05_noCH4.nc")


def test_overshoot_ch4_is_provisional():
    f = wr.retrieve_overshoot_variable("BiomeE", "ukesm", "hist", "ch4")
    assert not f.exists()
    with pytest.raises(core.ProvisionalDataError):
        f.read()


def _burnt_area_upload(tmp_path, monkeypatch, annual_fraction):
    path = tmp_path / "burntArea.nc"
    time = xr.DataArray(
        np.arange(12) * 30.0 + 15.0,
        dims="time",
        attrs={"units": "days since 1850-01-01", "calendar": "noleap"},
    )
    xr.Dataset(
        {
            "burntArea": (
                ("lon", "lat", "time"),
                np.full((1, 1, 12), annual_fraction, dtype="float32"),
                {"units": "fraction"},
            )
        },
        coords={"time": time, "lat": [10.25], "lon": [20.25]},
    ).to_netcdf(path)
    monkeypatch.setattr(BiomeE, "path", lambda self, *args: str(path))


def test_overshoot_burnt_area_spreads_the_year_over_its_months(tmp_path, monkeypatch):
    _burnt_area_upload(tmp_path, monkeypatch, 0.6)
    da = core.WIEFile(
        "BiomeE", "overshoot", "hist", "ukesm", "burntArea", _adapter=BiomeE()
    ).read()
    assert float(da.isel(time=0, lat=0, lon=0)) == pytest.approx(5.0)
    assert float(da.sum("time").isel(lat=0, lon=0)) == pytest.approx(60.0)
    assert da.attrs["units"] == "%"


def test_one_pct_burnt_area_is_not_spread(tmp_path, monkeypatch):
    _burnt_area_upload(tmp_path, monkeypatch, 0.6)
    da = core.WIEFile(
        "BiomeE",
        "1pctCO2",
        "bgc",
        "stable",
        "burntArea",
        _adapter=BiomeE(),
        factorial="baseline",
    ).read()
    assert float(da.isel(time=0, lat=0, lon=0)) == pytest.approx(60.0)
