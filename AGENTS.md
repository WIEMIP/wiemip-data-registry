# WIE-MIP data processing — working notes

Reference for the `wiemip_registry` package: it turns a standardized WIE-MIP variable
request into the right per-model netCDF file and computes global stocks & fluxes. Every
participating model uploads with its own naming convention, dims, time encoding, area
recipe and fill values, so each gets a bespoke adapter behind one API. For the
project-level overview (experiments, science goals, drivers) see `CONTEXT.md`.

## The registry API

```python
import wiemip_registry as wr
import wiemip_registry.const as const

f = wr.retrieve_one_pct_variable(
    model="CLASSIC", forcing="ukesm", simulation="cou",
    factorial="baseline", variable="cVeg",
)                        # -> WIEFile (no I/O yet)
f.path                   # resolved path — sanity-check this first
f.exists()               # is the constructed path a real file?
da = f.read()            # standardized xarray.DataArray, NATIVE units, NaN fills
s  = f.latitudinal_sum()               # global Pg C series (cached to CSV)
s_tropics = f.latitudinal_sum(-30, 30) # restrict to a latitude band

o = wr.retrieve_overshoot_variable(    # overshoot has no factorial axis
    model="LPX_Bern", forcing="ukesm", simulation="hl", variable="cVeg")
```

Requests are validated against the vocabularies exported at the top level (`wr.models`,
`wr.gcm_patterns`, `wr.one_percent_simulations`, `wr.overshoot_simulations`,
`wr.variables`, `wr.factorials`), built from the enums in `wiemip_registry/const.py`:

- `GCMPattern`: ukesm / ipsl / gfdl / stable
- `OnePctSimulation`: bgc / cou / ctrl / rad, each with an `_ndep` variant
- `OvershootSimulation`: hist / hist_ctrl / ctrl / vl / vl_cf / l / hl / hl_cf / m
- `Factorial`: baseline / noFire / noNitrogen / noPermafrost / noFire_noNitrogen /
  noFire_noPermafrost / noBVOC (model-unique names in `extra_factorials`)

**Model names are the underscored registry keys** (`LPJ_EOSIM`, `LPX_Bern`, `VISIT_UT`,
`CLM_FATES`) even though the on-disk dirs are hyphenated. Pass the underscore form to
`retrieve_*`.

### Design contract
- Each adapter's `one_pct_path` / `overshoot_path` is a **pure token→string transform**:
  it spells the request into that model's naming convention and never decides what exists.
- `read()` is the **only existence gate**: a combo that wasn't uploaded raises
  `FileNotFoundError` when opened, not at selection time — so be ready to catch on
  `.read()` / `.latitudinal_sum()`.
- **Factorials are per-model.** Each adapter declares a `FACTORIALS` dict; the namespace
  validates the factorial against the chosen model's keys. Common names live in
  `const.Factorial`; model-unique ones (`const.extra_factorials`: JULES config strings,
  LPX permafrost, fire param sweeps) pass through as plain strings (warn, still resolve).
- **Baseline vs factorial:** a run/file with no `no<Process>` token is the baseline
  (comparable across models); a `_noFire`/`noNitrogen`/… token marks a sensitivity run.
  `_ndep` means N-deposition **on** — a simulation, not a "no" factorial.

### Units & global integral
- `const.STOCKS` (cVeg/cSoil/cLitter/cWood/cLeaf/cRoot/cCwd) are `kg C m⁻²`; global stock
  = `Σ(x·area)/1e12` Pg C.
- Everything else is a flux `kg C m⁻² s⁻¹`; global flux = `Σ(x·area)·SPY/1e12` Pg C yr⁻¹
  (`SPY = 365.25·86400`, `PG = 1e12`).
- `latitudinal_sum()` keeps the file's native cadence (monthly stays monthly) and
  converts via the adapter's `to_pgc` (default in `core.py`; no adapter overrides it).
  `const.ANNUAL` picks the `yr`/`ann` vs `mon` filename token, independent of stock/flux
  (N pools and per-PFT carbon are annual but not stocks).
- Fills below `const.FILL_FLOOR = -1e3` (BiomeE −1e5, JULES −9999, stray −99999) → NaN.

### Paths & CSV cache
- Files resolve under `const.DATA_ROOT` (`/mnt/wiemip`) as
  `<experiment>/output/<MODEL>/[<run-subdir>/]<file>.nc` — **one variable per file**.
- `latitudinal_sum` caches its Pg C series to `const.CSV_ROOT` (override with the
  `WIEMIP_CSV_PATH` env var), keyed on the source `.nc` mtime — recomputes only when the
  CSV is missing or older than the source. Note: an *adapter code* edit does NOT bust the
  cache (the key is the `.nc`); delete the CSV to force a rebuild.

## Data layout & naming

Layout is either **flat** (run encoded in the filename prefix) or **nested** (a run
sub-directory). Filenames are roughly `<model/run tokens>_<VAR>_<cadence>_<grid>[suffix].nc`
(`cadence` = `yr`/`ann` or `mon`; `grid` = `05` for 0.5°, `1`/`1deg` for 1°, `n96` for
JULES). Some `<MODEL>` dirs are empty placeholders for groups that haven't submitted.

## Per-model adapters — why each is bespoke

