# `wiemip_registry` — design plan

> Status: **draft, to refine over the coming days.** Captures the target architecture; see
> `AGENTS.md` for the empirical facts (naming, per-model quirks, units) this is built on.

## Vision

A version-controlled Python package, `wiemip_registry`, that is a **centralized, typed accessor for
every file in the WIE-MIP buckets**. It sits *on top of* the s3 filesystem: the heavy data stays in
s3; the registry is thin code + reference metadata committed to git, updated as new models/runs land.

The headline access pattern is a dotted namespace resolving to a single file wrapper:

```python
import wiemip_registry as wr

# Order: experiment . model . forcing . simulation . factorial . variable  -> WIEFile
f = wr.one_percent_co2.LPX_Bern.ukesm.bgc.baseline.cVeg
ts = f.latitudinal_sum()               # global total time series (Pg C), native cadence
da = f.read()                          # standardized xr.DataArray, but does NOT load into memory, stays lazy
```

- Order: **`experiment.model.forcing.simulation.factorial.variable`** (e.g. `one_percent_co2.CLASSIC.ukesm.cou.noNitrogen.gpp`).
- `experiment` is `one_percent_co2` or `overshoot` (the data dirs `1pctCO2`/`overshoot`; the leading
  digit forces the Python-safe alias `one_percent_co2`).
- `forcing` is a **required** level (no default) — use `ukesm` for cross-model comparability.
- `factorial == baseline` selects the comparable, unperturbed run (per the AGENTS.md rule).
- Resolution is **lazy and name-based**: the Enum axes (experiment/forcing/simulation/factorial) and
  `model` are validated by name as you select them; `variable` is free-form and a non-existent file
  only errors when you call `.read()` (no eager existence scan).

## Core object: `WIEFile`

A thin wrapper over one variable's file(s). Lazy — holds identity + the model's `convert` adapter,
touches s3 only when a method needs data.

```python
class WIEFile:
    model: str          # "LPX-Bern"
    experiment: str     # "one_percent_co2" | "overshoot"
    simulation: str     # "bgc" | "cou" | "rad" | "ctrl"
    forcing: str        # "ukesm" | "gfdl" | "ipsl" — required level (use ukesm for comparability)
    factorial: str      # "baseline" | "noNitrogen" | "noFire" | ...
    variable: str       # CMIP name, e.g. "cVeg"
    kind: str           # "stock" | "flux"
    units: str          # native units from the file
    s3_path: str        # resolved by the model's convert.py

    # --- data access ---
    def read(self) -> xr.DataArray: ...
        # Reads the .nc into a STANDARDIZED form (consistent dim names/order, decoded time->year,
        # fill values -> NaN, units normalized). This is where virtualizarr / kerchunk plug in:
        # read from committed virtual-zarr references rather than re-opening raw netCDF each time.

    def weight_dataarray(self, da: xr.DataArray | None = None) -> xr.core.weighted.DataArrayWeighted: ...
        # Wrap the data in THIS model's documented weights (README recipe) via xarray .weighted():
        # da.weighted(gridcell_area), da.weighted(veg_area) (BiomeE), da.weighted(landfrac*cell) (JULES).
        # Returns a DataArrayWeighted so .sum()/.mean() over (lat,lon) are one call. Farms out to
        # convert.weight_dataarray().

    # --- prebaked aggregations (return tidy time series) ---
    def global_sum(self) -> pd.Series: ...                 # Pg C (stock) / Pg C yr-1 (flux)
    def latitudinal_sum(self, start: float, end: float) -> pd.Series: ...  # band [start,end] deg
    def compute_weighted_aggregation(self, dims=("lat","lon")) -> xr.DataArray: ...
        # generic weighted reduce over arbitrary dims; global_sum is this specialized to (lat,lon)
```

**Compute vs. cache:** prebaked methods (`global_sum`, `latitudinal_sum`, …) **either** compute on the
fly with xarray **or** load a precomputed CSV from the mirror bucket (below), whichever is present.
Computed results can be written back to the cache.

## Per-model adapter: `wiemip_registry/<MODEL>/convert.py`

The bespoke per-model knowledge (we proved a single reader is impossible — see AGENTS.md §3) lives in
one `convert.py` per model, all implementing the **same small API**, with **hardcoded s3fs paths**.

```python
# wiemip_registry/LPX_Bern/convert.py
MODEL = "LPX-Bern"

def s3_path(experiment, simulation, forcing, factorial, variable) -> str:
    """Resolve the hardcoded s3 path for this (experiment, simulation, forcing, factorial, variable)."""

def read(experiment, simulation, forcing, factorial, variable) -> xr.DataArray:
    """Open + STANDARDIZE: rename dims to (time, lat, lon), decode time -> integer year,
       mask fill values, attach units. Returns an unweighted DataArray."""

def weights() -> xr.DataArray:
    """Grid-cell weight [m2] for this model, per its README (provided raster OR computed).
	We can materialize a weights array to disk if used more than once.
    """

def weight_dataarray(da) -> xr.core.weighted.DataArrayWeighted:
    """Apply the model's documented weighting recipe (the thing global_sum sums).
       Returns da.weighted(weights()) — an xarray DataArrayWeighted.
    """
```

The registry's `__init__.py` discovers each `<MODEL>/convert.py`, enumerates available
`(experiment, simulation, forcing, factorial, variable)` tuples, and exposes them through the dotted
namespace as `WIEFile`s backed by that adapter. `extract.py`'s current per-model adapter tables are
the seed for these `convert.py` modules.

