# CLM soil layer depths

`read()` returns `soilT`, `soilIce`, `soilMoist`, `mrsoLayer`, `soilRh` and `cPoolVr` on a
`soil` axis of depths in m.

## Source

The files ship CLM's own level coordinates in m: `levgrnd` (`"coordinate ground levels"`)
on soilT, `levsoi` (`"coordinate soil levels (equivalent to top nlevsoi levels of
levgrnd)"`) on everything else. The registry uses them as is.

## Snippet

The adapter adds no depths. It only lists the variables (`convert.py:71`):

```python
LAYERED_VARIABLES = {
    "soilT",
    "soilIce",
    "soilMoist",
    "mrsoLayer",
    "soilRh",
    "cPoolVr",
}
```

`WIEFile._standardize_layers` (`core.py:696`) then renames `levgrnd` / `levsoi` to
`soil`, requires `units == "m"`, pins the values to float64 at 1 µm and checks that they
increase.

## Result

Read off the bucket 2026-10-23 (`hh_ukesm_bgc_deep`):

| variable | file level dim | `soil` [m] |
|---|---|---|
| soilT | `levgrnd` (25) | 0.01, 0.04, 0.09, 0.16, 0.26, 0.4, 0.58, 0.8, 1.06, 1.36, 1.7, 2.08, 2.5, 2.99, 3.58, 4.27, 5.06, 5.95, 6.94, 8.03, 9.795, 13.327767, 19.48313, 28.870724, 41.998436 |
| soilIce | `levsoi` (20) | 0.01, 0.04, 0.09, 0.16, 0.26, 0.4, 0.58, 0.8, 1.06, 1.36, 1.7, 2.08, 2.5, 2.99, 3.58, 4.27, 5.06, 5.95, 6.94, 8.03 |
| soilMoist | `levsoi` (20) | same as soilIce |
| mrsoLayer | `levsoi` (20) | same as soilIce |
| soilRh | `levsoi` (20) | same as soilIce |
| cPoolVr | `levsoi` (20) | same as soilIce |
