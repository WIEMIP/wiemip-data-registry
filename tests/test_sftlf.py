import numpy as np
import pytest
import xarray as xr

import wiemip_registry as wr
from wiemip_registry.CLASSIC.convert import CLASSIC
from wiemip_registry.CLM.convert import CLM
from wiemip_registry.CoLM.convert import CoLM
from wiemip_registry.EDv3.convert import EDv3
from wiemip_registry.ELM.convert import ELM
from wiemip_registry.JSBACH.convert import JSBACH
from wiemip_registry.JULES.convert import JULES

ONE_PCT_PATHS = [
    (
        "CoLM",
        "stable",
        "bgc",
        "baseline",
        "CoLM/CoLM_stable_bgc/CoLM_stable_bgc_sftlf_fx_1.nc",
    ),
    (
        "EDv3",
        "stable",
        "bgc",
        "baseline",
        "EDv3/1ptco2_stable_bgc/EDv3_stable_bgc_landFrac_fx_05.nc",
    ),
    (
        "EDv3",
        "ukesm",
        "cou",
        "noFire",
        "EDv3/1ptco2_ukesm_cou_nofire/EDv3_ukesm_cou_nofire_landFrac_fx_05.nc",
    ),
    (
        "CLASSIC",
        "stable",
        "bgc",
        "baseline",
        "CLASSIC/CLASSIC_stable_1pctCO2-BGC/CLASSIC_1pctCO2-BGC_land_fraction_ann_1deg.nc",
    ),
    (
        "CLASSIC",
        "stable",
        "ctrl",
        "noFire",
        "CLASSIC/CLASSIC_stable_piControl_noFire/CLASSIC_stable_land_fraction_ann_noFire_1deg.nc",
    ),
    (
        "CLASSIC",
        "ukesm",
        "cou_ndep",
        "baseline",
        "CLASSIC/CLASSIC_UKESM_1pctCO2-COU-Ndep/CLASSIC_UKESM_1pctCO2-COU-Ndep_land_fraction_ann_1deg.nc",
    ),
    ("JSBACH", "ukesm", "cou", "noFire", "1pctCO2/output/JSBACH/sftlf_1.nc"),
    ("JULES", "stable", "bgc", "Fire0005", "1pctCO2/output/JULES/landfrac_n96.nc"),
    ("ELM", "stable", "ctrl", "noFire", "1pctCO2/output/ELM/landfrac.360x720.nc"),
    (
        "CLM",
        "stable",
        "bgc",
        "flat",
        "1pctCO2/output/CLM/hh_ukesm_bgc/clm6_hh_ukesm_bgc_cVeg.nc",
    ),
]

OVERSHOOT_PATHS = [
    ("CoLM", "ukesm", "hist", None, "CoLM/CoLM_hist/CoLM_hist_sftlf_fx_1.nc"),
    (
        "CoLM",
        "ukesm",
        "hl_cf",
        None,
        "CoLM/CoLM_ukesm_hl_cf/CoLM_ukesm_hl_cf_sftlf_fx_1.nc",
    ),
    ("EDv3", "gfdl", "l", None, "EDv3/overshoot_gfdl_l/EDv3_gfdl_l_landFrac_fx_05.nc"),
    (
        "EDv3",
        "ukesm",
        "hist",
        None,
        "EDv3/overshoot_crujra_hist/EDv3_crujra_hist_landFrac_fx_05.nc",
    ),
    ("JSBACH", "ukesm", "hl", None, "1pctCO2/output/JSBACH/sftlf_1.nc"),
    ("JULES", "ukesm", "l", "Fire0249", "1pctCO2/output/JULES/landfrac_n96.nc"),
    (
        "CLM",
        "ukesm",
        "hl",
        None,
        "1pctCO2/output/CLM/hh_ukesm_bgc/clm6_hh_ukesm_bgc_cVeg.nc",
    ),
]


@pytest.mark.parametrize(
    "model, forcing, simulation, factorial, expected", ONE_PCT_PATHS
)
def test_one_pct_sftlf_spells_the_land_fraction_file(
    model, forcing, simulation, factorial, expected
):
    f = wr.retrieve_one_pct_variable(model, forcing, simulation, factorial, "sftlf")
    assert f.paths == [f.path]
    assert f.path.endswith(expected)


@pytest.mark.parametrize(
    "model, forcing, simulation, factorial, expected", OVERSHOOT_PATHS
)
def test_overshoot_sftlf_spells_the_land_fraction_file(
    model, forcing, simulation, factorial, expected
):
    f = wr.retrieve_overshoot_variable(
        model, forcing, simulation, "sftlf", factorial=factorial
    )
    assert f.paths == [f.path]
    assert f.path.endswith(expected)


# adapter, field the land fraction is stored under, the file's (lat, lon) dim names
READS = [
    (CoLM, "sftlf", ("latitude", "longitude")),
    (EDv3, "landFrac", ("longitude", "latitude")),
    (CLASSIC, "sftlf", ("latitude", "longitude")),
    (JSBACH, "sftlf", ("latitude", "longitude")),
    (JULES, "land", ("latitude", "longitude")),
    (ELM, "landfrac", ("lat", "lon")),
    (CLM, "landfrac", ("lat", "lon")),
]


@pytest.mark.parametrize("adapter_class, field, dims", READS)
def test_sftlf_reads_a_lat_lon_field(adapter_class, field, dims, tmp_path, monkeypatch):
    lat_name = dims[0] if dims[0].startswith("lat") else dims[1]
    lon_name = dims[1] if dims[1].startswith("lon") else dims[0]
    shape = (3, 2) if dims[0] == lat_name else (2, 3)
    nc = tmp_path / "land_fraction.nc"
    xr.Dataset(
        {
            field: (dims, np.full(shape, 0.25), {"units": "1"}),
            "cVeg": (("time",) + dims, np.zeros((2,) + shape)),
        },
        coords={
            "time": ("time", [0.0, 1.0], {"units": "hours since 1850-01-01"}),
            lat_name: [-10.0, 0.0, 10.0],
            lon_name: [0.0, 1.0],
        },
    ).to_netcdf(nc)
    adapter = adapter_class()
    monkeypatch.setattr(adapter, "path", lambda *args: str(nc))

    da = adapter.read("1pctCO2", "bgc", "stable", "baseline", "sftlf")

    assert da.dims == ("lat", "lon")
    assert da.sizes == {"lat": 3, "lon": 2}
    assert float(da.mean()) == 0.25
    assert da.attrs["units"] == "1"


def test_jules_sftlf_masks_the_undeclared_ocean_fill(tmp_path, monkeypatch):
    nc = tmp_path / "landfrac_n96.nc"
    xr.Dataset(
        {
            "land": (
                ("latitude", "longitude"),
                np.array([[0.5, 9.969209968386869e36]], dtype="float32"),
            )
        },
        coords={"latitude": [0.0], "longitude": [0.0, 1.0]},
    ).to_netcdf(nc)
    adapter = JULES()
    monkeypatch.setattr(adapter, "path", lambda *args: str(nc))

    da = adapter.read("1pctCO2", "bgc", "stable", "baseline", "sftlf")

    assert float(da.isel(lat=0, lon=0)) == 0.5
    assert np.isnan(float(da.isel(lat=0, lon=1)))
