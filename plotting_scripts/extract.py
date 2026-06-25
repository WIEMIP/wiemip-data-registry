# Generalised global-integral extractor for WIE-MIP 1pctCO2 output.
# One row of per-model "adapter" knowledge (grid, time encoding, area recipe, fill masking),
# driven over experiments x variables. Writes one tidy CSV per (experiment, model, variable):
#   /tmp/wiemip/series/<exp>__<model>__<req>.csv   columns: year,value
# Stocks -> Pg C ; fluxes -> Pg C/yr (annual-mean rate * seconds/yr).  Runs on the ubuntu box.
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path("/mnt/wiemip/1pctCO2/output")
OUT  = Path("/tmp/wiemip/series"); OUT.mkdir(parents=True, exist_ok=True)
SPY  = 365.25 * 86400.0

CMIP   = {"vegc": "cVeg", "soilc": "cSoil", "litc": "cLitter",
          "mgpp": "gpp", "mnpp": "npp", "rh": "rh", "mnbp": "nbp", "firec": "fFire"}
STOCKS = {"vegc", "soilc", "litc"}
REQS   = ["vegc", "soilc", "litc", "mgpp", "mnpp", "rh", "mnbp", "firec"]
EXPS   = ["bgc", "ctrl", "cou"]

# Base (no-factorial) run path prefix per model per experiment. cou = UKESM-forced.
RUNS = {
 "BiomeE":   {"bgc": "BiomeE/BiomeE_ukesm_bgc_", "cou": "BiomeE/BiomeE_ukesm_cou_"},  # no ctrl
 "CLASSIC":  {"bgc": "CLASSIC/CLASSIC_UKESM_1pctCO2-BGC/CLASSIC_UKESM_1pctCO2-BGC_",
              "cou": "CLASSIC/CLASSIC_UKESM_1pctCO2-COU/CLASSIC_UKESM_1pctCO2-COU_",
              "ctrl": "CLASSIC/CLASSIC_stable_piControl/CLASSIC_stable_"},
 "DLEM":     {"bgc": "DLEM/1pctCO2_BGC_ndep/DLEM_bgc_",
              "cou": "DLEM/1pctCO2_COU_UKESM_ndep/DLEM_ukesm_cou_",
              "ctrl": "DLEM/1pctCO2_CTRL/DLEM_ctrl_"},
 "JSBACH":   {"bgc": "JSBACH/JSBACH_stable_bgc/JSBACH_stable_bgc_",
              "cou": "JSBACH/JSBACH_ukesm_cou/JSBACH_ukesm_cou_",
              "ctrl": "JSBACH/JSBACH_stable_ctrl/JSBACH_stable_ctrl_"},
 "JULES":    {"bgc": "JULES/JULESwiemipV2_bgc_Nitrogen_DynVeg_Permafrost_noFire/JULESwiemipV2_bgc_",
              "cou": "JULES/JULESwiemipV2_ukesm_cou_Nitrogen_DynVeg_Permafrost_noFire/JULESwiemipV2_ukesm_cou_",
              "ctrl": "JULES/JULESwiemipV2_ctl_Nitrogen_DynVeg_Permafrost_noFire/JULESwiemipV2_ctl_"},
 "LPX-Bern": {"bgc": "LPX-Bern/LPX-Bern_bgc_", "cou": "LPX-Bern/LPX-Bern_cou_UKESM_",
              "ctrl": "LPX-Bern/LPX-Bern_ctrl_"},
 "VISIT-UT": {"bgc": "VISIT-UT/VISIT-UT_BGC/VISIT-UT_BGC_",
              "cou": "VISIT-UT/VISIT-UT_ukesm_COU/VISIT-UT_ukesm_COU_",
              "ctrl": "VISIT-UT/VISIT-UT_CTRL/VISIT-UT_CTRL_"},
}
DECODE = {"BiomeE": True, "CLASSIC": True, "JSBACH": True, "JULES": True,
          "DLEM": False, "LPX-Bern": False, "VISIT-UT": False}
LATLON = {"BiomeE": ("lat", "lon"), "CLASSIC": ("latitude", "longitude"), "DLEM": ("lat", "lon"),
          "JSBACH": ("lat", "lon"), "JULES": ("latitude", "longitude"),
          "LPX-Bern": ("latitude", "longitude"), "VISIT-UT": ("lat", "lon")}
HAS_FLUX = {"JULES": False}  # JULES submitted only cVeg & cSoil


def fname(model, prefix, req, stock):
    var = CMIP[req]
    if model == "BiomeE":   return ROOT / f"{prefix}{var}_{'yr' if stock else 'mon'}_05.nc"
    if model == "CLASSIC":  return ROOT / f"{prefix}{var}_{'ann' if stock else 'mon'}_1deg.nc"
    if model == "DLEM":     return ROOT / f"{prefix}{var}_{'yr' if stock else 'mon'}_05.nc"
    if model == "JSBACH":   return ROOT / f"{prefix}{var}_{'yr' if stock else 'mon'}_1.nc"
    if model == "JULES":    return ROOT / f"{prefix}{var}_yr_Nitrogen_DynVeg_Permafrost_noFire_n96.nc"
    if model == "LPX-Bern": return ROOT / f"{prefix}{var}_{'yr' if stock else 'mon'}_1.nc"
    if model == "VISIT-UT": return ROOT / f"{prefix}{var}_mon_05.nc"


