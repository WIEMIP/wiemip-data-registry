# CoLM soil layer depths

`read()` returns `soilT`, `soilIce`, `mrsoLayer` and `cSoilLayers` on a `soil` axis of
depths in m.

## Source

Every file ships its own depth coordinate in m: `layer` on soilT, mrsoLayer and
cSoilLayers, `nsoil` on soilIce. The registry uses it as is.

## Snippet

The adapter adds no depths. It only lists the variables (`convert.py:20`):

```python
LAYERED_VARIABLES = {"soilT", "soilIce", "mrsoLayer", "cSoilLayers"}
```

`WIEFile._standardize_layers` (`core.py:696`) then renames `layer` / `nsoil` to `soil`,
requires `units == "m"`, pins the values to float64 at 1 µm and checks that they
increase.

## Result

Read off the bucket 2026-10-23 (`CoLM_stable_bgc`):

| variable | file level dim | `soil` [m] |
|---|---|---|
| soilT | `layer` (15) | 0.007101, 0.027925, 0.062258, 0.118865, 0.212193, 0.366066, 0.619758, 1.038027, 1.727635, 2.864607, 4.739157, 7.829767, 12.92532, 21.326469, 35.17762 |
| soilIce | `nsoil` (15) | same as soilT |
| mrsoLayer | `layer` (15) | same as soilT |
| cSoilLayers | `layer` (15) | same as soilT |
