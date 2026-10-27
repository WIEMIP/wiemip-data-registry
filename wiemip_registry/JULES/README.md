# JULES soil layer depths

`read()` returns `soilT`, `soilIce`, `mrsoLayer`, `cSoilLayers`, `rhLayers`,
`nOrgSoilLayer` and `nInorgSoilLayer` on a `soil` axis of layer-middle depths in m.

## Source

Most files ship a `depth` coordinate in m with JULES's 10 layer middles. The adapter
carries the same 10 values and overwrites the file's coordinate in two cases:

- **Overshoot soil C/N layer files** (`cSoilLayers`, `rhLayers`, `nOrgSoilLayer`) index
  the layers on `sclayer` = 1-10 with no units.
- **1pctCO2 `nInorgSoilLayer`** has its `depth` truncated to integers
  (0, 0, 0, 0, 1, 1, 2, 3, 6, 9), so the values repeat.

## Snippet

`convert.py:15`:

```python
_SOIL_LAYER_DEPTHS = (0.05, 0.175, 0.36, 0.635, 1.05, 1.67, 2.59, 3.96, 6.005, 9.06)
```

`convert.py:160-167`, in `read()`:

```python
if "sclayer" in da.dims:
    da = da.rename({"sclayer": "depth"}).assign_coords(
        depth=("depth", list(_SOIL_LAYER_DEPTHS), {"units": "m"})
    )
if "depth" in da.dims and not da.indexes["depth"].is_unique:
    da = da.assign_coords(
        depth=("depth", list(_SOIL_LAYER_DEPTHS), {"units": "m"})
    )
```

`WIEFile._standardize_layers` (`core.py:696`) then renames `depth` to `soil`, requires
`units == "m"`, pins the values to float64 at 1 µm and checks that they increase.

## Result

Read off the bucket 2026-10-23. Every variable comes back on the same 10 depths:
0.05, 0.175, 0.36, 0.635, 1.05, 1.67, 2.59, 3.96, 6.005, 9.06 m.

| variable | 1pctCO2 file level dim | overshoot file level dim |
|---|---|---|
| soilT | `depth` | `depth` |
| soilIce | `depth` | not checked |
| mrsoLayer | `depth` | `depth` |
| cSoilLayers | `depth` | `sclayer` (1-10) |
| rhLayers | `depth` | `sclayer` (1-10) |
| nOrgSoilLayer | `depth` | `sclayer` (1-10) |
| nInorgSoilLayer | `depth` (truncated, repeats) | not checked |

1pctCO2 was read from `bgc` (soilIce from `ukesm_cou`, as bgc has no soilIce). Overshoot
was read from `noFire_ukesm_hl`.
