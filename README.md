# BLANCO Smart Home Cloud for Home Assistant

An independent, read-only Home Assistant custom integration for the BLANCO
Smart Home API. It is intended as a bridge until BLANCO's proposed native Home
Assistant integration is released.

The integration does **not** ask for or store BLANCO account credentials. The
BLANCO UNIT app grants a device-specific connection through RCA (Request Cloud
Access). The service code is used once to derive the cloud device ID and is not
stored by the integration.

## Features

- Cloud connection and last-online state
- Critical-error and warning counters with bounded error details
- Filter and CO₂ capacity for supported devices
- Cold- and hot-water target temperatures where available
- CHOICE.ALL absence and hot-water mode states
- Last dispense and aggregate water use for API-supported devices
- Redacted diagnostics for discovering additional fields safely
- Automatic token renewal and a Home Assistant reauthentication flow
- German and English UI

All entities are read-only. This repository contains no dispense, hot-water,
reset, firmware, or settings write operations.

## Known device scope

BLANCO currently documents Smart Home API access for CHOICE.ALL, EVOL-S PRO
SODA revision F or later, and AQUA UVC-AC. The API itself decides whether a
particular serial number and device type is eligible.

Water-action and aggregate-statistics endpoints are less mature than the basic
status endpoints. They are polled only every 15 minutes and fail independently;
a failure cannot take the normal device sensors down. The "last dispense"
lookup is intentionally limited to the previous 30 days to avoid an expensive
full-history scan.

## Requirements

- Home Assistant 2026.8.3 or newer
- A supported BLANCO device connected to Wi-Fi/BLANCO Cloud
- BLANCO UNIT on an iPhone or Android phone
- The device serial number
- The Smart Home service code shown by BLANCO UNIT

## Manual installation

1. Copy `custom_components/blanco_smart_home` into Home Assistant's
   `/config/custom_components/` directory.
2. Restart Home Assistant.
3. In BLANCO UNIT, stand near the device and open its settings.
4. Open **Smart Home** and activate **RCA**.
5. Within five minutes, in Home Assistant open **Settings → Devices & services
   → Add integration** and select **BLANCO Smart Home Cloud**.
6. Enter the serial number and service code exactly as displayed. Leading
   zeroes matter.

Treat the serial number and service code like credentials. Do not post them in
an issue, log, screenshot, or chat.

## HACS installation

Once this repository has been published on GitHub, add its URL in HACS as a
custom **Integration** repository and install **BLANCO Smart Home Cloud**.

## Troubleshooting and safe diagnostics

- `Access was not granted`: activate RCA again while the phone is in Bluetooth
  range, then retry within five minutes.
- `Device type not supported`: the BLANCO cloud has not enabled this model or
  revision for Smart Home access.
- Missing consumption entities do not imply that basic status failed; the
  history endpoints are optional and tracked separately.
- From the BLANCO device page in Home Assistant, choose **Download diagnostics**
  to capture the API response. Tokens, device IDs, serial/network identifiers,
  and service-code-like fields are redacted. Review the file once more before
  sharing it because new firmware may add fields unknown to this integration.

## Polling

- System, status, and errors: every 60 seconds
- Settings, recent actions, and aggregate statistics: every 15 minutes

The integration retains the last value for an endpoint after a transient cloud
failure, but marks entities sourced from that endpoint unavailable rather than
showing a misleading zero.

## Relationship to the proposed native integration

Home Assistant's proposed integration uses the domain `blanco`. This custom
integration deliberately uses `blanco_smart_home`, so both can coexist during
testing. When the native integration is released, remove this custom integration
before adding the native one to avoid duplicate devices and API traffic.

## Upstream and attribution

This project builds on:

- [BLANCO Smart Home API client](https://github.com/blancoGDPD/blanco-smart-home-api-client)
- [Proposed Home Assistant BLANCO integration](https://github.com/home-assistant/core/pull/168250)
- [Proposed Home Assistant documentation](https://github.com/home-assistant/home-assistant.io/pull/44785)

The Home Assistant integration patterns adapted here are provided under the
Home Assistant project's Apache License 2.0. The BLANCO API client is MIT
licensed and installed as a dependency from PyPI.

## Development

Run the dependency-free helper tests:

```bash
python -m unittest discover -s tests
```

The repository workflow additionally runs HACS validation and hassfest.

## License

Apache License 2.0. This project is independent and is not an official BLANCO
support channel.
