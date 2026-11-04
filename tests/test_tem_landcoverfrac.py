import numpy as np
import xarray as xr

import wiemip_registry as wr
from wiemip_registry.TEM.convert import TEM

ROOT = "overshoot/output/TEM/"


def test_hist_landcoverfrac_spells_fx():
    f = wr.retrieve_overshoot_variable("TEM", "ukesm", "hist", "landCoverFrac")
    assert f.path.endswith(ROOT + "hist/TEM-MDM_crujra3_hist_landCoverFrac_fx_05.nc")


def test_scenario_landcoverfrac_spells_fx():
    f = wr.retrieve_overshoot_variable("TEM", "ipsl", "hl_cf", "landCoverFrac")
    assert f.path.endswith(ROOT + "hl_cf/TEM-MDM_ipsl_hl_cf_landCoverFrac_fx_05.nc")


def test_landcoverfrac_reads_without_time(tmp_path, monkeypatch):
    # Layout of the 2026-11-03 upload: (longitude, latitude, pft, time=1), % units.
    nc = tmp_path / "TEM-MDM_ukesm_hl_landCoverFrac_fx_05.nc"
    values = np.zeros((3, 2, 12, 1), dtype="float32")
    values[:, :, 3, 0] = 100.0
    values[0, 0, :, 0] = -99999.0
    xr.Dataset(
        {"landCoverFrac": (("longitude", "latitude", "pft", "time"), values)},
        coords={
            "longitude": [-150.25, -149.75, -149.25],
            "latitude": [60.25, 60.75],
            "pft": np.arange(1, 13),
            "time": ("time", [0.0], {"units": "days since 1850-01-01 00:00:00"}),
        },
    ).to_netcdf(nc)
    adapter = TEM()
    monkeypatch.setattr(adapter, "path", lambda *args: str(nc))

    da = adapter.read("overshoot", "hl", "ukesm", None, "landCoverFrac")

    assert da.dims == ("lat", "lon", "pft")
    assert np.isnan(da.isel(lat=0, lon=0)).all()
    assert da.sum("pft").values[1, 1] == 100.0
