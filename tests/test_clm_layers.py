def test_clm_layered_variables_resolve_to_deep_dirs():
    from wiemip_registry.CLM.convert import CLM

    clm = CLM()
    soil_t = clm.path("1pctCO2", "bgc", "stable", "baseline", "soilT")
    assert soil_t.endswith("CLM/hh_ukesm_bgc_deep/clm6_hh_ukesm_bgc_soilT.nc")
    assert clm.path("1pctCO2", "cou", "gfdl", "baseline", "cVeg").endswith(
        "CLM/hh_gfdl_cou/clm6_hh_gfdl_cou_cVeg.nc"
    )
    assert clm.path("1pctCO2", "bgc", "stable", "noNitrogen", "cVeg").endswith(
        "CLM/flat_ukesm_noN_bgc/clm6_flat_ukesm_noN_bgc_cVeg.1850-2000.nc"
    )
    assert "_deep" not in clm.path("overshoot", "hl", "ukesm", "baseline", "soilT")


def test_clm_nonitrogen_layered_variables_stay_in_the_plain_run_dir():
    from wiemip_registry.CLM.convert import CLM

    assert (
        CLM()
        .path("1pctCO2", "bgc", "stable", "noNitrogen", "soilT")
        .endswith("CLM/flat_ukesm_noN_bgc/clm6_flat_ukesm_noN_bgc_soilT.1850-2000.nc")
    )
