# Supported Devices

Android Flasher is **capability-driven**, not model-driven. Support is
determined by what a device exposes at runtime, combined with firmware
metadata and the profiles under `profiles/`.

No generic application can safely guarantee compatibility with every
Android device. This document describes the *classes* of devices the
application is designed to handle.

## Device classes

### Legacy single-slot fastboot devices

Straightforward partition layout. Physical partitions such as `boot`,
`system`, `vendor`, `recovery`, `userdata`. No slot management.

### A/B fastboot devices

Two slots (`_a`, `_b`) with `current-slot`, `slot-successful`,
`slot-unbootable` and `slot-retry-count` variables.

### A/B devices with dynamic partitions

A `super` partition containing logical partitions: `system`,
`system_ext`, `product`, `vendor`, `odm`. Flashing logical partitions
typically requires fastbootd.

### FastbootD-capable devices

Devices that expose `fastboot reboot fastboot` and accept logical
partition operations in fastbootd mode.

## Compatibility matrix

|                     | Legacy | A/B | Dynamic |
| ------------------- | ------ | --- | ------- |
| Fastboot            | ✓      | ✓   | ✓       |
| FastbootD           | –      | ✓   | ✓       |
| Raw IMG             | ✓      | ✓   | ✓*      |
| Factory ZIP         | varies | ✓   | ✓       |
| Payload             | –      | ✓   | ✓       |
| Slot management     | –      | ✓   | ✓       |

`✓*` indicates that support depends on the specific image and device
architecture.

## Profiles

Device profiles live under `profiles/` and are YAML data files. They
provide hints, not authority: runtime detection always takes
precedence where it is available.

### Adding a device

1. Create a YAML file under `profiles/<manufacturer>/<codename>.yaml`.
2. Record manufacturer, family, codename, slot architecture and
   dynamic-partition support.
3. Do not add model-specific Python logic.

## What this application does not do

- It does not claim to support every Android device.
- It does not install drivers automatically.
- It does not bypass bootloader locks.
- It does not unlock bootloaders.
- It does not flash a device whose compatibility state is `MISMATCH`
  or `BLOCKED`.
