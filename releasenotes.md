# Release Notes

## v0.2.0-dev

Released on xx/xx/xxxx.

- Made binary and multistate variable conversions between test runner and device two-way.  This is for [#46](https://github.com/LBNL-ETA/guideline36_conformance_test/issues/46).
- Added persistent testing across test blocks (skipping the remainder of a failed block and continuing with subsequent blocks), `start_block` and `single_block` configuration options, and `test_block`/`test_step` columns in result CSVs (with `step` renamed to `marker` in `*_test_times.csv` and corresponding visualization updates).  This is for [#60](https://github.com/LBNL-ETA/guideline36_conformance_test/issues/60).


## v0.1.0

Released on 10/1/2026.

This is an initial development release.