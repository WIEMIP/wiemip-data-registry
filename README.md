# WIEMIP variable registry

This repository contains scripts to map each model's submission to a standard WIEMIP format.
Each model gets its own directory under wiemip_registry/MODEL/, within which is a convert.py script
that implements the class in wiemip_registry/core.py: the `WIEAdapter`. This class has methods
to read a file from `S3` by transforming the standardized WIEMIP variable request into a model-specific one.
In addition, it applies the masking specified by each group's uploaded `README` to compute global sums.

Not included is the cloud infrastructure to set this up. Reach out to the WIEMIP team if you're interested in getting
access to the data.

A WIEMIP variable request is structured as follows (and the `Enums` describing this are in `wiemip_registry/const.py`):

```python
import wiemip_registry as wr
# one percent co2; note model, forcing, simulation (bgc, rad, cou, ctrl), and factorial (baseline, noFire, noNitrogen, etc)
classic_cveg = wr.retrieve_one_pct_variable(model="CLASSIC", forcing="ukesm", simulation="cou", factorial="baseline", variable="cVeg")
# and overshoot
overshoot_classic_cveg = wr.retrieve_overshoot_variable(model="CLASSIC", forcing="ukesm", simulation="cou",variable="cVeg")
```
The `.read()` method returns an `xarray.DataArray` in native units that can be transformed as you need.
If you want the result masked to land and scaled by gridcell area, use `.weighted_dataarray()`. You can
cut straight to the chase with `latitudinal_sum()`. Note: these methods construct a path using the `WIEAdapter` object
in `wiemip_registry` and by design throw errors if you ask for a file that 1) doesn't conform to the naming convention
spelled out in the adapter or 2) doesn't exist. 

`latitudinal_sum()` will cache a csv locally when it first runs so that subsequent requests for the same latitude bands
will be faster. It runs again if it detects a difference in the underlying netCDF file. TODO: run latitudinal sums
across the entire dataset and save to S3.


## Adding a new model
Add a new directory following the template in the current model directories. Implement the WIEAdapter API and test it to 
make sure it works on the new data. Add the adapter to `wiemip_registry/adapters.py` to enable imports and lookup
with 
