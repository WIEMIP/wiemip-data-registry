import numpy as np
import xarray as xr

import wiemip_registry as wr
from wiemip_registry.VISIT_UT.convert import VISIT_UT


def test_one_pct_fch4soil_keeps_its_own_name():
    f = wr.retrieve_one_pct_variable(
        "VISIT_UT", "stable", "bgc", "baseline", "fch4soil"
    )
    assert f.path.endswith("VISIT-UT_BGC/VISIT-UT_BGC_fch4soil_mon_05.nc")


def test_overshoot_fch4soil_spells_fch4soilnat():
    f = wr.retrieve_overshoot_variable("VISIT_UT", "ukesm", "l", "fch4soil")
    assert f.path.endswith("VISIT-UT_ukesm_l/VISIT-UT_ukesm_l_fch4soilnat_mon_05.nc")


def test_overshoot_fch4soil_reads_the_fch4soilnat_field(tmp_path, monkeypatch):
    nc = tmp_path / "VISIT-UT_ukesm_l_fch4soilnat_mon_05.nc"
    xr.Dataset(
        {"fch4soilnat": (("time", "lat", "lon"), np.full((2, 1, 1), -1e-11))},
        coords={"time": [2024.0, 2024 + 1 / 12], "lat": [10.25], "lon": [20.25]},
    ).to_netcdf(nc)
    adapter = VISIT_UT()
    monkeypatch.setattr(adapter, "path", lambda *args: str(nc))

    da = adapter.read("overshoot", "l", "ukesm", None, "fch4soil")

    assert float(da.isel(time=0, lat=0, lon=0)) == -1e-11
