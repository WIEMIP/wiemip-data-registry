# Cumulative land C uptake = running sum of annual NBP (Pg C). One panel per simulation
# (BGC / COU / CTRL), one line per model. The CTRL/piControl panel exposes model drift.
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
SIMS = [("bgc", "BGC (biogeochem-coupled)"),
        ("cou", "COU (fully coupled, UKESM)"),
        ("ctrl", "CTRL / piControl  —  drift check")]
COMMON_LAST_YEAR = 1999   # all models cover 1850-1999; clip so cumulative NBP is comparable

fig, axes = plt.subplots(1, 3, figsize=(19, 6), sharex=True)
lines = {}
for ax, (sim, longname) in zip(axes, SIMS):
    n = 0
    for m in MODELS:
        if m in EXCLUDE_MODELS:
            continue
        csv = SER / f"{sim}__{m}__mnbp.csv"
        if not csv.exists():
            continue
        df = pd.read_csv(csv).sort_values("year")
        df = df[df["year"] <= COMMON_LAST_YEAR]      # common window -> cumulative is comparable
        cum = df["value"].cumsum()
        cum = cum - cum.iloc[0]                      # anchor cumulative uptake to 0 at first year
        ln, = ax.plot(df["year"], cum, color=COLORS[m], lw=1.8, label=m)
        lines[m] = ln
        n += 1
    ax.set_title(longname, fontsize=11)
    ax.set_xlabel("Year")
    ax.set_ylabel("Cumulative NBP (Pg C)")
    ax.grid(alpha=0.3)
    ax.axhline(0, color="0.6", lw=0.6)
    if sim == "ctrl":
        ax.set_ylim(-600, 800)   # match forced-run scale -> drift reads as ~flat (per Vivek's deck)

handles = [lines[m] for m in MODELS if m in lines]
fig.legend(handles, [h.get_label() for h in handles], loc="upper center",
           ncol=len(handles), bbox_to_anchor=(0.5, 1.04), frameon=False)
fig.suptitle("WIE-MIP 1pctCO2 — cumulative land carbon uptake (cumulative NBP)", y=1.10, fontsize=14)
fig.tight_layout()
outf = OUTDIR / "cumulative_nbp_PgC.png"
fig.savefig(outf, dpi=140, bbox_inches="tight")
print(f"wrote {outf}")
