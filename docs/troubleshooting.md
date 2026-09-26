# Troubleshooting

## Platform Tools missing

**Symptom:** The Platform Tools panel reports `NOT FOUND`.

**Cause:** `adb` and/or `fastboot` are not on PATH and not bundled.

**Fix:** Install Android SDK Platform Tools. Either add them to PATH
or place them under `platform-tools/` inside the project.

## Device unauthorized (ADB)

**Symptom:** `adb devices` reports `unauthorized`.

**Fix:** Unlock the device, accept the USB debugging prompt on the
device, and re-run detection.

## Multiple devices

**Symptom:** Detection reports `MULTIPLE_DEVICES`.

**Cause:** More than one device is connected.

**Fix:** Disconnect all but the intended device. The application
refuses to guess.

## Firmware malformed

**Symptom:** Firmware analysis fails or the detector reports
`UNREADABLE`.

**Cause:** The file is truncated, corrupt, or not the format its
extension claims.

**Fix:** Re-download the firmware from the vendor. Verify its
published hash.

## Firmware mismatch

**Symptom:** Compatibility matrix shows `MISMATCH` or `BLOCKED`.

**Cause:** The firmware codename or product does not match the
connected device.

**Fix:** Use firmware intended for the connected device. Do not
attempt to bypass this check.

## Unsupported operation

**Symptom:** A plan is blocked with "operation not supported".

**Cause:** The device does not expose the required capability, or the
safety settings do not permit the operation.

**Fix:** Review the Blockers and Warnings panel in the Flash Plan tab.

## Locked bootloader

**Symptom:** Preflight reports "Bootloader is locked."

**Cause:** The device bootloader is locked.

**Fix:** Unlocking the bootloader is a device-specific manual process.
This application does not unlock bootloaders.

## Missing partition

**Symptom:** Preflight reports a partition is not present in the
device model.

**Cause:** The firmware targets a partition the device does not have.

**Fix:** Use firmware that matches the device. Do not force the
operation.

## Unsupported capability

**Symptom:** A plan requires fastbootd or dynamic partition support
that the device does not report.

**Fix:** Verify the device is in the correct mode, or use a different
firmware package.

## Command timeout

**Symptom:** A step reports `TIMEOUT`.

**Cause:** The command did not complete within the configured timeout.

**Fix:** Check the cable and port. Increase `flash.step_timeout_seconds`
in `config.yaml` if the device is known to be slow.

## Command failure

**Symptom:** A step reports `FAILED` with a nonzero exit code.

**Cause:** fastboot rejected the operation.

**Fix:** Review the command output in the Log tab. Do not immediately
retry destructive operations; diagnose first.

## Verification failure

**Symptom:** The Verification report shows `FAILED`.

**Cause:** One or more steps failed, timed out, or were cancelled.

**Fix:** Review the execution trace. The device may be in an
intermediate state.

## Verifying the safety net

Before any destructive operation, the application runs:

1. Device detected?
2. Correct transport?
3. Correct serial?
4. Firmware identified?
5. Compatibility checked?
6. Partition exists?
7. Slot architecture understood?
8. Bootloader permits the operation?
9. Capabilities satisfied?
10. Integrity recorded?
11. Risk assessed?
12. User confirmation obtained?

If any of these fail, the operation is blocked and reported.
