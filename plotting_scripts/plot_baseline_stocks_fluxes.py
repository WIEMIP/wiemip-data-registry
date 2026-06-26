# One multi-panel figure of the main global stocks & fluxes for the baseline run,
# one line per model, built on the wiemip_registry API (latitudinal_sum() already
# area-weights and converts to Pg C / Pg C yr^-1). Runs on the ubuntu box.
from pathlib import Path
import functools

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import wiemip_registry as wr


def resolve(experiment, model, forcing, simulation, factorial, variable):
    """Dotted-namespace walk from string axis names to a WIEFile (lazy; no S3)."""
    axes = [experiment, model, forcing, simulation, factorial, variable]
    return functools.reduce(getattr, axes, wr)


if __name__ == "__main__":
    # --- edit me ---
    outdir     = Path("/tmp/wiemip/baseline_stocks_fluxes")
    experiment = "one_percent_co2"
    simulation = "bgc"          # the comparable baseline carbon-cycle run (cou/rad/ctrl are variants)
    forcing    = "ukesm"        # used by cou/rad; ignored by bgc/ctrl
    factorial  = "baseline"
    models     = wr.models
    panels = [
        ("cVeg",    "Vegetation C (cVeg)",      "Pg C"),
        ("cLitter", "Litter C (cLitter)",       "Pg C"),
        ("cSoil",   "Soil C (cSoil)",           "Pg C"),
        ("gpp",     "GPP",                       "Pg C yr$^{-1}$"),
        ("npp",     "NPP",                       "Pg C yr$^{-1}$"),
        ("ra",      "Autotrophic resp (ra)",    "Pg C yr$^{-1}$"),
        ("rh",      "Heterotrophic resp (rh)",  "Pg C yr$^{-1}$"),
        ("nbp",     "NBP",                       "Pg C yr$^{-1}$"),
        ("fFire",   "Fire C emissions (fFire)", "Pg C yr$^{-1}$"),
    ]
    exclude = {("VISIT_UT", "fFire")}   # VISIT-UT fFire units broken (~600x); see AGENTS.md §5
    nrows, ncols = 3, 3
    # ---------------

    outdir.mkdir(parents=True, exist_ok=True)
    seriesdir = outdir / "series"
    seriesdir.mkdir(exist_ok=True)
    colors = {m: c for m, c in zip(models, plt.cm.tab10.colors)}

    plot_path = outdir / f"baseline_{simulation}_stocks_fluxes.png"
    if plot_path.exists():
        print(f"skip {plot_path} (rm to redraw)")
    else:
        fig, axes = plt.subplots(nrows, ncols, figsize=(18, 12))
        handles = {}
        for ax, (variable, title, unit) in zip(axes.flat, panels):
            for model in models:
                if (model, variable) in exclude:
                    continue
                csv_path = seriesdir / f"{model}__{variable}.csv"
                if csv_path.exists():
                    annual = pd.read_csv(csv_path, index_col=0).squeeze("columns")
                else:
                    try:
                        s = resolve(experiment, model, forcing, simulation,
                                    factorial, variable).latitudinal_sum()
                    except Exception:
                        continue                       # combo not submitted by this model
                    annual = s.groupby(s.index.year).mean()   # monthly fluxes -> annual mean
                    annual.to_csv(csv_path)
                line, = ax.plot(annual.index, annual.values, lw=1.5,
                                color=colors[model], label=model)
                handles[model] = line
            ax.set_title(title, fontsize=11)
            ax.set_ylabel(unit)
            ax.set_xlabel("Year")
            ax.grid(alpha=0.3)
            ax.axhline(0, color="0.7", lw=0.6)

        ordered = [handles[m] for m in models if m in handles]
        fig.legend(ordered, [h.get_label() for h in ordered], loc="upper center",
                   ncol=len(ordered), frameon=False, bbox_to_anchor=(0.5, 1.0))
        fig.suptitle(
            f"WIE-MIP {experiment} — global stocks & fluxes — {simulation} baseline",
            y=1.02, fontsize=15)
        fig.tight_layout()
        fig.savefig(plot_path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        print(f"wrote {plot_path}  ({len(ordered)} models)")
