# One 8-panel figure per (simulation, factorial). Solid = factorial run; dashed (same colour) =
# that model's baseline for the SAME simulation, so the factorial's effect is readable.
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

FAC    = Path("/tmp/wiemip/series_fac")   # factorial runs: <sim>__<fac>__<model>__<req>.csv
BASE   = Path("/tmp/wiemip/series")       # baseline runs:  <sim>__<model>__<req>.csv
OUTDIR = Path("/tmp/wiemip")
MODELS = ["BiomeE", "CLASSIC", "DLEM", "JSBACH", "JULES", "LPX-Bern", "VISIT-UT"]
COLORS = {m: c for m, c in zip(MODELS, plt.cm.tab10.colors)}
SIMS = {"bgc": "BGC", "cou": "COU (UKESM-forced)"}
FACTORIALS = {"noNitrogen": "no nitrogen limitation",
              "noFire": "fire disabled",
              "noPermafrost": "permafrost disabled",
              "noBVOC": "BVOC disabled"}
PANELS = [("litc", "Litter carbon (cLitter)", "Pg C"),
          ("vegc", "Vegetation carbon (cVeg)", "Pg C"),
          ("mgpp", "GPP", "Pg C yr$^{-1}$"),
          ("mnpp", "NPP", "Pg C yr$^{-1}$"),
          ("rh", "Heterotrophic respiration (Rh)", "Pg C yr$^{-1}$"),
          ("soilc", "Soil carbon (cSoil)", "Pg C"),
          ("mnbp", "NBP", "Pg C yr$^{-1}$"),
          ("firec", "Fire C emissions (fFire)", "Pg C yr$^{-1}$")]
EXCLUDE = {("VISIT-UT", "firec")}

for sim, simlong in SIMS.items():
    for fac, longname in FACTORIALS.items():
        present = sorted({p.name.split("__")[2] for p in FAC.glob(f"{sim}__{fac}__*.csv")},
                         key=MODELS.index)
        if not present:
            print(f"skip {sim} {fac} (no runs)"); continue
        fig, axes = plt.subplots(2, 4, figsize=(20, 9))
        for ax, (key, title, unit) in zip(axes.flat, PANELS):
            for m in present:
                if (m, key) in EXCLUDE:
                    continue
                fcsv = FAC / f"{sim}__{fac}__{m}__{key}.csv"
                if not fcsv.exists():
                    continue
                df = pd.read_csv(fcsv)
                ax.plot(df["year"], df["value"], color=COLORS[m], lw=1.7)             # factorial: solid
                bcsv = BASE / f"{sim}__{m}__{key}.csv"
                if bcsv.exists():
                    b = pd.read_csv(bcsv)
                    ax.plot(b["year"], b["value"], color=COLORS[m], lw=1.1, ls="--", alpha=0.6)  # baseline
            ax.set_title(title, fontsize=11)
            ax.set_ylabel(unit); ax.set_xlabel("Year"); ax.grid(alpha=0.3)
            ax.axhline(0, color="0.6", lw=0.6)
            if key == "firec" and "VISIT-UT" in present:
                ax.text(0.5, 0.94, "VISIT-UT excluded (fFire units)", transform=ax.transAxes,
                        ha="center", va="top", fontsize=8, color="0.4")
        handles = [Line2D([0], [0], color=COLORS[m], lw=2, label=m) for m in present]
        handles += [Line2D([0], [0], color="0.3", lw=2, ls="-", label="factorial run"),
                    Line2D([0], [0], color="0.3", lw=1.1, ls="--", label=f"{sim} baseline")]
        fig.legend(handles, [h.get_label() for h in handles], loc="upper center",
                   ncol=len(handles), bbox_to_anchor=(0.5, 1.015), frameon=False)
        fig.suptitle(f"WIE-MIP 1pctCO2 — {simlong} factorial: {fac} ({longname})  —  solid=factorial, dashed=baseline",
                     y=1.05, fontsize=14)
        fig.tight_layout()
        outf = OUTDIR / f"factorial_{sim}_{fac}_PgC.png"
        fig.savefig(outf, dpi=140, bbox_inches="tight")
        plt.close(fig)
        print(f"wrote {outf}  (models: {', '.join(present)})")
