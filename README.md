# WIEMIP variable registry

This repository contains scripts to map each model's submission to a standard WIEMIP format.
Each model gets its own directory under wiemip_registry/MODEL/, within which is a convert.py script
that implements the class in wiemip_registry/core.py: the `WIEAdapter`. This class has methods
to read a file from `S3` by transforming the standardized WIEMIP variable request into a model-specific one.
In addition, it applies the masking specified by each group's uploaded `README` to compute global sums.

A WIEMIP variable request is structured as follows (and the `Enums` describing this are in `wiemip_registry/const.py`):

```python
import wiemip_registry as wr
# one percent co2 or overshoot, model (CLASSIC in this case), gcm pattern (ukesm, ipsl, gfdl),
# simulation (cou, bgc, rad, ctrl), factorial (baseline, noFire, etc), and finally variable
classic_cveg = wr.one_percent_co2.CLASSIC.ukesm.cou.baseline.cVeg.read()
```
The `.read()` method returns an `xarray.DataArray` in native units that can be transformed as you need.
If you want the result masked to land and scaled by gridcell area, use `.weighted_dataarray()`. You can
cut straight to the chase with `latitudinal_sum()`. 

