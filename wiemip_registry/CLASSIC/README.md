# CLASSIC soil layer depths

`read()` returns `soilT` and `mrsoLayer` on a `soil` axis of layer-middle depths in m.

## Source

Layer bounds from Vivek Arora (email, 2026-09-23), copied into the `convert.py` module
docstring: 15 permeable soil layers to 4 m, then 5 bedrock layers to 62 m. The files
index the 20 layers on `layer` = 1-20 (`units = "layer"`).

## Snippet

`convert.py:48-74`:

```python
_SOIL_LAYER_BOUNDS = (
    0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1,
    1.2, 1.6, 2.2, 3, 4,
    7, 12, 22, 42, 62,
)
_SOIL_LAYER_DEPTHS = tuple(
    (top + bottom) / 2
    for top, bottom in zip(_SOIL_LAYER_BOUNDS[:-1], _SOIL_LAYER_BOUNDS[1:])
)
```

`convert.py:199-202`, in `read()`:

```python
if variable in self.LAYERED_VARIABLES:
    da = da.assign_coords(
        layer=("layer", list(_SOIL_LAYER_DEPTHS), {"units": "m"})
    )
```

`WIEFile._standardize_layers` (`core.py:696`) then renames `layer` to `soil`, requires
`units == "m"`, pins the values to float64 at 1 µm and checks that they increase.

## Result

Read off the bucket 2026-10-23 (`stable_1pctCO2-BGC`):

| variable | file level dim | `soil` [m] |
|---|---|---|
| soilT | `layer` (1-20) | 0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95, 1.1, 1.4, 1.9, 2.6, 3.5, 5.5, 9.5, 17, 32, 52 |
| mrsoLayer | `layer` (1-20) | same as soilT |

The last 5 depths (5.5 to 52 m) are bedrock.
