# WIE-MIP data processing — working notes

The `wiemip_registry` package turns a standardized WIE-MIP variable request into the
right per-model netCDF file and computes global stocks and fluxes. Every participating
model uploads with its own naming, dims, time encoding, area recipe and fill values, so
each gets a bespoke adapter (`wiemip_registry/<MODEL>/convert.py`) behind one API. For
the project overview (experiments, science goals, drivers) see `CONTEXT.md`.

## Where model knowledge lives

This file holds only the rules that hold across models. How one model is read is in its
adapter code. Every known data defect, open question for a group, and analysis caveat
(exclude it, don't pool it, slice it) is a **`data-quality` issue** on
`WIEMIP/wiemip-data-registry`, one per issue, labelled `model:<KEY>`. Read the open ones
for every model in an analysis before you draw a conclusion from it:
`gh issue list -R WIEMIP/wiemip-data-registry --label data-quality --state open`
(without `gh`: `curl -s 'https://api.github.com/repos/WIEMIP/wiemip-data-registry/issues?labels=data-quality&state=open&per_page=100'`).

Upload history and per-run coverage live in git, the nightly `uncovered` action, and the
progress-tracker page.

## The registry API

```python
import wiemip_registry as wr

f = wr.retrieve_one_pct_variable(
    model="CLM", forcing="ukesm", simulation="cou",
    factorial="baseline", variable="cVeg",
)                        # -> WIEFile (no I/O yet)
f.path                   # resolved path — sanity-check this first
f.exists()               # are all the constructed paths real files?
da = f.read()            # standardized xarray.DataArray, NATIVE units, NaN fills
s  = f.latitudinal_sum()               # global Pg series (cached to CSV)
s_tropics = f.latitudinal_sum(-30, 30) # restrict to a latitude band

o = wr.retrieve_overshoot_variable(    # factorial is optional here
    model="LPX_Bern", forcing="ukesm", simulation="hl", variable="cVeg")

wr.land_carbon_stock("1pctCO2", "CLM", "stable", "bgc")  # sum of land_carbon_variables
```

Requests are validated against the vocabularies at the top level (`wr.models`,
`wr.gcm_patterns`, `wr.one_percent_simulations`, `wr.overshoot_simulations`,
`wr.variables`, `wr.factorials`), built from the enums in `wiemip_registry/const.py`.

- **Model names are the underscored registry keys** (`LPJ_EOSIM`, `LPX_Bern`,
  `VISIT_UT`, `CLM_FATES`), even where the on-disk dirs are hyphenated.
- **bgc / bgc_ndep / ctrl take `forcing="stable"`**: those runs are constant-climate,
  and `core.ensure_valid` raises `InvalidSimulationError` for any other pattern. An
  adapter whose group uploaded them under another token pins that token on disk rather
  than interpolating the requested forcing, or the run is unreachable.
- `land_carbon_stock` sums the adapter's `land_carbon_variables`. When the components
  sit on different time indexes (annual pools beside a monthly one), each is
  annual-meaned and the total takes the coarsest component's stamps.

## Design contract

- **`one_pct_path` / `overshoot_path` are pure token→string transforms**: they spell the
  request in the model's naming convention and never decide what exists. Each model
  spells overshoot differently from its own 1pctCO2 arm, so derive each arm's grammar
  from the real bucket names.
- **`read()` is the existence gate that raises**: a combo that wasn't uploaded raises
  `FileNotFoundError` when opened, so catch on `.read()` / `.latitudinal_sum()`.
- **`exists()` is the non-raising probe**: it returns whether every path is on disk. It
  returns False for a factorial the model doesn't declare and for an arm the adapter
  hasn't mapped, so it is safe across the whole model list.
- **One variable can span several files.** `WIEFile.paths` is the list `read()` opens
  (time chunks, pool splits); `path` is its first entry. The adapter hook is `paths()`.
  Coverage tooling uses `paths`.
- **Provisional data is treated as absent.** An adapter lists `(experiment, variable)`
  pairs a group hasn't QA'd in `PROVISIONAL_DATA`; `exists()` then returns False and
  `read()` / `latitudinal_sum()` raise `core.ProvisionalDataError`, cached CSV included.
- **Factorials are per-model.** Each adapter declares `FACTORIALS` (and
  `OVERSHOOT_FACTORIALS` where the overshoot arm has its own). Common names live in
  `const.Factorial`; model-unique ones (`const.extra_factorials`) pass through as
  strings with a warning.
- **Baseline vs factorial**: a run with no `no<Process>` token is the baseline,
  comparable across models; a `noFire` / `noNitrogen` / … token marks a sensitivity
  run. `_ndep` means N deposition **on**: it is a simulation, not a factorial.
- **Layered soil variables come back on one `soil` axis.** An adapter lists them in
  `LAYERED_VARIABLES`; `WIEFile.read()` renames the one dim beyond (time, lat, lon) to
  `soil` and raises unless it holds strictly increasing **layer-middle depths in m**,
  pinned to float64 at micrometre precision. The adapter's `read()` supplies the depths.
  A model whose depths are unknown stays off the list and keeps its native level dim.
- **Fixed fields** (`sftlf`) are listed in the adapter's `FIXED` and come back as
  `(lat, lon)` with no `time`, in native units (% or fraction), returned before
  `core.standardize`. One raster serves every run, so `exists()` is True even for a run
  that was never uploaded.

## Units and global integrals

- **`const.STOCKS`** is every per-m² amount: carbon pools (kg C m⁻²), nitrogen pools
  (kg N m⁻²), water pools (kg m⁻²). Global total = `Σ(x·area)/PG` → Pg C, Pg N or Gt
  H₂O. Membership follows the `units` of the real uploads, so go by `const.STOCKS`, not
  the name: `nVeg` is a pool but `nbp` a flux, `mrso` an amount but `mrro` a rate.
- **Everything else is a flux** in kg m⁻² s⁻¹: global = `Σ(x·area)·SPY/PG` Pg yr⁻¹, with
  `SPY = 365·86400` because the WIE-MIP drivers are noleap.
- **Intensive variables get the wrong answer from `latitudinal_sum`** (albedo, `lai`,
  `tas`/`soilT`, `wetfrac`, `landCoverFrac`, `burntArea`, `snowDepth`/`wtd`/`alt`, the
  W m⁻² terms): they want an area-weighted mean, which it does not offer. They stay out
  of `STOCKS` on purpose so the result is visibly wrong rather than plausibly wrong.
- `latitudinal_sum` keeps the file's native cadence and converts through the adapter's
  `to_pgc` (default in `core.py`; JULES overrides it for per-year headers).
- `const.ANNUAL` picks the `yr`/`ann` vs `mon` filename token. Where an upload disagrees,
  the adapter carries its own `ANNUAL` / `MONTHLY` sets, and `MONTHLY` is checked first.
- Values below `const.FILL_FLOOR` (−1e3) become NaN. Undeclared positive fills (`1e20`,
  `9.97e36`) are masked by the adapter that meets them.
- Soil CH4 uptake (`fch4soil`) comes back negative. CLASSIC uploads it positive and its
  adapter flips the sign.

## Time

- The `time` coord is `datetime64[us]`: overshoot runs reach 2300 and `[ns]` wraps after
  2262. `core.to_datetime64` casts, cftime included; `cache_csv` re-pins cached indexes.
- An adapter that reads with `decode_times=False` takes the CF epoch from the file with
  `core.cf_reference_month(units)`. 1pctCO2 files and overshoot hist/ctrl count from
  1850, but the overshoot scenarios count from `2024-01-01`.
- Sanity spans: 1pctCO2 runs 1850-2000 (a few stop at 1999); overshoot `hist` and the
  controls 1850-2023, every scenario 2024-2300. A scenario dated 1850-2126 is a
  hardcoded epoch.

## Soil layers and active-layer thickness

`core.calculate_alt(da)` takes a standardized monthly `soilT` (K) and returns the annual
maximum active-layer thickness on a `year` dim. It is `function_alt.py` verbatim, so a
column thawed top to bottom returns the deepest layer's depth, bedrock included. Compare
it with a model's own `alt` at the annual maximum, and only inside permafrost: outside
it each model reports its own column depth, so whole-grid differences mean nothing.

## Paths and the CSV cache

- Files resolve under `const.DATA_ROOT` (`/mnt/wiemip`, env `WIEMIP_DATA_ROOT`) as
  `<experiment>/output/<MODEL>/[<run-subdir>/]<file>.nc`, roughly
  `<model/run tokens>_<VAR>_<cadence>_<grid>[suffix].nc`. Layout is flat (run in the
  filename prefix) or nested (a run sub-dir).
- `latitudinal_sum` caches to `const.CSV_ROOT` (env `WIEMIP_CSV_PATH`), one CSV named
  after `WIEFile.path` and keyed on the newest source mtime across `WIEFile.paths`. It
  recomputes only when a source `.nc` is newer. An adapter, `STOCKS` or units edit does
  not bust it: delete the affected CSVs to force a rebuild.

## Adding or changing a model

1. Copy an existing `wiemip_registry/<MODEL>/` as a template and implement the
   `WIEAdapter` hooks (`one_pct_path`, `read`, `_compute_weights`; override
   `overshoot_path`, `to_pgc` or the cadence sets as needed). Declare `FACTORIALS`.
2. Derive the naming grammar from the real bucket names and let `read()` be the existence
   gate. Register the adapter in `wiemip_registry/adapters.py`.
3. Run the coverage check below and confirm the files you targeted left `uncovered.txt`.
4. Open a `data-quality` issue for each data defect or question for the group.

## Coverage: bucket files no request reaches

`.github/workflows/_uncovered.py` diffs a bucket listing against every path the registry
can spell for a legal request. It needs no `/mnt/wiemip`:

```sh
AWS_PROFILE=wasabi-read-only aws s3 ls s3://wiemip/ --recursive \
    --endpoint-url https://s3.us-east-2.wasabisys.com > /tmp/bucket_listing.txt
uv run python .github/workflows/_uncovered.py /tmp/bucket_listing.txt /nonexistent  # -> ./uncovered.txt
```

Pass an older `uncovered.txt` instead of `/nonexistent` to also get `issue.md` listing
only the new files. The `uncovered` action runs this daily and on pushes touching
`wiemip_registry/**`, and opens an issue whenever new files turn up unreached.

## QA scripts (`debug/`, gitignored)

- `verify_<model>.py`: per-adapter reachability, time-axis and global-integral checks,
  including the groups' own answer keys (DLEM's xlsx, BEPS's csv, CoLM's
  `validation_globals`). Each prints `all checks passed` or the failures.
- `remote_read.py`: read one variable straight off the bucket from a laptop through the
  real adapter, first `REMOTE_STEPS` steps only (netCDF4 files only):
  `uv run --with s3fs --with h5netcdf --with h5py python debug/remote_read.py CLM soilT`.
- `handoff_check/`: each overshoot run's hist 2023 against its first scenario year.
- `regen_land_carbon_stocks.py`: every model × factorial through `land_carbon_stock`,
  resumable.

## Static band aggregations

The latitude-band sweep for the QA site lives in `../wiemip-validation`, a consumer of
this package. An adapter change reaches it only after it is on `main` and deployed.
