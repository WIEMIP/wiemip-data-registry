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

o = wr.retrieve_overshoot_variable(    # factorial is optional here (JULES-only)
    model="LPX_Bern", forcing="ukesm", simulation="hl", variable="cVeg")

j = wr.retrieve_overshoot_variable(    # JULES ran the scenarios under 5 fire configs
    model="JULES", forcing="ukesm", simulation="hl", variable="cVeg",
    factorial="Fire0005")
```

Requests are validated against the vocabularies exported at the top level (`wr.models`,
`wr.gcm_patterns`, `wr.one_percent_simulations`, `wr.overshoot_simulations`,
`wr.variables`, `wr.factorials`), built from the enums in `wiemip_registry/const.py`:

- `GCMPattern`: ukesm / ipsl / gfdl / stable
- `OnePctSimulation`: bgc / cou / ctrl / rad, each with an `_ndep` variant
- `OvershootSimulation`: hist / hist_ctrl / ctrl / vl / vl_cf / l / hl / hl_cf / m /
  ml / ml_cf (ml/ml_cf aren't protocol-required, but driver data was provided and
  LPX_Bern + VISIT_UT submitted them)
- **bgc / bgc_ndep / ctrl must be requested with `forcing="stable"`** — those runs are
  constant-climate, and `core.ensure_valid` raises `InvalidSimulationError` for any
  other pattern. Adapters must therefore pin whatever token those files were actually
  uploaded under (CLM uses `ukesm` on disk) rather than interpolate the requested
  forcing, or the run is unreachable through the public API. (BiomeE went the other
  way: its adapter spells `stable` by agreement, and the ukesm-labelled files wait
  unreachable for the re-upload — see its row below.)
- `Factorial`: baseline / noFire / noNitrogen / noPermafrost / noFire_noNitrogen /
  noFire_noPermafrost / noBVOC (model-unique names in `extra_factorials`)

**Model names are the underscored registry keys** (`LPJ_EOSIM`, `LPX_Bern`, `VISIT_UT`,
`CLM_FATES`) even though the on-disk dirs are hyphenated. Pass the underscore form to
`retrieve_*`.

### Design contract
- Each adapter's `one_pct_path` / `overshoot_path` is a **pure token→string transform**:
  it spells the request into that model's naming convention and never decides what exists.
- `read()` is the **existence gate that raises**: a combo that wasn't uploaded raises
  `FileNotFoundError` when opened, not at selection time — so be ready to catch on
  `.read()` / `.latitudinal_sum()`.
- **One variable can span several files.** `WIEFile.paths` is the list `read()` opens and
  `path` is its first entry; the adapter hook is `paths()`, which defaults to `[path()]`.
  Only CLM's overshoot upload needs it (time-chunked runs), but coverage tooling should
  use `paths` so every chunk counts as reached.
- `exists()` is the **non-raising probe**: it spells the paths the same way `path()` does
  and returns whether they are all actually on disk (`os.path.isfile`), so you can
  pre-filter a request set without wrapping every combo in `try`/`except`. A factorial the
  chosen model doesn't declare returns `False` (it swallows `MissingFactorialError`), and so
  does a model whose overshoot naming isn't mapped yet (`NotImplementedError`) — `exists()`
  is safe to call across the whole model list for either experiment. Use it to check before
  reading; `read()` stays the gate that raises.
- **Factorials are per-model.** Each adapter declares a `FACTORIALS` dict; the namespace
  validates the factorial against the chosen model's keys. Common names live in
  `const.Factorial`; model-unique ones (`const.extra_factorials`: JULES config strings,
  LPX permafrost, fire param sweeps) pass through as plain strings (warn, still resolve).
- **Baseline vs factorial:** a run/file with no `no<Process>` token is the baseline
  (comparable across models); a `_noFire`/`noNitrogen`/… token marks a sensitivity run.
  `_ndep` means N-deposition **on** — a simulation, not a "no" factorial.

### Units & global integral
- `const.STOCKS` is every per-m² **amount**: the carbon pools (`kg C m⁻²`), the nitrogen
  pools (`kg N m⁻²`) and the water pools (`mrso`/`mrsoLayer`/`swe`/`soilMoist`/`soilIce`,
  `kg m⁻²`). Global total = `Σ(x·area)/1e12` → Pg C, Pg N or Gt H₂O; `PG = 1e12` is a
  kg→Pg factor and carries no species. Membership was set from the `units` attribute of
  the real uploads (one file per model × variable), so **don't go by the name**: `nVeg`/
  `nSoil` are nitrogen pools while `nbp`/`npp` are carbon fluxes, and `mrso` (soil
  moisture, an amount) sits next to `mrro` (runoff, a rate).
- Everything else falls through to the flux branch `kg m⁻² s⁻¹`; global flux =
  `Σ(x·area)·SPY/1e12` Pg yr⁻¹ (`SPY = 365.25·86400`).
- **The intensive variables are in neither branch and `latitudinal_sum` is wrong for
  them** — albedo, `lai`, `tas`/`soilT`, `wetfrac`, `landCoverFrac`, `burntArea`,
  `snowDepth`/`wtd`/`alt`, the `W m⁻²` energy terms. They are not rates, so the SPY
  multiply is meaningless, but an area-weighted *sum* is the wrong reduction anyway
  (they want a mean, which `latitudinal_sum` does not offer). Left out of `STOCKS` on
  purpose, so they stay visibly wrong rather than plausibly wrong.
- `latitudinal_sum()` keeps the file's native cadence (monthly stays monthly) and
  converts via the adapter's `to_pgc` (default in `core.py`; no adapter overrides it).
  `const.ANNUAL` picks the `yr`/`ann` vs `mon` filename token, independent of stock/flux
  (N pools and per-PFT carbon are annual but not stocks).
- Fills below `const.FILL_FLOOR = -1e3` (BiomeE −1e5, JULES −9999, stray −99999) → NaN.
- The `time` coord is `datetime64[us]`, not `[ns]`: overshoot runs end in 2300 and ns
  tops out at 2262, which silently wrapped the tail of every overshoot series (2299 read
  back as 1714). `core.to_datetime64` handles that cast, including the cftime objects
  xarray falls back to for those files, and `cache_csv` re-pins a cached index to `us` so
  a pre-2262 series and a post-2262 one can still be added.
- **A `decode_times=False` adapter must read the CF epoch off the file, never hardcode
  1850** — `core.cf_reference_month(units)`. Every 1pctCO2 file and the overshoot
  hist/ctrl runs count from 1850, but the overshoot **scenarios** were written with a
  `since 2024-01-01` reference. DLEM and TEM both hardcoded 1850 and so dated their
  2024-2300 scenarios as **1850-2126** — a silent 174-year shift that overlapped the
  historical period and made a scenario un-joinable with its own `hist` run (found and
  fixed 2026-09-02, when their overshoot adapters went in). CLM already read the epoch
  off the file; LPX-Bern and VISIT-UT decode absolute calendar years, so neither was
  exposed. Sanity rule for any overshoot series: hist and both controls span
  **1850-2023**, every scenario spans **2024-2300**.

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
| **BEPS** | 1°, `latitude`/`longitude`, dims `(lon,lat,time)` | datetime (`decode_times=True`; noleap → cftime, which `core.to_datetime64` handles) | computed spherical (R=6371 km) | nested, run dir = bare sim token (`bgc`/`cou`/`ctrl`); **every file carries a `_noDynVeg_noFire` suffix** | 54 vars × 3 stages = 162 files, uploaded 2026-09-02; 1850-1999 (150 yr, not 151); `stable` for bgc/ctrl, **ukesm only** for cou; `wetfrac` monthly (the one disagreement with `const.ANNUAL`); fills are `-99999` but arrive pre-masked via `_FillValue` encoding; `fch4soil` alone is `(lat,lon,time)`; ships a README, `export_report.json` (written/omitted inventory) and an answer key |
| **BiomeE** | 0.5°, `lat`/`lon` | datetime | provided `veg_area.nc` | flat; baseline/noFire/noNitrogen — factorial files insert a `fact_` token (`BiomeE_<forcing>_fact_<sim>_<token>_<var>…`); factorial runs uploaded 2026-08 (cou reachable; bgc/ctrl await re-labelling) | −1e5 fill; first valid yr 1851; the adapter spells `stable` for ALL constant-climate runs — bgc/ctrl and their `fact_` variants — agreed with the BiomeE team 2026-08-17. On disk, baseline bgc (40 files) and the `fact_` bgc/ctrl runs (162) are still labelled `ukesm`, so they sit unreachable **on purpose** until BiomeE re-uploads them as `stable`. Baseline ctrl already made that move: `BiomeE_stable_ctrl_*` (42 files = the old set + `cNS`/`cSeed`) supersedes the deliberately-unreachable `BiomeE_ukesm_ctrl_*` |
| **CLASSIC** | 1°, `latitude`/`longitude` | datetime | spherical × `sftlf` landfrac raster | nested; baseline/noFire/noNitrogen(+`-Ndep`), `post` token suffixes dir **and** trails cadence | var-name casing map (`fN2OFire→fN2oFire`, `wetCH4→wetch4`, `fch4soil→fCh4Soil`…) — the CH4 set uploaded 2026-08-24 uses plain `ch4`/`wetch4`/`fCh4Soil` names (the old `wetch4_spec` files are gone, and `ch4` ≠ `wetCH4` now — separate files); `cVegpft` monthly; `overshoot` stub returns `"null"`; **bgc re-run on the `stable` driver** — dir `CLASSIC_stable_1pctCO2-BGC<ndep><post>/`, files carry **no forcing token** (`CLASSIC_1pctCO2-BGC…`); the superseded `CLASSIC_UKESM_1pctCO2-BGC*` dirs (362 files) were deleted from the bucket 2026-08-21 (versioned — recoverable as prior versions) |
| **CLM** | 1°, `lat`/`lon` | `decode_times=False`, mixed: annual pools on bare `yr` years (`years_to_datetime`), else monthly noleap "hours since 1850" | provided `area` (km²) × `landfrac` | nested `<set>_ukesm_<sim>/clm6_<set>_ukesm_<sim>_<var>.nc`; factorial picks the run set: `baseline`→`hh`, `flat`→`flat` | uploaded two run sets `flat`/`hh` — `hh` is baseline; `flat`'s ctrl originally sat loose at the model-dir top, moved into `flat_ukesm_ctrl/` on the bucket 2026-08-21, so all 8 runs resolve; `rhPools`/`cSoilPools` fan out to the per-pool files (`rhPools_cwd…`, `cSoilpools_1..3`) via `paths()` and stack along a `pool` dim on read (`_POOL_SPLITS`, both arms, composes with overshoot time chunks); no cadence token in filename; decode cadence from file `time:units` NOT `const.ANNUAL` (they disagree on `wetfrac`/`canopyheightTotal`); only ukesm submitted (bgc/ctrl also labelled `ukesm`) |
| **CLM_FATES** | `lat`/`lon` | datetime | computed spherical | flat; baseline only | filename needs `vegtype`+`level` tokens; `read()` divides `fN2O`/`wetCH4` by 1000 (g→kg); `wetfrac` monthly; **ukesm only** — the prefix must still spell the *requested* pattern so ipsl/gfdl raise, since a hardcoded `FATES_ukesm` silently served ukesm data for every pattern (three identical γ_land curves, no error); **overshoot implemented** — same flat layout and same filename grammar as 1pctCO2 (shared `_fname`), only the experiment dir differs; sims ctrl/hist/l/m/vl/hl/ml + counterfactuals ml_cf/vl_cf/hl_cf (vl/vl_cf/hl_cf uploaded 2026-08), ukesm even for hist+ctrl, and the counterfactuals are hyphenated on disk (`_OVERSHOOT_SIMULATION_TOKENS`) |
| **DLEM** | 0.5°, `lat`/`lon`, lat truncated | `decode_times=False`, "months/years since 1850" by hand | provided `LAND_AREA_DLEM.nc` (km² → m²) | nested; baseline maps to curated `_ndep` dirs; **overshoot implemented** — own grammar: `os_ctrl`/`os_hist` (no forcing token) vs `os_future_<sim>` (pattern spelled), 6 runs x 27 vars uploaded 2026-08-31, `ukesm` only, no factorial axis | no `fFire`; `nbp`=0 in 1850; area raster is the full 360-row grid but output drops 3 rows at each pole, so it's `.sel`-ed onto the data grid; land-only (132.2 Mkm²) reproduces the group's own totals **exactly** (see `stats_for_WIEMIP_1pctCO2_DLEM.xlsx` below), spherical over-counted ~2.8% |
| **JSBACH** | 1°, `lat`/`lon` | datetime | computed spherical | nested; baseline/noNitrogen/noFire `post` suffix (suffixes dir **and** trails cadence) | fire ≈ 0 in baseline (so noFire ≈ baseline); **overshoot implemented** — different grammar from the 1pct arm: run dir is the *bare* sim token (`ctrl`, `hist`, `l`, `hl_cf`, …), and the file's forcing token is `crujra3` for hist/ctrl (`_CRUJRA_FORCED_SIMULATIONS`) but the GCM name for the 8 scenarios, never `stable`; all 10 submitted runs × 3 patterns reachable, `hist_ctrl` not submitted |
| **JULES** ⚠️ | n96, `latitude`/`longitude` | datetime (ignores `year` coord) | spherical × `landfrac_n96.nc` (`land`>1→0) | nested; **factorials are positional config strings** (`Nitrogen_DynVeg_Permafrost_noFire`…) baked into dir+file | cadence from `const.ANNUAL` (was **hardcoded `yr`** until 2026-09-02, which hid every monthly file — 35 in 1pct, 2028 in overshoot); adapter `ANNUAL` set only overrides `fVegFire`/`fSoilFire`; `ctrl`→`ctl`; **overshoot implemented** — the only model with a factorial axis there: the whole scenario set was repeated under 5 fire configs, so `retrieve_overshoot_variable` takes an optional `factorial` (declared in `OVERSHOOT_FACTORIALS`, `baseline`→`noFire`, `Fire####`→`FireP####`). Config leads the prefix instead of trailing the sim token (`JULESwiemipV2<config>_<forcing>_<sim>/…_<var>_<cad>_n96.nc`), `hist`/`ctl` carry no forcing token, counterfactuals are hyphenated (`hl-cf`). The overshoot var set grew from cVeg+cSoil to ~20/run (2026-09): all in-vocab now reachable, `fVegFire`/`fSoilFire` reachable as the vocab's `fFireCveg`/`fFireCsoil` (`wiemip_to_jules_variable_mapping`), `nep` requestable via `extra_variables` — only `fwetch4` (130 files) is still unreachable, pending a vocab decision. **`nbp` is deliberately NOT aliased to `nep`**: JULES uploaded both and they are different fields (global mean 0.24 vs 3.88 Pg C/yr — NBP is NEP minus the ~2 Pg C/yr of fire/disturbance), so aliasing would orphan the real NBP |
| **LPJ_EOSIM** | 0.5°, `latitude`/`longitude` | datetime (gregorian days-since-1850) | computed spherical | nested; baseline/`_noFire`/`_noNitrogen` suffix on dir+file | dir hyphenated `LPJ-EOSIM`, prefix underscored `LPJ_EOSIM`; full upload landed 2026-08-28 (97 vars/run × 15 runs incl. the new noNitrogen set); cadence overrides of `const.ANNUAL`: `wetfrac`/`nInorgSoil` monthly, `docFlux` annual (adapter `MONTHLY`/`ANNUAL` sets); 7 uploaded vars not in the vocab (`evspsblsoi`, `evspsblveg`, `fHarvest`, `fLuc`, `msl`, `tran`, `tsl` — 105 files) await a vocab decision; **overshoot implemented** (uploaded 2026-08-31) — same grammar minus the factorial axis (`LPJ_EOSIM_<forcing>_<sim>/…_<var>_<cad>_05.nc`), scenario token spelled exactly as the enum (`hl_cf`, not `hl-cf`), same 97 vars and same cadences as the 1pct arm; all 3 patterns × 8 scenarios uploaded (24 runs × 97 files) plus `hist` (2026-08-31); like JULES the CRUJRA-driven `hist` carries **no forcing token** (`LPJ_EOSIM_hist/LPJ_EOSIM_hist_<var>…`, `_NO_FORCING_TOKEN`), so all 3 GCM spellings collapse to one run; ctrl + hist_ctrl still missing and grouped with hist on the assumption they follow the same rule |
| **LPJmL6** | `latitude`/`longitude` | datetime | computed spherical | nested; baseline/noNitrogen (uploaded 2026-08) — token suffixes the run dir AND trails the cadence (`ukesm_cou_noNitrogen/LPJmL6_ukesm_cou_<var>_<cad>_noNitrogen_05.nc`) | `alt`/`fNHarvest` forced annual; `overshoot` stub returns `"null"` |
| **LPX_Bern** ⚠️ | 1°, `latitude`/`longitude` | `decode_times=False`, numeric years → floor (`years_to_datetime`) | provided `gridcell_area.nc` | flat; **factorials are (prefix,suffix) pairs** — lowercase `nofire`/`nopermafrost` **before** the sim token, suffix after | high fire (~15–23 Pg C/yr) but **real**; **overshoot implemented** |
| **TEM** | 0.5°, `latitude`/`longitude`, dims `(lon,lat,time)` | `decode_times=False`, noleap days-since-1850 by hand | computed spherical | nested, run dir = `SIM.upper()`; baseline only; **overshoot implemented** — JSBACH's overshoot grammar verbatim (bare sim dir, `crujra3` for hist/ctrl, GCM for the 8 scenarios), 10 runs x 11 vars uploaded 2026-09-01 | file prefix `TEM-MDM`; `nbp` sign/units look off |
| **VISIT_UT** | 0.5°, `lat`/`lon` | `decode_times=False`, "years since AD 0" fractional → floor | computed spherical | nested; baseline/noBVOC/noFire `post` suffix | **always monthly** (`mon` hardcoded); `fFire` mis-scaled — adapter warns; **overshoot implemented**, incl. ml/ml_cf; overshoot control is the one run where dir and file tokens disagree (dir `…_control/`, files `…_CTRL_…`) |

