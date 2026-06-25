# Pool CHANGES (anomalies vs first year) — per C4MIP, the response to forcing is more comparable
# across models than the absolute pre-industrial state. One figure per simulation:
#   ΔcVeg, ΔcSoil, ΔcLitter, and cumulative NBP (land C uptake), one line per model.
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
SIMS = {"bgc": "BGC (biogeochem-coupled)",
        "cou": "COU (fully coupled, UKESM)",
        "ctrl": "CTRL / piControl"}
COMMON_LAST_YEAR = 1999   # clip to the window all models cover, for comparable changes
# (key, title, mode): mode "anom" = value - value[0]; "cum" = cumulative sum anchored to 0
PANELS = [("vegc",  "Δ Vegetation carbon (cVeg)", "anom"),
          ("soilc", "Δ Soil carbon (cSoil)",      "anom"),
          ("litc",  "Δ Litter carbon (cLitter)",  "anom"),
          ("mnbp",  "Cumulative NBP (land C uptake)", "cum")]

for sim, longname in SIMS.items():
    fig, axes = plt.subplots(1, 4, figsize=(22, 5.6))
    lines = {}
    nseries = 0
    for ax, (key, title, mode) in zip(axes, PANELS):
        for m in MODELS:
            if m in EXCLUDE_MODELS:
                continue
            csv = SER / f"{sim}__{m}__{key}.csv"
            if not csv.exists():
                continue
            df = pd.read_csv(csv).sort_values("year")
            df = df[df["year"] <= COMMON_LAST_YEAR]
            if mode == "cum":
                y = df["value"].cumsum()
                y = y - y.iloc[0]
            else:
                y = df["value"] - df["value"].iloc[0]
            ln, = ax.plot(df["year"], y, color=COLORS[m], lw=1.7, label=m)
            lines[m] = ln
            nseries += 1
        ax.set_title(title, fontsize=11)
        ax.set_ylabel("Pg C (relative to first year)")
        ax.set_xlabel("Year")
        ax.grid(alpha=0.3)
        ax.axhline(0, color="0.6", lw=0.6)
    if nseries == 0:
        plt.close(fig); print(f"skip {sim} (no data)"); continue
    handles = [lines[m] for m in MODELS if m in lines]
    fig.legend(handles, [h.get_label() for h in handles], loc="upper center",
               ncol=len(handles), bbox_to_anchor=(0.5, 1.02), frameon=False)
    fig.suptitle(f"WIE-MIP 1pctCO2 — {longname} — pool changes & cumulative uptake "
                 f"(anomalies vs first year)", y=1.06, fontsize=14)
    fig.tight_layout()
    outf = OUTDIR / f"pool_change_{sim}_PgC.png"
    fig.savefig(outf, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {outf}")
