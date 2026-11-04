import pytest

from wiemip_registry.LPJ_GUESS.convert import LPJ_GUESS

RUN = "LPJ-GUESS_stable_1pctCO2-BGC"

# baseline bgc files uploaded 2026-11-01, spelled with the run dir as their prefix
DIR_STYLE_UPLOADS = [
    ("ch4", "LPJ-GUESS_stable_1pctCO2-BGC_ch4_mon_05deg.nc"),
    ("gpppft", "LPJ-GUESS_stable_1pctCO2-BGC_gpppft_mon_05deg.nc"),
    ("isopr", "LPJ-GUESS_stable_1pctCO2-BGC_isopr_mon_05deg.nc"),
    ("laipft", "LPJ-GUESS_stable_1pctCO2-BGC_laipft_mon_05deg.nc"),
    ("nLitter", "LPJ-GUESS_stable_1pctCO2-BGC_nLitter_yr_05deg.nc"),
    ("terp", "LPJ-GUESS_stable_1pctCO2-BGC_terp_mon_05deg.nc"),
]


@pytest.mark.parametrize("variable, uploaded", DIR_STYLE_UPLOADS)
def test_bgc_dir_style_uploads_are_reached(variable, uploaded):
    path = LPJ_GUESS().one_pct_path("bgc", "stable", "baseline", variable)
    assert path.endswith(f"/LPJ-GUESS/{RUN}/{uploaded}")


@pytest.mark.parametrize("variable", ["cVeg", "cLitter", "nLitterpft"])
def test_bgc_older_uploads_keep_their_spelling(variable):
    path = LPJ_GUESS().one_pct_path("bgc", "stable", "baseline", variable)
    assert f"/{RUN}/LPJ-GUESS_stable_1pctco2_BGC_{variable}_" in path


def test_ctrl_isopr_is_not_dir_style():
    path = LPJ_GUESS().one_pct_path("ctrl", "stable", "baseline", "isopr")
    assert path.endswith(
        "/LPJ-GUESS_stable_1pctCO2-CRTL/LPJ-GUESS_stable_1pctco2_control_isopr_mon_05deg.nc"
    )