`overshoot_path` is a real implementation for **CLM, CLM_FATES, DLEM, JSBACH, JULES,
LPJ_EOSIM, LPX_Bern, TEM, VISIT_UT** (DLEM + TEM added 2026-09-02, from uploads that
landed 08-31 / 09-01); a `"null"` stub (resolves then fails at `read()`) for **CLASSIC,
LPJmL6**; and unimplemented (base `NotImplementedError`) for **BiomeE**. Those nine are
every group that has uploaded overshoot output — every other
`overshoot/output/<MODEL>/` dir on the bucket is an empty placeholder, so nothing else
needs an adapter yet. Each of the nine spells overshoot differently from its own 1pct
arm; don't assume the 1pct grammar carries over (LPJ-EOSIM is the one model where it
does, factorial axis aside; TEM's overshoot grammar is JSBACH's, not TEM's own). Nobody
submitted `hist_ctrl`.

## Known data-quality flags

- **VISIT-UT `fFire`** mis-scaled (~1000× / a g→kg slip; the adapter emits a runtime
  warning). **Exclude** from fire analyses — flag to Akihiko Ito.
- **VISIT-UT labels the `cLeaf`/`cRoot`/`cWood` pools `kg C m-2 s-1`** in the file
  header (its `cVeg` is correctly `kg C m-2`). A header slip, not a data problem — a
  leaf-carbon *rate* is meaningless and `const.STOCKS` keys off the variable name, not
  the attribute, so the registry integrates them correctly. Only bites someone reading
  `WIEFile.units` or the raw header. Worth mentioning to Akihiko Ito alongside `fFire`.
