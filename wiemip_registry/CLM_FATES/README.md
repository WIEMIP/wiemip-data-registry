# CLM-FATES soil layer depths

`read()` returns `soilT`, `soilIce`, `soilRh` and `cSoilLayers` on a `soil` axis of depths
in m. `soilT` is uploaded as `tsl`.

## Source

Every file ships a float32 `depth` coordinate in m, with `depth_bnds`. The registry uses
`depth` as is.

## Snippet

The adapter adds no depths. It only lists the variables (`convert.py:40`) and maps
`soilT` to the file's `tsl`:

```python
LAYERED_VARIABLES = {"soilT", "soilIce", "soilRh", "cSoilLayers"}

wiemip_to_clm_fates_variable_mapping = {
    ...
    "soilT": "tsl",
}
```

`WIEFile._standardize_layers` (`core.py:696`) then renames `depth` to `soil`, requires
`units == "m"`, pins the values to float64 at 1 µm (so float32 `0.009999999776` becomes
`0.01`) and checks that they increase.

## Result

Read off the bucket 2026-10-23 (`stable_bgc`):

| variable | file level dim | `soil` [m] |
|---|---|---|
| soilT (`tsl`) | `depth` (25) | 0.01, 0.04, 0.09, 0.16, 0.26, 0.4, 0.58, 0.8, 1.06, 1.36, 1.7, 2.08, 2.5, 2.99, 3.58, 4.27, 5.06, 5.95, 6.94, 8.03, 9.795, 13.327767, 19.48313, 28.870724, 41.998436 |
| soilIce | `depth` (20) | 0.01, 0.04, 0.09, 0.16, 0.26, 0.4, 0.58, 0.8, 1.06, 1.36, 1.7, 2.08, 2.5, 2.99, 3.58, 4.27, 5.06, 5.95, 6.94, 8.03 |
| soilRh | `depth` (20) | same as soilIce |
| cSoilLayers | `depth` (20) | same as soilIce |
