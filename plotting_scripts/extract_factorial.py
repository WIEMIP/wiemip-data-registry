# Extract global series for FACTORIAL (sensitivity) runs, for both BGC and COU simulations,
# reusing extract.py's per-model adapters. Writes:
#   /tmp/wiemip/series_fac/<sim>__<factorial>__<model>__<req>.csv   columns: year,value
# Factorial filename conventions differ per model, so paths are explicit templates ({var},{cad}).
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

import extract as E  # build_area, years_of, maskvar, CMIP, STOCKS, REQS, DECODE, HAS_FLUX, ROOT, SPY

OUT = Path("/tmp/wiemip/series_fac"); OUT.mkdir(parents=True, exist_ok=True)

# simulation -> factorial -> model -> path template (relative to E.ROOT), {var} & {cad} placeholders
FAC = {
 "bgc": {
   "noNitrogen": {
     "CLASSIC": "CLASSIC/CLASSIC_UKESM_1pctCO2-BGC_noNitrogen/CLASSIC_UKESM_1pctCO2-BGC_{var}_{cad}_noNitrogen_1deg.nc",
     "JSBACH":  "JSBACH/JSBACH_stable_bgc_noNitrogen/JSBACH_stable_bgc_{var}_{cad}_noNitrogen_1.nc",
     "JULES":   "JULES/JULESwiemipV2_bgc_noNitrogen_DynVeg_Permafrost_noFire/JULESwiemipV2_bgc_{var}_{cad}_noNitrogen_DynVeg_Permafrost_noFire_n96.nc",
   },
   "noFire": {
     "CLASSIC":  "CLASSIC/CLASSIC_UKESM_1pctCO2-BGC_noFire/CLASSIC_UKESM_1pctCO2-BGC_{var}_{cad}_noFire_1deg.nc",
     "LPX-Bern": "LPX-Bern/LPX-Bern_nofire_bgc_{var}_{cad}_1.nc",
     "VISIT-UT": "VISIT-UT/VISIT-UT_BGC_noFire/VISIT-UT_BGC_{var}_{cad}_noFire_05.nc",
   },
   "noPermafrost": {
     "LPX-Bern": "LPX-Bern/LPX-Bern_nopermafrost_bgc_{var}_{cad}_1.nc",
     "JULES":    "JULES/JULESwiemipV2_bgc_Nitrogen_DynVeg_noPermafrostC_noFire/JULESwiemipV2_bgc_{var}_{cad}_Nitrogen_DynVeg_noPermafrostC_noFire_n96.nc",
   },
   "noBVOC": {
     "VISIT-UT": "VISIT-UT/VISIT-UT_BGC_noBVOC/VISIT-UT_BGC_{var}_{cad}_noBVOC_05.nc",
   },
 },
 "cou": {
   "noNitrogen": {
     "CLASSIC": "CLASSIC/CLASSIC_UKESM_1pctCO2-COU_noNitrogen/CLASSIC_UKESM_1pctCO2-COU_{var}_{cad}_noNitrogen_1deg.nc",
     "JSBACH":  "JSBACH/JSBACH_ukesm_cou_noNitrogen/JSBACH_ukesm_cou_{var}_{cad}_noNitrogen_1.nc",
     "JULES":   "JULES/JULESwiemipV2_ukesm_cou_noNitrogen_DynVeg_Permafrost_noFire/JULESwiemipV2_ukesm_cou_{var}_{cad}_noNitrogen_DynVeg_Permafrost_noFire_n96.nc",
   },
   "noFire": {
     "CLASSIC":  "CLASSIC/CLASSIC_UKESM_1pctCO2-COU_noFire/CLASSIC_UKESM_1pctCO2-COU_{var}_{cad}_noFire_1deg.nc",
     "LPX-Bern": "LPX-Bern/LPX-Bern_nofire_cou_UKESM_{var}_{cad}_1.nc",
     "VISIT-UT": "VISIT-UT/VISIT-UT_ukesm_COU_noFire/VISIT-UT_ukesm_COU_{var}_{cad}_noFire_05.nc",
   },
   "noPermafrost": {
     "LPX-Bern": "LPX-Bern/LPX-Bern_nopermafrost_cou_UKESM_{var}_{cad}_1.nc",
     "JULES":    "JULES/JULESwiemipV2_ukesm_cou_Nitrogen_DynVeg_noPermafrostC_noFire/JULESwiemipV2_ukesm_cou_{var}_{cad}_Nitrogen_DynVeg_noPermafrostC_noFire_n96.nc",
   },
   "noBVOC": {
     "VISIT-UT": "VISIT-UT/VISIT-UT_ukesm_COU_noBVOC/VISIT-UT_ukesm_COU_{var}_{cad}_noBVOC_05.nc",
   },
 },
}


def cad_token(model, stock):
    if model == "CLASSIC":  return "ann" if stock else "mon"
    if model == "VISIT-UT": return "mon"
    if model == "JULES":    return "yr"
    return "yr" if stock else "mon"          # JSBACH, LPX-Bern


area_cache = {}


def main():
    for sim, facs in FAC.items():
        for fac, models in facs.items():
            for model, tmpl in models.items():
                if model not in area_cache:
                    area_cache[model] = E.build_area(model)
                area, latn, lonn = area_cache[model]
                for req in E.REQS:
                    stock = req in E.STOCKS
                    if not stock and not E.HAS_FLUX.get(model, True):
                        continue
                    outf = OUT / f"{sim}__{fac}__{model}__{req}.csv"
                    if outf.exists():
                        continue
                    path = E.ROOT / tmpl.format(var=E.CMIP[req], cad=cad_token(model, stock))
                    if not path.exists():
                        print(f"MISS  {sim} {fac:13s} {model:9s} {req:6s} {path.name}", flush=True)
                        continue
                    try:
                        ds = xr.open_dataset(path, decode_times=E.DECODE[model])
                        da = E.maskvar(model, ds[E.CMIP[req]])
                        gts = (da * area).sum((latn, lonn), skipna=True, dtype="float64")
                        ann = pd.Series(np.asarray(gts.values),
                                        index=np.asarray(E.years_of(model, ds))).groupby(level=0).mean()
                        val = ann.values / 1e12 if stock else ann.values * E.SPY / 1e12
                        ds.close()
                    except Exception as e:
                        print(f"ERR   {sim} {fac:13s} {model:9s} {req:6s} {e!r}"[:110], flush=True)
                        continue
                    if not np.isfinite(val).any() or np.nanmax(np.abs(val)) == 0:
                        print(f"ZERO  {sim} {fac:13s} {model:9s} {req:6s}", flush=True)
                        continue
                    pd.DataFrame({"year": ann.index.values, "value": val}).to_csv(outf, index=False)
                    print(f"OK    {sim} {fac:13s} {model:9s} {req:6s} {int(ann.index.min())}-{int(ann.index.max())} "
                          f"f={val[0]:.3g} l={val[-1]:.3g}", flush=True)


if __name__ == "__main__":
    main()