- **JULES overshoot mislabels the cadence token on 3 variables, in both directions**:
  `rhLayers` is `_mon_` but holds annual data (276 steps, July-2 stamps, same axis as
  `cVeg`), while `fVegFire`/`fSoilFire` are `_yr_` but hold monthly data (3312 steps,
  same axis as `fFire_mon`). The registry reaches all three — the token is what names
  the file, and the adapter's `ANNUAL` set spells the token, not the cadence — but a
  cadence-aware analysis will mis-read them. Flag to the JULES group.
- **LPX-Bern `fFire`** ~15–23 Pg C/yr (≈8× others) — high but a real model result.
- **JSBACH `fFire`** ≈ 0 (fire effectively off in this run).
- **DLEM** has no `fFire`; `nbp` is 0 in 1850 then nonzero.
- **DLEM ships its own answer key**: `1pctCO2/output/DLEM/stats_for_WIEMIP_1pctCO2_DLEM.xlsx`
  holds their reported global totals (g C / g N) for cSoil, nSoil, GPP, NBP and N2O —
  one sheet per variable, one column per run, 1850-2000. `debug/verify_dlem_area.py`
  checks the registry against it. Weighted by `LAND_AREA_DLEM.nc` the cSoil series
  matches to 6 significant figures on all 9 runs (which also confirms the curated
  `_ndep` mapping: their `BGC` column is our `bgc` → `noNdep` files, `BGC_ndep` our
  `bgc_ndep`); gpp/fN2O land within 0.1%. Each `<run>/figure/` dir has the same totals
  as PNGs. Their NBP sheet has a stray unnamed `Column1` splitting the BGC column.
