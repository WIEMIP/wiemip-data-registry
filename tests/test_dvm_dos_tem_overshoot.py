import warnings

import numpy as np
import xarray as xr

import wiemip_registry as wr
from wiemip_registry.DVM_DOS_TEM.convert import DVM_DOS_TEM

ROOT = "overshoot/output/DVM-DOS-TEM/"


def test_hist_reads_the_historic_run():
    f = wr.retrieve_overshoot_variable("DVM_DOS_TEM", "ukesm", "hist", "cVeg")
    assert f.path.endswith(
        ROOT + "DVM-DOS-TEM_historic/DVM-DOS-TEM_historic_cVeg_yr_05.nc"
    )


def test_hist_ctrl_and_ctrl_read_the_ctrl_run():
    for simulation in ("hist_ctrl", "ctrl"):
        f = wr.retrieve_overshoot_variable("DVM_DOS_TEM", "gfdl", simulation, "gpp")
        assert f.path.endswith(ROOT + "DVM-DOS-TEM_ctrl/DVM-DOS-TEM_ctrl_gpp_mon_05.nc")


def test_ukesm_scenario_has_no_forcing_token():
    f = wr.retrieve_overshoot_variable("DVM_DOS_TEM", "ukesm", "hl_ctap", "cVeg")
    assert f.path.endswith(ROOT + "DVM-DOS-TEM_hl_cf/DVM-DOS-TEM_hl_cf_cVeg_yr_05.nc")


def test_other_forcings_do_not_alias_the_ukesm_scenario():
    f = wr.retrieve_overshoot_variable("DVM_DOS_TEM", "ukesm", "hl", "cVeg")
    g = wr.retrieve_overshoot_variable("DVM_DOS_TEM", "gfdl", "hl", "cVeg")
    assert g.path != f.path
    assert "DVM-DOS-TEM_gfdl_hl/" in g.path


def test_overshoot_reads_the_uploaded_time_axis(tmp_path, monkeypatch):
    # Monthly from 2024, noleap days since 1850, as in the 2026-10-15 re-upload.
    month_starts = np.array([0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334])
    days = 174 * 365 + np.concatenate([month_starts, 365 + month_starts])
    time = xr.Variable(
        "time",
        days.astype("float64"),
        {"units": "days since 1850-01-01", "calendar": "365_day"},
    )
    nc = tmp_path / "DVM-DOS-TEM_hl_gpp_mon_05.nc"
    xr.Dataset(
        {
            "gpp": (("time", "y", "x"), np.ones((24, 2, 3), dtype="float32")),
            "Y": ("y", np.array([60.25, 60.75], dtype="float32")),
            "X": ("x", np.array([-150.25, -149.75, -149.25], dtype="float32")),
        },
        coords={"time": time},
    ).to_netcdf(nc)
    adapter = DVM_DOS_TEM()
    monkeypatch.setattr(adapter, "path", lambda *args: str(nc))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        da = adapter.read("overshoot", "hl", "ukesm", None, "gpp")

    assert not [w for w in caught if "SYNTHESIZED" in str(w.message)]
    assert da.time.values[0] == np.datetime64("2024-01-01")
    assert da.time.values[13] == np.datetime64("2025-02-01")
    assert da.sizes == {"time": 24, "lat": 2, "lon": 3}
