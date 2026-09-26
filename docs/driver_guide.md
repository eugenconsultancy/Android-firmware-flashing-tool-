# Driver Guide

Driver problems are the most common cause of "device not detected".
This guide explains how Android Flasher helps.

## What the application detects

- Whether `adb` and `fastboot` are visible on `PATH` or bundled.
- Whether the platform tools respond to `--version`.
- Whether a device is visible to `adb devices` and `fastboot devices`.

The application **does not install drivers**. Installing system drivers
requires elevated privileges and a deliberate user decision.

## Windows

Install the appropriate OEM USB driver:

- Google devices: Google USB Driver.
- Samsung: Samsung Android USB Driver.
- Xiaomi: Mi USB Driver.
- Motorola: Motorola USB Driver.
- OnePlus: Google USB Driver usually works.

Then install Android SDK Platform Tools.

If `fastboot devices` returns nothing while the device is physically
connected and in bootloader mode, the fastboot interface is not bound
to a driver. Reinstall the OEM driver and reconnect.

## Linux

There is no driver in the Windows sense. The relevant configuration
is udev rules and group membership.

Typical udev rules grant access to vendor `18d1` (Google) and other
Android vendors. Ensure your user is in `plugdev` or a similar group.

If `fastboot devices` requires `sudo`, udev rules are missing or too
restrictive. Do not run the application as root; fix the udev rules.

## macOS

macOS does not require OEM drivers. The first time a terminal
application accesses a USB device, macOS may prompt for permission.

## Diagnostics

When a device is not detected, Android Flasher reports:

- whether adb and fastboot are on PATH
- what detection state was reached
- guidance to check cable, port, hubs, and driver installation

Technical details are always available in the Log tab.
