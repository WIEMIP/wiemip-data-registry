# LPJmL6 soil layer depths

`read()` returns `soilT`, `mrsoLayer`, `cSoilLayers`, `nOrgSoilLayer` and `nInorgSoilLayer`
on a `soil` axis of layer-middle depths in m.

## Source

Every file ships a `depth` coordinate in m (`long_name = "depth_below_land"`) with no
bounds. The registry takes those values as layer middles. The group has not confirmed this
(2026-10-14).

## Snippet

The adapter adds no depths. It only lists the variables (`convert.py:27`):

```python
LAYERED_VARIABLES = {
    "soilT",
    "mrsoLayer",
    "cSoilLayers",
    "nOrgSoilLayer",
    "nInorgSoilLayer",
}
```

`WIEFile._standardize_layers` (`core.py:696`) then renames `depth` to `soil`, requires
`units == "m"`, pins the values to float64 at 1 µm and checks that they increase.

## Result

Read off the bucket 2026-10-23 (`stable_bgc`):

| variable | file level dim | `soil` [m] |
|---|---|---|
| soilT | `depth` | 0.1, 0.35, 0.75, 1.5, 2.5 |
| mrsoLayer | `depth` | 0.1, 0.35, 0.75, 1.5, 2.5 |
| cSoilLayers | `depth` | 0.1, 0.35, 0.75, 1.5, 2.5 |
| nOrgSoilLayer | `depth` | 0.1, 0.35, 0.75, 1.5, 2.5 |
| nInorgSoilLayer | `depth` | 0.1, 0.35, 0.75, 1.5, 2.5 |
