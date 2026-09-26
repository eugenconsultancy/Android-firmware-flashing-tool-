# Test Fixtures

This directory holds static test fixtures used by Phase 1, 2 and 3
tests. Fixtures are deliberately tiny and contain only synthetic data.

## Files

- `fastboot_devices.txt` — synthetic output of `fastboot devices`.
- `fastboot_getvar_all_pixel.txt` — synthetic `fastboot getvar all`
  output for an A/B dynamic-partition device.
- `fastboot_getvar_all_ab.txt` — synthetic `fastboot getvar all`
  output for a simpler A/B device.

## Guidelines

1. Never add real device firmware.
2. Never add proprietary images.
3. Keep each fixture under a few KB.
4. Document the fixture's purpose here when adding a new one.
