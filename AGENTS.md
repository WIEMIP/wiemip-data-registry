# WIE-MIP data processing — working notes

Processing land-model-intercomparison output (WIE-MIP) into global stocks & fluxes.
This file is the shared reference for what we've learned about the data. Keep it current.

## Where the data lives & how to run

- Data is an **S3 bucket mounted via s3fs (read-only) at `/mnt/wiemip`** on the ubuntu box:
  `ssh ubuntu@<box-ip>`. It is **not** on the Mac, so scripts must **run on the box**.
- Python env on the box: `source /opt/analysis/bin/activate` (py3.10, xarray 2025.6, numpy 2.2,
  matplotlib 3.10, netCDF4). Stack: **xarray + numpy + pandas + matplotlib** (no Dask).
- Workflow: develop here on the Mac → `scp`/`rsync` to the box → run there → `scp` figures back → `open`.
- s3fs is **latency-bound (~1 s per file open)**. Reading thousands of files serially is slow
  (full 1pctCO2 scan ≈ 90 min); parallelize header reads, and cache intermediates to CSV.

## 1. Data structure

```
/mnt/wiemip/<experiment>/output/<MODEL>/[<run-subdir>/]<file>.nc
```
- **Experiments:** `1pctCO2`, `overshoot`. (`overshoot` currently only has **LPX-Bern** populated.)
  (registry namespace aliases the leading-digit dir `1pctCO2` → `one_percent_co2`.)
- **Models populated in 1pctCO2 (have data):** BiomeE, CLASSIC, DLEM, JSBACH, JULES, LPX-Bern,
  VISIT-UT, TEM, LPJ-EOSIM. The other ~20 dirs (BEPS, CLM, ELM, …) are empty placeholders.
  `LPJ-EOSIM` is a recent, partial upload — only `cVeg` so far, across bgc/ctrl/(ukesm) cou plus a
  `noFire` factorial of each. `extremes` is a pseudo-dir, not a model.
- **One variable per netCDF file.** ~4938 files in 1pctCO2.
- **Layout differs by model:** *flat* (run encoded in the filename prefix — BiomeE, LPX-Bern) vs
  *nested run sub-directories* (CLASSIC, DLEM, JSBACH, JULES, VISIT-UT).

## 2. Naming conventions

Filenames are roughly: `<model/run tokens>_<VAR>_<cadence>_<grid|suffix>.nc`

| token type | values |
|---|---|
| **VAR** (CMIP names) | `cVeg`, `cSoil`, `cLitter`, `cWood`/`cLeaf`/`cRoot`/`cCwd`, `gpp`, `npp`, `nbp`, `ra`, `rh`, `fFire`, `fFireCveg`, `lai`, `nbp`, n-cycle (`fBNF`,`fN2O`,…), `*pft` per-PFT variants |
| **cadence** | `yr`/`ann` (annual, usually stocks), `mon` (monthly, usually fluxes), `day` |
| **grid** | `05` = 0.5°, `1`/`1deg` = 1°, `n96` (JULES) |
| **simulation / run type** | `bgc` (biogeochem-coupled), `cou` (fully coupled), `rad` (radiatively coupled), `ctrl`/`ctl`/`piControl`/`stable` (control) |
| **forcing ESM** (cou/rad) | `ukesm`, `gfdl`, `ipsl` — use **UKESM** for cross-model comparability |
| **factorial suffix** | `noNitrogen`, `noFire`, `noPermafrost`, `noBVOC`, `noNdep`, `noDynVeg`, `addPermafrostC[N][Ninorg]`, `removePermafrostC…`, `Fire####` (param sweep); LPX uses lowercase `nofire`/`nopermafrost` prefixes |

**Comparable-run rule (from Tom):** a run/dir/file carrying a `_no<Process>` (or `add/remove/Fire####`)
suffix is a **factorial** sensitivity run; a run with **no such suffix is the raw/baseline run**, and the
baseline runs are what's directly **comparable across models**.