- **`const.STOCKS` was widened (2026-08-24) from the 7 carbon pools to all 36 per-m²
  amounts.** Before that, every other pool was multiplied by `SPY` in `core.to_pgc`:
  `latitudinal_sum("nSoil")` returned 2.9e9 instead of 92.2 Pg N, a ratio of exactly
  SPY. The N pools, the non-headline C pools (`cProduct`, `cVegpft`, `cSoilpft`,
  `cLitterpft`, `cSoilPools`, `cSoilLayers`, `cSoilAbove1m`, `cSoilBelow1m`,
  `cPoolVr`, `cOther`, `cfuelTotal`) and the water pools were affected **for every
  model**. Carbon stock/flux work (cVeg/cSoil/cLitter and the `f*` fluxes) was never
  affected, so `land_carbon_stock()` results did not change. Confirmed against DLEM's
  xlsx (nSoil now 0.00% off on all 9 runs) and magnitude-checked cross-model: nVeg 5.5,
  nLitter 1.4, nSoil 92.2 Pg N, mrso 1.6e5 Gt H₂O.
  **A `STOCKS` edit does not bust the CSV cache** (keyed on the `.nc` mtime) — the 2
  stale `nSoil` CSVs were deleted at the time, but re-check `const.CSV_ROOT` if the set
  changes again.
