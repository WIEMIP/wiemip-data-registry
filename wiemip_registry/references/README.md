# `references/` — committed virtualizarr / kerchunk sidecars

Small JSON sidecars (one per WIE-MIP `.nc` file) describing the byte ranges /
chunk layout of the raw netCDFs in s3. `WIEFile.read()` opens through these
virtual-zarr references instead of re-opening raw netCDF, so reads are:

- **lazy + chunk-aligned**, and
- **usable off the box** (from the Mac via s3 creds, not the s3fs mount).

The model's `convert.py:s3_path()` resolves *which* raw file a coordinate maps
to (the upload naming conventions differ per model and don't matter to callers);
the reference here is what `read()` actually opens.

## TODO (not yet wired)
- Build the references (`virtualizarr` / `kerchunk`) over the raw netCDFs and
  commit the sidecars here, mirroring the bucket tree.
- Point `core.WIEFile.read()` at the sidecar when one exists, falling back to the
  s3fs path otherwise.
- Record the bucket snapshot the references were built against, so a registry
  version maps to a known data state (PLAN.md §Versioning).

This directory is intentionally committed (kept by `.gitkeep` until sidecars land).
