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
