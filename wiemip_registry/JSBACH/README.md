# JSBACH soil layer depths

`read()` returns `soilT` and `mrsoLayer` on a `soil` axis of layer-middle depths in m.

## Source

The files carry a bare `layer` dim (size 5, no coordinate). The depths come from the
5-layer table in the group's bucket README (`1pctCO2/output/JSBACH/README`, 2026-07-17).
That table's "depth" column is the layer bottom (0.065, 0.319, 1.232, 4.134, 9.834 m), so
the registry uses the midpoints between consecutive bottoms.

## Snippet

`convert.py:36-38`:

```python
# Layer middles [m] from the bucket README's 5-layer table, whose "depth" column is the
# layer bottom (0.065, 0.319, 1.232, 4.134, 9.834). The files carry bare indices.
_SOIL_LAYER_DEPTHS = (0.0325, 0.192, 0.7755, 2.683, 6.984)
```

`convert.py:133-136`, in `read()`:

```python
if variable in self.LAYERED_VARIABLES:
    da = da.assign_coords(
        layer=("layer", list(_SOIL_LAYER_DEPTHS), {"units": "m"})
    )
```

`WIEFile._standardize_layers` (`core.py:696`) then renames `layer` to `soil`, requires
`units == "m"`, pins the values to float64 at 1 µm and checks that they increase.

## Result

Read off the bucket 2026-10-23 (`JSBACH_stable_bgc`):

| variable | file level dim | `soil` [m] |
|---|---|---|
| soilT | `layer` (5, no coord) | 0.0325, 0.192, 0.7755, 2.683, 6.984 |
| mrsoLayer | `layer` (5, no coord) | same as soilT |
