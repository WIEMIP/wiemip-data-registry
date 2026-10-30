import pytest

from wiemip_registry.LPJ_GUESS.convert import LPJ_GUESS

UPLOADED = [
    (
        "bgc",
        "stable",
        "cVeg",
        "LPJ_GUESS_Stable_1pctCO2-No_N_Cycle_BGC/"
        "LPJ-GUESS_stable_1pctco2_No_N_Cycle_BGC_cVeg_yr_05deg.nc",
    ),
    (
        "ctrl",
        "stable",
        "gpp",
        "LPJ_GUESS_Stable_1pctCO2-No_N_Cycle_Control/"
        "LPJ-GUESS_stable_1pctco2_No_N_Cycle_Control_gpp_mon_05deg.nc",
    ),
    (
        "ctrl",
        "stable",
        "landCoverFrac",
        "LPJ_GUESS_Stable_1pctCO2-No_N_Cycle_Control/"
        "LPJ-GUESS_stable_1pctco2_No_N_Cycle_Control_LandCoverFrac_yr_05deg.nc",
    ),
    (
        "ctrl",
        "stable",
        "nLitter",
        "LPJ_GUESS_Stable_1pctCO2-No_N_Cycle_Control/"
        "LPJ-GUESS_stable_1pctco2_No_N_Cycle_Control_nLiitter_yr_05deg.nc",
    ),
    (
        "cou",
        "ukesm",
        "cSoil",
        "LPJ_GUESS_UKESM_1pctCO2-No_N_Cycle_COU/"
        "LPJ-GUESS_UKESM_1pctco2_NO_N_Cycle_COU_cSoil_yr_05deg.nc",
    ),
    (
        "cou",
        "ukesm",
        "npp",
        "LPJ_GUESS_UKESM_1pctCO2-No_N_Cycle_COU/"
        "LPJ-GUESS_UKESM_1pctco2_NO_N_Cycle_COU_npp_mom_05deg.nc",
    ),
]


@pytest.mark.parametrize("simulation, forcing, variable, uploaded", UPLOADED)
def test_no_nitrogen_paths_match_upload(simulation, forcing, variable, uploaded):
    path = LPJ_GUESS().one_pct_path(simulation, forcing, "noNitrogen", variable)
    assert path.endswith(f"/LPJ-GUESS/{uploaded}")


def test_no_nitrogen_cou_keeps_its_forcing():
    path = LPJ_GUESS().one_pct_path("cou", "ipsl", "noNitrogen", "cVeg")
    assert "_IPSL_" in path and "UKESM" not in path
