import numpy as np
import pytest
import xarray as xr

import wiemip_registry as wr
from wiemip_registry.DLEM.convert import DLEM


@pytest.mark.parametrize(
    "simulation, forcing, expected",
    [
        (
            "bgc",
            "stable",
            "1pctCO2/output/DLEM/1pctCO2_BGC/DLEM_bgc_noNdep_trans_mon_05.nc",
        ),
        (
            "cou",
            "ukesm",
            "1pctCO2/output/DLEM/1pctCO2_COU_UKESM/DLEM_ukesm_cou_noNdep_trans_mon_05.nc",
        ),
        (
            "ctrl",
            "stable",
            "1pctCO2/output/DLEM/1pctCO2_CTRL/DLEM_ctrl_trans_mon_05.nc",
        ),
    ],
)
def test_one_pct_tveg_reads_the_uploaded_trans_file(simulation, forcing, expected):
    f = wr.retrieve_one_pct_variable("DLEM", forcing, simulation, "baseline", "tveg")
    assert f.path.endswith(expected)


@pytest.mark.parametrize(
    "simulation, expected",
    [
        ("hist", "overshoot/output/DLEM/os_hist/DLEM_hist_trans_mon_05.nc"),
        ("hl", "overshoot/output/DLEM/os_future_hl/DLEM_ukesm_hl_trans_mon_05.nc"),
    ],
)
def test_overshoot_tveg_reads_the_uploaded_trans_file(simulation, expected):
    f = wr.retrieve_overshoot_variable("DLEM", "ukesm", simulation, "tveg")
    assert f.path.endswith(expected)


def test_tveg_read_takes_the_trans_field(tmp_path, monkeypatch):
    path = tmp_path / "trans.nc"
    time = xr.DataArray([0, 1], dims="time", attrs={"units": "months since 1850-01-01"})
    xr.Dataset(
        {
            "trans": (
                ("time", "lat", "lon"),
                np.full((2, 1, 1), 2e-5, dtype="float32"),
                {"units": "kg m-2 s-1"},
            )
        },
        coords={"time": time, "lat": [10.25], "lon": [20.25]},
    ).to_netcdf(path)
    monkeypatch.setattr(DLEM, "path", lambda self, *args: str(path))
    da = DLEM().read("1pctCO2", "bgc", "stable", "baseline", "tveg")
    assert float(da.isel(time=1, lat=0, lon=0)) == pytest.approx(2e-5)
    assert str(da["time"].values[1])[:7] == "1850-02"
