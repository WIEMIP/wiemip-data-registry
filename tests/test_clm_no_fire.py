import pytest

from wiemip_registry.CLM.convert import CLM


@pytest.mark.parametrize(
    "simulation, forcing, variable, uploaded",
    [
        (
            "bgc",
            "stable",
            "wetCH4",
            "flat_ukesm_noFire_bgc/clm6_flat_ukesm_noFire_bgc_wetCH4.1850-2000.nc",
        ),
        (
            "ctrl",
            "stable",
            "cVeg",
            "flat_ukesm_noFire_ctrl/clm6_flat_ukesm_noFire_ctrl_cVeg.1850-2000.nc",
        ),
        (
            "cou",
            "ukesm",
            "fFire",
            "flat_ukesm_noFire_cou/clm6_flat_ukesm_noFire_cou_fFire.1850-2000.nc",
        ),
        (
            "rad",
            "ukesm",
            "soilT",
            "flat_ukesm_noFire_rad/clm6_flat_ukesm_noFire_rad_soilT.1850-2000.nc",
        ),
    ],
)
def test_no_fire_uploads_are_reached(simulation, forcing, variable, uploaded):
    path = CLM().one_pct_path(simulation, forcing, "noFire", variable)
    assert path.endswith(f"/CLM/{uploaded}")