- **CLM `burntareaTotal` is corrupt in the upload** (found by the aggregate sweep,
  2026-08-27). The raw field is declared `units = fraction` but contains **`inf`** and
  denormal values around 3e-43 — the signature of reinterpreted bytes, not a physical
  burnt-area fraction. A single `inf` poisons any spatial reduction, so all four CLM
  runs carrying it (`bgc`/`ctrl` x `baseline`/`flat`) produce an all-null global series.
  The sweep leaves those nulls in place rather than masking the non-finite cells, so the
  corruption stays visible instead of yielding a plausible series from the good cells.
  **Flag to the CLM group**; exclude from any burnt-area analysis.
- **BEPS's `baseline` factorial is NOT a process-complete baseline.** Every file it
  uploaded carries `_noDynVeg_noFire` — static vegetation and fire off is the only
  configuration BEPS ran — and the adapter maps `baseline` onto it because the
  surrounding tooling requires that key (`aggregate.specs.model_dir` hardcodes
  `factorial="baseline"`, as does `land_carbon_stock`'s default). So a cross-model
  "baseline" comparison silently includes a noFire/noDynVeg run for BEPS. Same shape as
  CLM's `baseline`→`hh` and JULES's overshoot `baseline`→`noFire`, but here it crosses a
  *process* boundary, so exclude BEPS from fire or dynamic-vegetation analyses and treat
  its β/γ_land as a factorial point, not a baseline. Declaring a second factorial name
  for the same files was rejected: `enumerate_runs` keys its dedupe on
  `(model, factorial, paths)`, so it would emit two identical run artifacts per run.
- **BEPS ships its own answer key**, `1pctCO2/output/BEPS/global_carbon_aggregates.csv`
  — annual global cVeg/cLitter/cSoil in Pg C per stage, summed exactly as the registry
  does (spherical area, missing cells excluded). `debug/verify_beps.py` checks against
  it: **0.0006% max error across all 9 stage × variable series**, which confirms the
  spherical-area recipe and the fill mask. **Its `year` column is broken** — 150 rows
  but only 76 unique years, stepping 1850, 1852, 1852, 1854 … 1998, 1998, 2000, an axis
  derived at roughly double the true step. The netCDF time axis is correct (1850-1999),
  so match rows by ORDER, not by that column. Flag to the BEPS group.
- **BEPS `fch4soil` is entirely ≤ 0** (min −2.2e−11, max −0.0 `kg CH4 m-2 s-1`) — it
  reports soil methane *uptake* with a negative sign where other models report a
  positive source. Physically defensible for upland soils, but check the sign
  convention with the group before pooling it cross-model.
- **DLEM's and TEM's overshoot `ctrl` is a HISTORICAL control** — 1850-2023 (174
  steps), the same span as their `hist`, not the 2024-2300 span of a scenario. Do not
  difference a scenario against it timestep-for-timestep.
- **TEM `nbp`** sign/units look off (persistent ~−10 Pg C/yr source while cVeg+cSoil
  rise) — flag to the TEM group.
- **TEM and JULES submitted no `cLitter`** (0 files across every combo), so their
  `land_carbon_variables()` is `cVeg + cSoil` and litter is *presumed* folded into the
  reported `cSoil`. Unconfirmed with either group — a cross-model comparison that hinges
  on an explicit litter pool should treat those two totals with care. (CLM likewise
  declares only cVeg + cSoil.)
- **LPJ-EOSIM `LPJ_EOSIM_ipsl_cou_noFire/`**: the 2026-08-28 re-upload added 87
  properly-named `ipsl` files, so the run is now reachable — but the 25 stray files
  named `LPJ_EOSIM_ukesm_cou_…` from the original slip are still in the dir and need
  deleting on the bucket (do NOT alias them in the adapter — that would orphan the
  real ukesm run).
- **VISIT-UT overshoot `gfdl_ml_cf/`** contains `albedo` + `burntArea` misnamed with the
  `ml` prefix. Flag to Akihiko Ito. (The duplicate hyphen-spelled `VISIT-UT_ukesm_ml-cf/`
  dir noted earlier is gone as of 2026-08-28.)
- **VISIT-UT overshoot `fch4soil`** (uploaded 2026-08-28) is unreachable in the three
  control dirs: the filenames spell the run token lowercase
  (`VISIT-UT_<forcing>_control_fch4soil_…`) where every sibling file uses `CTRL`.
  Flag to Akihiko Ito for a rename (3 files).
- **DLEM's `nProduct` + `trans` are now reachable** (resolved 2026-09-02): both were
  added to `variable_overrides.extra_variables`, which closed the last 30 uncovered
  1pctCO2 files (15 runs x 2) and the matching 12 in overshoot (6 runs x 2).
  `nProduct` was already in `const.STOCKS` + `const.ANNUAL` — only the auto-synced
  `variables.py` list was missing it, so it integrates as a Pg N pool. `trans` is
  transpiration and is deliberately **not** aliased onto the vocab's `tveg`, which
  would orphan a real `tveg` upload; it falls through to the flux branch, which is
  right for a `kg m-2 s-1` rate. If the data request ever adopts either name, drop it
  from `extra_variables` and let the sync carry it.
- **A stray `LPX-Bern_gfdl_ml_cf_ch4_mon_1.nc`** (2026-08-13) sits in the **1pctCO2**
  LPX-Bern dir; the identical file in the overshoot dir is reachable, so the 1pct copy
  is a duplicate to delete.
- **macOS AppleDouble junk** (`._<name>.nc` sidecars) is scattered through VISIT-UT
  (1pct + overshoot). Harmless, but it inflates uncovered counts.
- Known-unreachable-by-design leftovers: CLM's `<run>_deep/` per-layer output (60
  files, up to ~9.4 GB each — deliberately unmapped until an analysis needs per-layer
  data), 9 odd top-level `hh_<run>.nc` stubs in its overshoot dir, and 10 loose
  top-level `<set>_<forcing>_<run>.nc` bundles (~471 MB each, 2026-08-18) in its 1pct
  dir; CLM-FATES's monthly duplicates of annual stocks (41 in 1pctCO2 — incl. a few
  hist/hl-named strays in the 1pct dir — and 110 in overshoot = 11 vars × 10 sims);
  LPX-Bern's 69 `overshoot_*`-prefixed copies (bitwise identical to the `ukesm` ones);
  CLASSIC's per-run `land_fraction` rasters (22, the sftlf class) and one loose
  top-level `CLASSIC_stable_cLeaf_ann_1deg.nc` stub.
  Cleaned up 2026-08-21: CLM's 94 loose top-level flat-ctrl files were moved into
  `flat_ukesm_ctrl/` (reachable now), the `rhPools_*`/`cSoilpools_*` pool splits
  became reachable via `_POOL_SPLITS`, and CLASSIC's superseded UKESM-BGC dirs were
  deleted from the bucket.

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
  set. `qa.sh <coverage|uncovered|reads> <one_pct_co2|overshoot> [MODEL]` drives it —
  note the **experiment** argument: run both, the overshoot arm covers the five models
  that uploaded overshoot output, sweeping the adapter's `OVERSHOOT_FACTORIALS` where it
  declares any (JULES). It only spells combos a user may legally request (bgc/ctrl as
  `stable`), so an uncovered file means genuinely unreachable through the API, not merely
  unspelled.
