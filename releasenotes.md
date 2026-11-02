# Release Notes

## v0.2.0-dev

Released on xx/xx/xxxx.

- Made binary and multistate variable conversions between test runner and device two-way.  This is for [#46](https://github.com/LBNL-ETA/guideline36_conformance_test/issues/46).
- Fixed `assert_output` to check all expected output cases, including relational operators (e.g., `>50`, `<=71`) and numbers stored as text, by introducing a shared `_parse_expected_value` helper used by both `assert_output` and `test_conditions`.  This is for [#62](https://github.com/LBNL-ETA/guideline36_conformance_test/issues/62).


## v0.1.0

Released on 10/1/2026.

This is an initial development release.