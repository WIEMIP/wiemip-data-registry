# ELM soil layer depths

`read()` returns `soilT`, `soilTemp`, `soilIce`, `soilMoist`, `mrsoLayer`, `soilRh`,
`rhLayers`, `cSoilLayers`, `nOrgSoilLayer` and `nInorgSoilLayer` on a `soil` axis of
depths in m. Only the 2026-10-19 baseline rerun and the 2026-10-25 nofire rerun (1pctCO2
bgc, ctrl, ukesm cou, ukesm rad) uploaded them.

## Source

The files ship ELM's own level coordinates in m (`long_name = "coordinate soil levels"`),
with no bounds: `levgrnd` on soilT, soilTemp, soilIce, soilMoist and mrsoLayer, `levdcmp`
on soilRh, rhLayers, cSoilLayers, nOrgSoilLayer and nInorgSoilLayer. Both hold the same
15 float32 node depths. The adapter carries the same 15 values as `_SOIL_LAYER_DEPTHS`
and assigns them on read, so a file with a different level count fails loudly.

The top 10 levels (nodes down to 2.86 m) are soil. Levels 11-15 are bedrock: in the first bgc
step they hold no soil carbon and at most 0.04 kg m⁻² of water.

## Snippet

`convert.py:21-39`:

```python
# node depths [m] of the 15 levels on both `levgrnd` and `levdcmp`; carbon sits in the
# top 10, levels 11-15 are bedrock
_SOIL_LAYER_DEPTHS = (
    0.007101, 0.027925, 0.062259, 0.118865, 0.212193,
    0.366066, 0.619758, 1.038027, 1.727635, 2.864607,
    4.739157, 7.829766, 12.925321, 21.326469, 35.17762,
)
```

`convert.py:131-135`, in `read()`:

```python
if variable in self.LAYERED_VARIABLES:
    level = "levdcmp" if "levdcmp" in da.dims else "levgrnd"
    da = da.assign_coords(
        {level: (level, list(_SOIL_LAYER_DEPTHS), {"units": "m"})}
    )
```

`convert.py:50`:

```python
LAYERED_VARIABLES = {
    "soilT",
    "soilTemp",
    "soilIce",
    "soilMoist",
    "mrsoLayer",
    "soilRh",
    "rhLayers",
    "cSoilLayers",
    "nOrgSoilLayer",
    "nInorgSoilLayer",
}
```

`WIEFile._standardize_layers` (`core.py:696`) then renames `levgrnd` / `levdcmp` to
`soil`, requires `units == "m"`, pins the values to float64 at 1 µm and checks that they
increase.

## Result

Read off the bucket 2026-10-23 (`stable_bgc`). Every variable comes back on the same 15
depths: 0.007101, 0.027925, 0.062259, 0.118865, 0.212193, 0.366066, 0.619758, 1.038027,
1.727635, 2.864607, 4.739157, 7.829766, 12.925321, 21.326469, 35.17762 m.

| variable | file level dim |
|---|---|
| soilT | `levgrnd` |
| soilTemp | `levgrnd` |
| soilIce | `levgrnd` |
| soilMoist | `levgrnd` |
| mrsoLayer | `levgrnd` |
| soilRh | `levdcmp` |
| rhLayers | `levdcmp` |
| cSoilLayers | `levdcmp` |
| nOrgSoilLayer | `levdcmp` |
| nInorgSoilLayer | `levdcmp` |
