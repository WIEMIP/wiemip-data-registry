# LPX-Bern soil layer depths

`read()` returns `soilT` and `mrsoLayer` on a `soil` axis of layer-middle depths in m.

## Source

The group's bucket README (`1pctCO2/output/LPX-Bern/README.md`, 2026-10-11) tables the 8
layer middles and says they apply to mrsoLayer too.

- **soilT** ships them in its own `layer` coordinate (m, float32). The registry uses it
  as is.
- **mrsoLayer** indexes `layer` = 1-8 with no units, so the adapter assigns the README's
  middles.

## Snippet

`convert.py:22`:

```python
_SOIL_LAYER_DEPTHS = (0.05, 0.15, 0.25, 0.4, 0.6, 0.85, 1.25, 1.75)
```

`convert.py:101-104`, in `read()`:

```python
if variable == "mrsoLayer":
    da = da.assign_coords(
        layer=("layer", list(_SOIL_LAYER_DEPTHS), {"units": "m"})
    )
```

`WIEFile._standardize_layers` (`core.py:696`) then renames `layer` to `soil`, requires
`units == "m"`, pins the values to float64 at 1 µm (so soilT's float32 depths match
mrsoLayer's float64 ones) and checks that they increase.

## Result

Read off the bucket 2026-10-23 (`bgc`):

| variable | file level dim | `soil` [m] |
|---|---|---|
| soilT | `layer` (m) | 0.05, 0.15, 0.25, 0.4, 0.6, 0.85, 1.25, 1.75 |
| mrsoLayer | `layer` (1-8) | same as soilT |
