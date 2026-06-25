# One 8-panel figure per run type (bgc/ctrl/cou): global stocks & fluxes, one line per model.
# Reads /tmp/wiemip/series/<exp>__<model>__<req>.csv written by extract.py.
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SER    = Path("/tmp/wiemip/series")
OUTDIR = Path("/tmp/wiemip")
MODELS = ["BiomeE", "CLASSIC", "DLEM", "JSBACH", "JULES", "LPX-Bern", "VISIT-UT"]
COLORS = {m: c for m, c in zip(MODELS, plt.cm.tab10.colors)}
EXCLUDE_MODELS = {"BiomeE"}   # BiomeE excluded pending fix (submission error)
EXPS   = {"bgc": "BGC (biogeochemically coupled)",
          "ctrl": "CTRL / piControl",
          "cou": "COU (fully coupled, UKESM-forced)"}
PANELS = [("litc", "Litter carbon (cLitter)", "Pg C"),
          ("vegc", "Vegetation carbon (cVeg)", "Pg C"),
          ("mgpp", "GPP", "Pg C yr$^{-1}$"),
          ("mnpp", "NPP", "Pg C yr$^{-1}$"),
          ("rh", "Heterotrophic respiration (Rh)", "Pg C yr$^{-1}$"),
          ("soilc", "Soil carbon (cSoil)", "Pg C"),
          ("mnbp", "NBP", "Pg C yr$^{-1}$"),
          ("firec", "Fire C emissions (fFire)", "Pg C yr$^{-1}$")]
EXCLUDE = {("VISIT-UT", "firec")}  # VISIT fFire units broken (~600x); see investigation

for exp, longname in EXPS.items():
    fig, axes = plt.subplots(2, 4, figsize=(20, 9))
    lines = {}
    nseries = 0
    for ax, (key, title, unit) in zip(axes.flat, PANELS):
        for m in MODELS:
            if m in EXCLUDE_MODELS or (m, key) in EXCLUDE:
                continue
            csv = SER / f"{exp}__{m}__{key}.csv"
            if not csv.exists():
                continue
            df = pd.read_csv(csv)
            ln, = ax.plot(df["year"], df["value"], color=COLORS[m], lw=1.5, label=m)
            lines[m] = ln
            nseries += 1
        ax.set_title(title, fontsize=11)
        ax.set_ylabel(unit); ax.set_xlabel("Year"); ax.grid(alpha=0.3)
        ax.axhline(0, color="0.6", lw=0.6)
        if key == "firec":
            ax.text(0.5, 0.94, "VISIT-UT excluded (fFire units)", transform=ax.transAxes,
                    ha="center", va="top", fontsize=8, color="0.4")
    if nseries == 0:
        plt.close(fig); print(f"skip {exp} (no data)"); continue
    handles = [lines[m] for m in MODELS if m in lines]
    fig.legend(handles, [h.get_label() for h in handles], loc="upper center",
               ncol=len(handles), bbox_to_anchor=(0.5, 1.015), frameon=False)
    fig.suptitle(f"WIE-MIP 1pctCO2 — global stocks & fluxes — {longname}", y=1.05, fontsize=15)
    fig.tight_layout()
    outf = OUTDIR / f"stocks_fluxes_{exp}_PgC.png"
    fig.savefig(outf, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {outf}  ({nseries} series)")
