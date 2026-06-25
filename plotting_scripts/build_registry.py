# Build a registry of every WIE-MIP output file, across scenarios, from RUNTIME values.
# For each .nc: open it (header only), read the actual variable / units / dims / grid / time
# from the file, and parse the path+filename into run / experiment / forcing / factorial tags.
#
# Runs on the ubuntu box where the s3fs bucket is mounted at /mnt/wiemip.
# Usage:  python build_registry.py [out.csv]
from __future__ import annotations
import csv
import re
import sys
import time
from pathlib import Path

import xarray as xr

ROOT      = Path("/mnt/wiemip")
SCENARIOS = ["1pctCO2", "overshoot"]
OUT       = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("registry.csv")

ESMS = ["ukesm", "gfdl", "ipsl"]
BNDS = {"time_bnds", "time_bounds", "lat_bnds", "lon_bnds",
        "latitude_bnds", "longitude_bnds", "bnds"}

# Factorial / perturbation markers. A run carrying ANY of these is NOT a "comparable" raw run.
# Case-insensitive. Covers: noNitrogen/noFire/noPermafrost/noBVOC/noNdep/noDynVeg,
# addPermafrostC[N][Ninorg], removePermafrostC[N][Ninorg], Fire#### parameter sweeps,
# and LPX's lowercase nofire/nopermafrost dir prefixes.
FACT_RE = re.compile(
    r"(nonitrogen|nofire|nopermafrost|nobvoc|nondep|nodynveg"
    r"|addpermafrost(?:cnninorg|cn|c)?|removepermafrost(?:cnninorg|cn|c)?"
    r"|fire\d{3,4})", re.I)
NDEP_RE = re.compile(r"(?<!no)(?:_|-)ndep(?:_|\.|$)", re.I)


def parse_name(model: str, run: str, fname: str) -> dict:
    s = f"{run}/{fname}"
    low = s.lower()
    forcing = next((e for e in ESMS if e in low), "")
    if any(k in low for k in ("picontrol", "control", "ctrl", "stable")):
        exp = "control"
    elif "bgc" in low:
        exp = "BGC"
    elif "cou" in low:
        exp = "COU"
    elif "rad" in low:
        exp = "RAD"
    else:
        exp = ""
    facts = sorted({m.group(0).lower() for m in FACT_RE.finditer(s)})
    ndep = bool(NDEP_RE.search(low))
    return dict(forcing=forcing, experiment=exp, ndep=ndep,
                factorials=";".join(facts), is_comparable=(len(facts) == 0))


def file_meta(path: Path) -> dict:
    try:
        ds = xr.open_dataset(path, decode_times=False)
    except Exception as e:
        return dict(variable="OPEN_ERROR", units=repr(e)[:120])
    try:
        dvars = [v for v in ds.data_vars if v not in BNDS]
        var = dvars[0] if dvars else ""
        a = ds[var].attrs if var else {}
        latn = next((c for c in ds.variables if c.lower() in ("lat", "latitude")), "")
        lonn = next((c for c in ds.variables if c.lower() in ("lon", "longitude")), "")
        nt = int(ds.sizes.get("time", 0))
        tcoord = ds["time"].values if ("time" in ds and nt) else None
        return dict(
            variable=var,
            units=a.get("units", ""),
            long_name=a.get("long_name", a.get("standard_name", "")),
            dims="|".join(ds[var].dims) if var else "",
            nlat=int(ds.sizes.get(latn, 0)) if latn else "",
            nlon=int(ds.sizes.get(lonn, 0)) if lonn else "",
            ntime=nt,
            time_units=ds["time"].attrs.get("units", "") if "time" in ds else "",
            time_first=float(tcoord[0]) if tcoord is not None else "",
            time_last=float(tcoord[-1]) if tcoord is not None else "",
        )
    finally:
        ds.close()


COLS = ["scenario", "model", "run", "experiment", "forcing", "ndep", "factorials",
        "is_comparable", "variable", "units", "cadence", "grid", "nlat", "nlon",
        "ntime", "time_units", "time_first", "time_last", "long_name", "dims", "file", "path"]


def main() -> None:
    rows = []
    t0 = time.time()
    for scen in SCENARIOS:
        base = ROOT / scen / "output"
        if not base.exists():
            print(f"skip {scen} (no output dir)"); continue
        files = sorted(base.rglob("*.nc"))
        print(f"{scen}: {len(files)} files")
        for i, f in enumerate(files, 1):
            rel = f.relative_to(base)
            model = rel.parts[0]
            run = "/".join(rel.parts[1:-1])
            fname = f.name
            cad = next((c for c in ("day", "mon", "ann", "yr")
                        if re.search(rf"_{c}(_|\.|$)", fname)), "")
            grid = next((g for g in ("n96", "1deg", "05", "1")
                         if re.search(rf"_{g}(_|\.|$)", fname)), "")
            row = dict(scenario=scen, model=model, run=run, file=fname,
                       cadence=cad, grid=grid, path=str(f))
            row.update(parse_name(model, run, fname))
            row.update(file_meta(f))
            rows.append(row)
            if i % 100 == 0:
                print(f"  {scen} {i}/{len(files)}  ({time.time()-t0:.0f}s)", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLS})
    print(f"wrote {OUT}  rows={len(rows)}  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
