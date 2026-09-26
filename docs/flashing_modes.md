# Flashing Modes

Android Flasher recognizes three transport modes.

## Bootloader fastboot

The device is in the bootloader. `fastboot devices` reports the
device. Physical partitions (`boot`, `init_boot`, `vendor_boot`,
`dtbo`, `vbmeta`, `super`, `bootloader`, `radio`) can be flashed.

## FastbootD

The device is in fastbootd (userspace fastboot). `fastboot devices`
still reports the device, but logical partitions (`system`,
`system_ext`, `product`, `vendor`, `odm`) can be flashed.

Enter fastbootd with:

fastboot reboot fastboot

text

The planner inserts this step automatically when the plan contains
operations on logical partitions, subject to
`safety.allow_fastbootd_mode_switch`.

## Update

`fastboot update <package>` is used for factory ZIPs and OTA ZIPs
when extraction is disabled. This relies on the package's own flash
script. The planner warns the user that `fastboot update` relies on
package contents and on a compatible fastboot version.

## ADB

ADB is used for read-only identification (`getprop`) and for
`adb reboot bootloader` / `adb reboot fastboot` transitions. ADB is
not used for flashing.

## Slot management

A/B devices expose `current-slot`, `set_active`, and per-slot
successful/unbootable/retry-count variables. Android Flasher defaults
to the current slot. Changing the active slot is disabled by default
via `safety.allow_ab_slot_change`.

## What the engine never does

- It never flashes both slots automatically.
- It never disables AVB unless `flash.allow_avb_disable` is enabled
  and the user confirms.
- It never erases or formats unless the corresponding safety flag is
  enabled.
- It never runs a shell.
