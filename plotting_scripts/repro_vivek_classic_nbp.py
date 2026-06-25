# Reproduce Vivek Arora's CLASSIC "Cumulative net biome productivity" figure:
# the 7 cnf (carbon-nitrogen-fire, all-on) CLASSIC runs — spinup + {BGC,COU,RAD} x {no-Ndep,Ndep},
# all UKESM-forced. Cumulative NBP (Pg C), legend shows mean of last 20 yr (as in his deck).
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import extract as E   # build_area("CLASSIC") -> area x sftlf ; maskvar ; ROOT ; SPY

# (label, colour, nbp file relative to ROOT)
RUNS = [
    ("spinup / piControl", "tab:green",  "CLASSIC/CLASSIC_stable_piControl/CLASSIC_stable_nbp_mon_1deg.nc"),
    ("BGC-UKESM",          "tab:pink",   "CLASSIC/CLASSIC_UKESM_1pctCO2-BGC/CLASSIC_UKESM_1pctCO2-BGC_nbp_mon_1deg.nc"),
    ("BGC-Ndep-UKESM",     "tab:orange", "CLASSIC/CLASSIC_UKESM_1pctCO2-BGC-Ndep/CLASSIC_UKESM_1pctCO2-BGC-Ndep_nbp_mon_1deg.nc"),
    ("COU-UKESM",          "tab:blue",   "CLASSIC/CLASSIC_UKESM_1pctCO2-COU/CLASSIC_UKESM_1pctCO2-COU_nbp_mon_1deg.nc"),
    ("COU-Ndep-UKESM",     "tab:red",    "CLASSIC/CLASSIC_UKESM_1pctCO2-COU-Ndep/CLASSIC_UKESM_1pctCO2-COU-Ndep_nbp_mon_1deg.nc"),
    ("RAD-UKESM",          "tab:purple", "CLASSIC/CLASSIC_UKESM_1pctCO2-RAD/CLASSIC_UKESM_1pctCO2-RAD_nbp_mon_1deg.nc"),
    ("RAD-Ndep-UKESM",     "indigo",     "CLASSIC/CLASSIC_UKESM_1pctCO2-RAD-Ndep/CLASSIC_UKESM_1pctCO2-RAD-Ndep_nbp_mon_1deg.nc"),
]

area, latn, lonn = E.build_area("CLASSIC")   # area x sftlf [m2]

fig, ax = plt.subplots(figsize=(9, 6.5))
for label, color, rel in RUNS:
    ds = xr.open_dataset(E.ROOT / rel)                          # datetime
    da = E.maskvar("CLASSIC", ds["nbp"])
    gts = (da * area).sum((latn, lonn), skipna=True, dtype="float64")
    ann = pd.Series(np.asarray(gts.values),
                    index=np.asarray(ds["time"].dt.year.values)).groupby(level=0).mean()
    flux = ann.values * E.SPY / 1e12                            # annual NBP, Pg C/yr
    cum = np.cumsum(flux); cum = cum - cum[0]                   # cumulative, anchored 0 at start
    last20 = cum[-20:].mean()
    ax.plot(ann.index.values, cum, color=color, lw=1.8, label=f"{label} ({last20:.1f})")
    ds.close()

ax.set_ylim(-600, 800)
ax.set_xlim(1850, 2000)
ax.axhline(0, color="k", lw=0.8, ls="--")
ax.set_xlabel("Year")
ax.set_ylabel("Cumulative net biome productivity (Pg C)")
ax.set_title("Cumulative NBP")
ax.legend(loc="upper left", fontsize=9, title="(mean over last 20 yr)")
ax.grid(alpha=0.3)
fig.tight_layout()
outf = Path("/tmp/wiemip/repro_vivek_classic_nbp.png")
fig.savefig(outf, dpi=150, bbox_inches="tight")
print(f"wrote {outf}")
for label, _, _ in RUNS:
    pass