def spherical_area(ds, latn, lonn):
    lat, lon = ds[latn].values, ds[lonn].values
    R = 6.371e6
    dlat, dlon = np.abs(np.gradient(lat)), np.abs(np.gradient(lon))
    band = R**2 * (np.sin(np.deg2rad(lat + dlat / 2)) - np.sin(np.deg2rad(lat - dlat / 2)))
    return xr.DataArray(band[:, None] * np.deg2rad(dlon)[None, :], dims=(latn, lonn),
                        coords={latn: ds[latn], lonn: ds[lonn]}).astype("float32")


def build_area(model):
    """Per-model grid-cell weight [m2]. Uses provided rasters where the README supplies one."""
    latn, lonn = LATLON[model]
    if model == "BiomeE":
        a = xr.open_dataset(ROOT / "BiomeE/veg_area.nc")["veg_area"].drop_vars("time", errors="ignore")
        return a.astype("float32"), latn, lonn
    if model == "LPX-Bern":
        a = xr.open_dataset(ROOT / "LPX-Bern/gridcell_area.nc")["area"]
        return a.astype("float32"), latn, lonn
    if model == "JULES":
        ref = xr.open_dataset(fname("JULES", RUNS["JULES"]["bgc"], "vegc", True))
        cell = spherical_area(ref, latn, lonn); ref.close()
        land = xr.open_dataset(ROOT / "JULES/landfrac_n96.nc")["land"]
        return (cell * land.where(land <= 1.0, 0.0)).astype("float32"), latn, lonn
    if model == "CLASSIC":
        # CLASSIC global integral needs land fraction too (per V. Arora): area x sftlf x quantity.
        # sftlf is static and identical across CLASSIC runs, so load it once from the BGC run.
        ref = xr.open_dataset(fname("CLASSIC", RUNS["CLASSIC"]["bgc"], "vegc", True))
        cell = spherical_area(ref, latn, lonn); ref.close()
        sftlf = xr.open_dataset(ROOT / "CLASSIC/CLASSIC_UKESM_1pctCO2-BGC/"
                                "CLASSIC_UKESM_1pctCO2-BGC_land_fraction_ann_1deg.nc")["sftlf"]
        return (cell * sftlf).astype("float32"), latn, lonn
    ref = xr.open_dataset(fname(model, RUNS[model]["bgc"], "vegc", True), decode_times=DECODE[model])
    a = spherical_area(ref, latn, lonn); ref.close()
    return a, latn, lonn


def years_of(model, ds):
    if model in ("BiomeE", "CLASSIC", "JSBACH"):
        return ds["time"].dt.year.values
    if model == "JULES":
        return ds["year"].values if "year" in ds.coords else ds["time"].dt.year.values
    if model == "DLEM":
        tu, tv = ds["time"].attrs.get("units", ""), ds["time"].values
        return (1850 + tv // 12).astype(int) if "months since" in tu else (1850 + tv).astype(int)
    return np.floor(ds["time"].values).astype(int)  # LPX-Bern, VISIT-UT


def maskvar(model, da):
    # Mask sentinel fills not always declared as _FillValue: BiomeE -1e5, JULES noNitrogen -9999,
    # stray -99999. No physical stock/flux is below -1e3, so this is a safe universal floor.
    return da.where(da > -1e3)


def main():
    for model in RUNS:
        area, latn, lonn = build_area(model)
        for exp in EXPS:
            if exp not in RUNS[model]:
                continue
            prefix = RUNS[model][exp]
            for req in REQS:
                stock = req in STOCKS
                if not stock and not HAS_FLUX.get(model, True):
                    continue
                outf = OUT / f"{exp}__{model}__{req}.csv"
                if outf.exists():
                    continue
                path = fname(model, prefix, req, stock)
                if not path.exists():
                    print(f"MISS  {exp:4s} {model:9s} {req:6s} {path.name}", flush=True)
                    continue
                try:
                    ds = xr.open_dataset(path, decode_times=DECODE[model])
                    da = maskvar(model, ds[CMIP[req]])
                    gts = (da * area).sum((latn, lonn), skipna=True, dtype="float64")
                    ann = pd.Series(np.asarray(gts.values),
                                    index=np.asarray(years_of(model, ds))).groupby(level=0).mean()
                    val = ann.values / 1e12 if stock else ann.values * SPY / 1e12
                    ds.close()
                except Exception as e:
                    print(f"ERR   {exp:4s} {model:9s} {req:6s} {e!r}"[:110], flush=True)
                    continue
                if not np.isfinite(val).any() or np.nanmax(np.abs(val)) == 0:
                    print(f"ZERO  {exp:4s} {model:9s} {req:6s}", flush=True)
                    continue
                pd.DataFrame({"year": ann.index.values, "value": val}).to_csv(outf, index=False)
                print(f"OK    {exp:4s} {model:9s} {req:6s} {int(ann.index.min())}-{int(ann.index.max())} "
                      f"f={val[0]:.3g} l={val[-1]:.3g}", flush=True)


if __name__ == "__main__":
    main()