No single reader works: coord names, time encoding, area weighting, fill values,
factorial grammar and which variables exist all vary. Each lives in
`wiemip_registry/<MODEL>/convert.py`.

| model (key) | grid / coords | time decode | area weight | layout & factorials | notable gotchas |
|---|---|---|---|---|---|
| **BiomeE** | 0.5°, `lat`/`lon` | datetime | provided `veg_area.nc` | flat; baseline only | −1e5 fill; first valid yr 1851 |
| **CLASSIC** | 1°, `latitude`/`longitude` | datetime | spherical × `sftlf` landfrac raster | nested; baseline/noFire/noNitrogen(+`-Ndep`), `post` token suffixes dir **and** trails cadence | var-name casing map (`fN2OFire→fN2oFire`…); `cVegpft` monthly; `overshoot` stub returns `"null"` |
| **CLM_FATES** | `lat`/`lon` | datetime | computed spherical | flat; baseline only | filename needs `vegtype`+`level` tokens; `read()` divides `fN2O`/`wetCH4` by 1000 (g→kg); `wetfrac` monthly |
| **DLEM** | 0.5°, `lat`/`lon`, lat truncated | `decode_times=False`, "months/years since 1850" by hand | computed spherical | nested; baseline maps to curated `_ndep` dirs | no `fFire`; `nbp`=0 in 1850 |
| **JSBACH** | 1°, `lat`/`lon` | datetime | computed spherical | nested; baseline/noNitrogen `post` suffix | fire ≈ 0 (off in this run); **overshoot implemented** |
| **JULES** ⚠️ | n96, `latitude`/`longitude` | datetime (ignores `year` coord) | spherical × `landfrac_n96.nc` (`land`>1→0) | nested; **factorials are positional config strings** (`Nitrogen_DynVeg_Permafrost_noFire`…) baked into dir+file | **always annual** (`yr` hardcoded); `ctrl`→`ctl`; limited var set |
| **LPJ_EOSIM** | 0.5°, `latitude`/`longitude` | datetime (gregorian days-since-1850) | computed spherical | nested; baseline/`_noFire` suffix on dir+file | dir hyphenated `LPJ-EOSIM`, prefix underscored `LPJ_EOSIM`; partial upload, expanding |
| **LPJmL6** | `latitude`/`longitude` | datetime | computed spherical | nested; baseline only | `alt`/`fNHarvest` forced annual; `overshoot` stub returns `"null"` |
| **LPX_Bern** ⚠️ | 1°, `latitude`/`longitude` | `decode_times=False`, numeric years → floor (`years_to_datetime`) | provided `gridcell_area.nc` | flat; **factorials are (prefix,suffix) pairs** — lowercase `nofire`/`nopermafrost` **before** the sim token, suffix after | high fire (~15–23 Pg C/yr) but **real**; **overshoot implemented** |
| **TEM** | 0.5°, `latitude`/`longitude`, dims `(lon,lat,time)` | `decode_times=False`, noleap days-since-1850 by hand | computed spherical | nested, run dir = `SIM.upper()`; baseline only | file prefix `TEM-MDM`; `nbp` sign/units look off |
| **VISIT_UT** | 0.5°, `lat`/`lon` | `decode_times=False`, "years since AD 0" fractional → floor | computed spherical | nested; baseline/noBVOC/noFire `post` suffix | **always monthly** (`mon` hardcoded); `fFire` mis-scaled — adapter warns; **overshoot implemented** |

`overshoot_path` is a real implementation for **JSBACH, LPX_Bern, VISIT_UT**; a `"null"`
stub (resolves then fails at `read()`) for **CLASSIC, LPJmL6**; and unimplemented (base
`NotImplementedError`) for the rest.

## Known data-quality flags

- **VISIT-UT `fFire`** mis-scaled (~1000× / a g→kg slip; the adapter emits a runtime
  warning). **Exclude** from fire analyses — flag to Akihiko Ito.
- **LPX-Bern `fFire`** ~15–23 Pg C/yr (≈8× others) — high but a real model result.
- **JSBACH `fFire`** ≈ 0 (fire effectively off in this run).
- **DLEM** has no `fFire`; `nbp` is 0 in 1850 then nonzero.
- **TEM `nbp`** sign/units look off (persistent ~−10 Pg C/yr source while cVeg+cSoil
  rise) — flag to the TEM group.

## Adding a model

Copy an existing `wiemip_registry/<MODEL>/` directory as a template, implement the
`WIEAdapter` hooks (`one_pct_path`, `read`, `_compute_weights`; override
`overshoot_path` / `to_pgc` / cadence handling as needed), declare its `FACTORIALS`, and
register it in `wiemip_registry/adapters.py`. Derive the naming grammar from the real
bucket dir/file names and let `read()` be the existence gate — don't hardcode which
combos exist. `README.md` has a worked example.

## Dev / QA harnesses (`debug/`)

Run against a machine that has the model-output bucket available at `const.DATA_ROOT`:

- **`test_wr.py`** — stress-tests the reader over the full namespace product; reports
  on-disk files no request combo can reach (naming coverage) and reads/plots the carbon
  set. `qa.sh [coverage|uncovered|reads] [MODEL]` is a convenience driver.
- **`test_factorials.py`** — factorial-axis coverage/accessibility, through the public
  API. `qa_factorials.sh [coverage|reads|plots|all] [MODEL]` drives it.