- **`test_factorials.py`** — factorial-axis coverage/accessibility, through the public
  API. `qa_factorials.sh [coverage|reads|plots|all] [MODEL]` drives it.
- **`probe_constant_climate_runs.py`** — one line per model showing whether its
  bgc/bgc_ndep/ctrl run resolves under the mandatory `stable` pattern. Cheapest way to
  catch an adapter that interpolates the requested forcing into a constant-climate name.
- **`verify_newly_reachable.py`** / **`verify_classic_bgc.py`** — read + global-integral
  spot checks for the files the CLASSIC/BiomeE/VISIT-UT naming fixes exposed.
- **`verify_dlem_area.py`** — DLEM's `LAND_AREA_DLEM.nc` weighting against the group's
  own `stats_for_WIEMIP_1pctCO2_DLEM.xlsx`: cSoil over all 9 runs, plus a flux spot-check
  (the flux files are 0.6-0.9 GB monthly, so those are limited to 2 runs). Needs
  `openpyxl` in the QA venv.
- **`verify_beps.py`** — BEPS reachability plus its `global_carbon_aggregates.csv`
  answer key over all 3 stages × cVeg/cLitter/cSoil, a dim-order check on `fch4soil`,
  and land carbon per stage. Prints `all checks passed` or the failures.
