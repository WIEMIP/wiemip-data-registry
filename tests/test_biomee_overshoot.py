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


def _gpp_upload(tmp_path, monkeypatch, time_units):
    path = tmp_path / "gpp.nc"
    time = xr.DataArray(
        np.array([15.5, 45.0, 63494.5]),
        dims="time",
        attrs={"units": time_units, "calendar": "noleap"},
    )
    xr.Dataset(
        {
            "gpp": (
                ("lon", "lat", "time"),
                np.ones((1, 1, 3), dtype="float32"),
                {"units": "kg C m-2 s-1"},
            )
        },
        coords={"time": time, "lat": [10.25], "lon": [20.25]},
    ).to_netcdf(path)
    monkeypatch.setattr(BiomeE, "path", lambda self, *args: str(path))


def test_hist_misstamped_2024_epoch_is_read_from_1850(tmp_path, monkeypatch):
    _gpp_upload(tmp_path, monkeypatch, "days since 2024-01-01")
    time = BiomeE().read("overshoot", "hist", "ukesm", None, "gpp")["time"].values
    assert str(time[0])[:10] == "1850-01-16"
    assert str(time[-1])[:7] == "2023-12"


def test_hist_1850_epoch_is_left_alone(tmp_path, monkeypatch):
    _gpp_upload(tmp_path, monkeypatch, "days since 1850-01-01")
    time = BiomeE().read("overshoot", "hist", "ukesm", None, "gpp")["time"].values
    assert str(time[0])[:10] == "1850-01-16"


def test_scenario_2024_epoch_is_left_alone(tmp_path, monkeypatch):
    _gpp_upload(tmp_path, monkeypatch, "days since 2024-01-01")
    time = BiomeE().read("overshoot", "hl", "ukesm", None, "gpp")["time"].values
    assert str(time[0])[:10] == "2024-01-16"


@pytest.mark.parametrize(
    "experiment, simulation, forcing, factorial",
    [("overshoot", "hist", "ukesm", None), ("1pctCO2", "bgc", "stable", "baseline")],
)
def test_transpft_water_flux_comes_back_as_latent_heat(
    tmp_path, monkeypatch, experiment, simulation, forcing, factorial
):
    path = tmp_path / "transpft.nc"
    time = xr.DataArray(
        [15.5],
        dims="time",
        attrs={"units": "days since 1850-01-01", "calendar": "noleap"},
    )
    xr.Dataset(
        {
            "transpft": (
                ("lon", "lat", "pft", "time"),
                np.full((1, 1, 2, 1), 1e-5, dtype="float32"),
                {"units": "W m-2"},
            )
        },
        coords={"time": time, "lat": [10.25], "lon": [20.25]},
    ).to_netcdf(path)
    monkeypatch.setattr(BiomeE, "path", lambda self, *args: str(path))
    da = BiomeE().read(experiment, simulation, forcing, factorial, "transpft")
    assert float(da.isel(time=0, lat=0, lon=0, pft=0)) == pytest.approx(25.01, rel=1e-4)
    assert da.attrs["units"] == "W m-2"


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