## Module / directory layout

```
wiemip_registry/
  __init__.py            # builds the dotted namespace; discovers model adapters; WIEFile factory
  core.py                # WIEFile, shared aggregation logic, cache lookup
                         # (the comparable-run / baseline rule is encoded per-model in each convert.py,
                         #  since paths are hardcoded there — no shared filename parser)
  BiomeE/convert.py
  CLASSIC/convert.py
  DLEM/convert.py
  JSBACH/convert.py
  JULES/convert.py
  LPX_Bern/convert.py
  VISIT_UT/convert.py
  references/            # committed virtualizarr/kerchunk sidecars (small JSON) per file
```

## Precomputed cache: `wiemip-csv` bucket

A new bucket **`wiemip-csv`** mirrors the `wiemip` `.nc` layout **structurally** 1:1 (same dir tree),
though individual filenames differ — each CSV embeds the input's mtime/hash (see cache-invalidation
below). Each entry is the **precomputed aggregation as CSV** (e.g. `global_sum` time series).
`global_sum()` looks here first
(cheap) and falls back to xarray compute (then optionally writes the CSV). The `series/*.csv` that
`extract.py` already emits are the prototype of these cache files.

## Reading & virtualization (virtualizarr / kerchunk)

- Build **virtual-zarr references** over the raw netCDFs and **commit the sidecars** (`references/`).
  Reads then go through a uniform zarr interface — lazy, chunk-aligned, and **usable off the box**
  (from the Mac via s3 creds, not the s3fs mount).
    - The naming convention that the models upload in _does not matter_ because
      the API takes care of selecting the correct file.
    - This logic will take place in s3_path() for each model - not one model
      followed the naming convention exactly.
- `read()` is the single place that maps a model's raw layout onto the **standardized DataArray**
  (canonical dims/order, year coord, NaN fills, units) so everything downstream is uniform.

## Versioning & extensibility

- The package (adapters + naming rules + references + this plan) is **git-versioned**. Adding a model
  = add `<MODEL>/convert.py` + its references; the namespace picks it up automatically.
- Pin/record the bucket state the references were built against, so a registry version maps to a
  known data snapshot.

## Open questions (refine later)

- `factorial` taxonomy: how to name multi-factor combos (e.g. JULES `addPermafrostCN`, `Fire0249`)
  and how `baseline` maps per model (DLEM baseline includes `ndep`; JULES baseline is `Nitrogen_DynVeg_Permafrost_noFire`).
    - These questions MUST be resolved by examining the data and making informed
      choices. In an ideal world, each model has its own set of factorials
      defined by what they've actually run:
      one_percent_co2.cou.JULES.ukesm.addPermafrostCN.cVeg, where the description of the
      factorial is accessible via shift-K or whatever pulls up the docstring
- ~~`forcing` placement in the namespace~~ — RESOLVED: `forcing` is a required namespace level,
  positioned `…model.forcing.factorial…`. No default; use `ukesm` for comparability.
- Whether `read()` returns a `DataArray` (one var) or a `Dataset` (var + weights + bounds).
    - DataArray, since each file is single-variable-per-file
- Cache invalidation between `wiemip` and `wiemip-csv` (checksum / mtime / registry version).
    - .csv stores mod time/hash of input file in its name, constructed at
      runtime by the reading code - if computing the hash of input file
      expensive, then just use mtime. I'm not up-to-date on the specifics of how
      hashes are computed across large .nc files.
- Handling flagged-bad data in the API (e.g. VISIT-UT `fFire`) — raise, warn, or mask?
    - Do nothing - expect outputs to be perfect, it's up to the user to email
      and debug bad files

## Decisions log (resolved)

Folded into the body above; kept here for rationale/traceability.

- **Namespace order:** `experiment.simulation.model.forcing.factorial.variable` (6 levels).
- **Experiment alias:** `1pctCO2` dir → Python-safe `one_percent_co2`; `overshoot` unchanged.
- **`forcing` is a required level** (not optional, no UKESM default) — use `ukesm` for comparability.
- **Adapter signatures** take `(experiment, simulation, forcing, factorial, variable)` (model is the module).
- **Terminology:** `experiment` = `one_percent_co2`/`overshoot`; `simulation` = `bgc`/`cou`/`rad`/`ctrl`.
  `AGENTS.md` updated to match (its old `scenario` → `experiment`, old run-type `experiment` → `simulation`).
- **`baseline`** is the one token for the comparable unperturbed run (never `base`).
- **Weighting** uses xarray `.weighted()` (returns `DataArrayWeighted`) so `global_sum`/`mean` are one
  call; `convert.weight_dataarray()` is the adapter hook.
- **Namespace misses = missing files** (model exists, that combo doesn't) → clear error listing what's
  available at that level.
- **`naming.py` dropped** — paths are hardcoded per model in `s3_path()`, so there's no shared parser.

## Still to confirm

- **`naming.py` removal in `AGENTS.md`.** Removed `naming.py` from this plan. Your note said "drop
  this from agents.md and this plan" — but `AGENTS.md §2` is the empirical *naming-conventions /
  comparable-run* reference (facts the adapters are built from), not a description of `naming.py`. Left
  §2 intact. Confirm whether you also want §2 itself trimmed.
- **"Normalize to the dot notation" for `s3_uri`/`units`.** Renamed the attr `s3_uri` → `s3_path` (to
  match the adapter). Left `units` as "native units from the file." Unclear what "dot notation" meant
  for units — confirm if you wanted units normalized to something specific.