- **`verify_dlem_tem_overshoot.py`** — the DLEM + TEM overshoot adapters: full
  reachability (every on-disk `.nc` in both experiments named by some legal request),
  then per-run reads asserting the overshoot grid matches the weights built off the
  1pct reference file, the series reaches 2300 (no `datetime64[ns]` wrap), and land
  carbon is sane. Prints `all checks passed` or the failures.
- **`verify_jules_overshoot.py`** — same for JULES overshoot: all 5 fire configs ×
  scenario × pattern resolve (260/260 files), then a read plus a land-carbon series per
  config.
- **`verify_clm_overshoot.py`** — CLM's chunked overshoot runs: `exists()` returns a plain
  False for every model (including the unmapped ones), then hist/scenario reads showing the
  chunks concatenated into one 1850–2023 / 2024–2300 series, plus land carbon per run.
- **`regen_land_carbon_stocks.py`** — every model × registered factorial × valid
  sim/forcing through `wr.land_carbon_stock()`; one CSV per combo plus `summary.csv`
  under `/tmp/wiemip/land_carbon/`, and it re-warms `const.CSV_ROOT` as a side effect.
  Skips combos whose output already exists, so it is resumable; pass model names as argv
  to redo just those. Long job (~1h for the full sweep) — `nohup` it on the box.

## Static band aggregations — moved

The `aggregate/` sweep that precomputes the latitude-band series for the QA site now
lives in **`../wiemip-validation`**, beside the viewer that reads its output. It is a
*consumer* of this package (`import wiemip_registry`), never a part of it — it was
never in `pyproject.toml`'s `packages` either. Its working notes are
`../wiemip-validation/AGENTS.md`.

Nothing in this repo imports it. What matters here: the sweep runs against the copy of
`wiemip_registry` **deployed to the hub** (`/opt/tljh/user`), so an adapter change only
reaches the nightly aggregation once it is pushed to `main` and the `deploy-to-hub`
action has run.
