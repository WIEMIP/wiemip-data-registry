# LPJ-EOSIM soil layer depths

`read()` returns `soilT`, `soilIce` and `soilMoist` on a `soil` axis of depths in m.

## Source

The files carry bare integer indices: `pool` on soilT, `layer` = 0-7 on soilIce and
soilMoist.

- **soilT** holds point temperatures, so its depths are point depths, not layer middles.
  They come from LPJ's output names `mtsoil_0` … `mtsoil_200` (cm). The 1pctCO2 upload
  (2026-09-16) has 9 `pool` levels: a 0-50 cm mean (`mtsoil_top`) first, which the
  adapter drops. The overshoot upload (2026-10-16) has only the 8 point temperatures.
- **soilIce, soilMoist** are per layer. Their depths are the middles of LPJ's `Dz_soil`
  (`permafrost.c`: 100, 100, 100, 200, 200, 300, 500, 500 mm).

## Snippet

`convert.py:16-17`:

```python
_SOIL_T_DEPTHS = (0.0, 0.1, 0.25, 0.5, 0.7, 1.0, 1.5, 2.0)
_SOIL_LAYER_DEPTHS = (0.05, 0.15, 0.25, 0.4, 0.6, 0.85, 1.25, 1.75)
```

`convert.py:82-90`, in `read()`:

```python
if variable == "soilT":
    # the 2026-09-16 1pctCO2 upload leads with a 0-50 cm mean; overshoot doesn't
    if da.sizes["pool"] == len(_SOIL_T_DEPTHS) + 1:
        da = da.isel(pool=slice(1, None))
    da = da.assign_coords(pool=("pool", list(_SOIL_T_DEPTHS), {"units": "m"}))
elif variable in self.LAYERED_VARIABLES:
    da = da.assign_coords(
        layer=("layer", list(_SOIL_LAYER_DEPTHS), {"units": "m"})
    )
```

`WIEFile._standardize_layers` (`core.py:696`) then renames `pool` / `layer` to `soil`,
requires `units == "m"`, pins the values to float64 at 1 µm and checks that they
increase.

## Result

Read off the bucket 2026-10-23:

| variable | run read | file level dim | `soil` [m] |
|---|---|---|---|
| soilT | 1pctCO2 `stable_bgc`, `ukesm_cou` | `pool` (0-8, first dropped) | 0.0, 0.1, 0.25, 0.5, 0.7, 1.0, 1.5, 2.0 |
| soilT | overshoot `ukesm_hl` | `pool` (0-7) | same as 1pctCO2 soilT |
| soilIce | 1pctCO2 `stable_bgc` | `layer` (0-7) | 0.05, 0.15, 0.25, 0.4, 0.6, 0.85, 1.25, 1.75 |
| soilMoist | 1pctCO2 `stable_bgc` | `layer` (0-7) | same as soilIce |