**Caveats to the rule:**
- `-Ndep` / `_ndep` means N-deposition **ON** (additive) — *not* a "no" factorial.
- Models disagree on what the baseline includes: **DLEM** baseline has `ndep` in the *dir* name but the
  *filename* has no suffix (so it's the baseline); **CLASSIC** baseline is plain `BGC` and `-Ndep` is a
  separate variant.
- **JULES** has no truly-bare run — every config carries `Nitrogen_DynVeg_Permafrost_noFire`
  (their README designates that as the reference). Treat it as JULES's baseline.

## 3. Per-model quirks → why each model needs a bespoke adapter

There is **no single reader**: dim order, coordinate names, time encoding, area weighting, fill
values and even which variables exist all vary by model. Encode per-model knowledge once (see
`extract.py`'s adapter tables) and drive it generically.

| model | grid/dims | time encoding | area weighting | fill / gotchas | runs present |
|---|---|---|---|---|---|
| **BiomeE** | 0.5°, dims `(lon,lat,time)` | datetime, annual→2028 | **`veg_area.nc`** (vegetated m²) | cVeg/etc use **−1e5 fill → must mask**; first valid yr 1851 | bgc, cou (**no ctrl**), ukesm-forced |
| **CLASSIC** | 1°, `latitude/longitude` | datetime | compute spherical (ocean=NaN) | units written `kg C m$^{-2}$` | BGC/COU/RAD (+`-Ndep`,`noFire`,`noNitrogen`), `stable_piControl` |
| **DLEM** | 0.5°, lat=354 (truncated) | `years since 1850` (yr) / `months since 1850` (mon) → **decode_times=False** | compute spherical (ocean=0) | **no `fFire`**; `nbp`=0 in 1850 (nonzero later) | BGC[_ndep], COU_{esm}[_ndep], RAD_*, CTRL |
| **JSBACH** | 1°, lat/lon | datetime (epoch 1847) | compute spherical (ocean=NaN) | `fFire`≈0 (fire off); dirs hold two prefixes (`stable_bgc_` vs `stable_1pctCO2_`) — pick the exp-tagged one | stable_bgc, stable_ctrl, ukesm_cou |
| **JULES** | n96, `latitude/longitude` | datetime + `year` coord | `landfrac_n96.nc` `land` × spherical cell; **`land` has ~1e37 ocean fill → mask >1→0** | **only `cVeg` & `cSoil` submitted**; ctrl is **`ctl`** | bgc/ctl/{esm}_cou, all `Nitrogen_DynVeg_Permafrost_*` |
| **LPX-Bern** | 1°, `latitude/longitude` | `years`/`year` numeric → **floor**, decode_times=False | **provided `gridcell_area.nc`** (`area`, land-only) | high-fire model (~15–23 PgC/yr fire — **real**, not a bug); has `fFireCveg` too | flat: bgc/ctrl/cou_{ESM}/rad_{ESM} (+nofire/nopermafrost/ndep variants) |
| **VISIT-UT** | 0.5°, lat/lon | `years since AD 0` (fractional) → **floor**, decode_times=False | compute spherical (no land frac; README §: Σ flux×area) | **`fFire` BROKEN** (units off ~600×, see below) — exclude; stocks/gpp/npp/rh OK | BGC/CTRL/{esm}_COU/{esm}_RAD (+noBVOC/noFire) |
| **TEM** (TEM-MDM) | 0.5°, `latitude/longitude`, dims `(lon,lat,time)` | `days since 1850-01-01` **noleap** → **decode_times=False**, decode by hand | compute spherical (ocean=NaN in data → land mask) | file prefix `TEM-MDM`; nested `BGC/COU/CTRL` dirs; `nbp` sign/units look off (persistent ~−10 PgC/yr source while cVeg+cSoil rise) — flag for TEM group | **baseline only**: `stable_bgc`, `ukesm_cou`, `stable_ctrl` (no rad, no ndep, no factorials); vars = cVeg,cSoil,gpp,lai,mrro,mrso,nbp,npp,pr,ra,rh |
| **LPJ-EOSIM** | 0.5° (`05`), `latitude/longitude` (both ascending), dims `(time,lat,lon)` | `days since 1850-01-01` **gregorian** (end-of-yr stamps 1850..2000) → decodes to datetime64, **decode_times=True** | compute spherical (ocean=NaN in data → land mask) | model dir `LPJ-EOSIM` hyphenated but run-dir/file prefix `LPJ_EOSIM` underscored; `noFire` is a post-cadence `_noFire` suffix on BOTH the run sub-dir and the filename | **partial**: `stable_bgc`, `stable_ctrl`, `ukesm_cou`, each with a `noFire` variant (no rad, no ndep); only `cVeg` uploaded so far |

## 4. Units & global integral

- **Stocks** (`cVeg/cSoil/cLitter`): `kg C m⁻²` → `Pg C = Σ(x·area)/1e12`.
- **Fluxes** (`gpp/npp/rh/nbp/fFire`): `kg C m⁻² s⁻¹`, monthly → annual-mean rate × seconds/yr:
  `Pg C yr⁻¹ = mean_months(Σ x·area) × (365.25·86400) / 1e12`.
- `1 Pg = 1e12 kg`. Monthly data collapsed to annual (stocks: mean; fluxes: mean rate → ×SPY).

## 5. Known data-quality flags

- **VISIT-UT `fFire`** is mis-scaled (~600×; netCDF says `kg m⁻²s⁻¹` but README raw unit is
  `Mg C ha⁻¹ month⁻¹`; neither interpretation is physical, peaks exceed biomass). **Excluded** from
  fire plots — flag for Akihiko Ito.
- **LPX-Bern `fFire`** ~15–23 Pg C/yr (≈8× others) — high but real model output via their own recipe.
- **JSBACH `fFire`** ≈ 0 (fire effectively off in this run).
- **DLEM** has no `fFire`; `nbp` is 0 in 1850 then nonzero.

## 6. Scripts in this repo

- `build_registry.py` — walk both experiments, parse names + read **runtime** metadata (variable,
  units, dims, grid, time) → `registry.csv`. (Serial is slow; parallelize header reads.)
- `extract.py` — per-model adapters → global annual series CSV per `(simulation, model, variable)`
  under `/tmp/wiemip/series/`.
- `plot_runtype.py` — one 8-panel figure per run type (bgc/ctrl/cou), one line per model.
