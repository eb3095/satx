# SatX

**SatX** is a terminal-based satellite and ISM monitoring app for SDR backends on macOS. Switch between four live dashboards from one Rich terminal UI.

```
 __       _  __  __
/ _\ __ _| |_\ \/ /
\ \ / _` | __|\  / 
_\ \ (_| | |_ /  \ 
\__/\__,_|\__/_/\_\
                   
```

## Features

- **APT (A)** — NOAA weather satellites near 137 MHz with WFM demod, 2400 Hz line sync detection, grayscale image preview, and PNG export to `~/.satx/images/`
- **LRPT (L)** — METEOR satellites near 137 MHz with signal level, digital energy metrics, and event logging (full LRPT image decode is complex; use external **satdump** if installed)
- **ISM (I)** — 433 MHz ISM band via **rtl_433** with HackRF piping or direct RTL-SDR (`-d 0`)
- **Sat Radio (R)** — ISS and amateur satellite NBFM voice with squelch, waveform scope, speaker audio, and optional local STT

Config auto-created at `~/.config/satx/config.json`. Logs written to `~/.satx/logs/`.

## Requirements

- macOS
- Python 3.11+
- One SDR backend:
  - HackRF (`hackrf_transfer`)
  - RTL-SDR (`rtl_sdr`)

```bash
brew install hackrf
# or:
brew install rtl-sdr
```

**rtl_433** and **satdump** are separate native Homebrew apps — they are not Python packages and are not installed by `pip` or `make dev-install`. SatX shells out to them for the ISM and LRPT dashboards.

Install all SDR tools (runs automatically with `make dev-install` / `make install`):

```bash
make deps
# installs: hackrf, rtl-sdr, rtl_433, satdump
```

Or individually:

```bash
brew install rtl_433      # ISM dashboard (433 MHz sensors)
brew install satdump      # external METEOR LRPT image decode
```

Python extras (STT + speaker audio) are included in satx deps: `faster-whisper`, `sounddevice`.

## Live image preview

On **APT** and **LRPT** dashboards, SatX shows a braille preview in the terminal and opens **Preview.app** on macOS (refreshes as lines or waterfall data arrive). The Rich terminal UI keeps running — press **`s`** to save a PNG to `~/.satx/images/` (APT only when the pass image is complete; LRPT when a pass is detected). Completed APT images auto-save as `apt_{channel}_{timestamp}.png`; LRPT manual saves use `lrpt_{channel}_{timestamp}.png`.

## Quick Start

```bash
cd satx
make dev-install
./start.sh
```

Entry points:

- `python -m satx`
- `./start.sh`
- `satx` (after `make install` or `make dev-install`)

## Configuration

SatX stores config in `~/.config/satx/config.json` and creates defaults on first run.

| Key | Type | Default | Description |
|---|---|---|---|
| `backend` | string | `"auto"` | SDR backend: `"auto"`, `"hackrf"`, or `"rtlsdr"` |
| `lna` | int | `32` | HackRF LNA gain (HackRF backend) |
| `vga` | int | `48` | HackRF VGA gain (HackRF backend) |
| `amp_enable` | bool | `true` | Enable HackRF RF amp (HackRF backend) |
| `tuner_gain` | int | `40` | RTL-SDR tuner gain in dB (RTL-SDR backend) |
| `ppm_error` | int | `0` | RTL-SDR ppm correction (RTL-SDR backend) |
| `sound_enabled` | bool | `true` | Enable sound notifications |
| `refresh_hz` | float | `2.0` | UI refresh frequency |
| `show_banner` | bool | `true` | Show startup banner |
| `replay_file` | string/null | `null` | Optional IQ replay file path |
| `apt_channels` | list | NOAA 15/18/19 | APT channel list (`id`, `name`, `freq_mhz`, `description`) |
| `lrpt_channels` | list | METEOR M2/M2-2 | LRPT channel list |
| `ism_freq_mhz` | float | `433.92` | ISM center frequency |
| `sat_radio_channels` | list | ISS/SO-50/etc. | Satellite voice channel list |

Default **APT** channels:

- NOAA 15 — `137.620` MHz
- NOAA 18 — `137.9125` MHz
- NOAA 19 — `137.100` MHz

Default **LRPT** channels:

- METEOR M2 — `137.900` MHz
- METEOR M2-2 — `137.900` MHz

Default **sat radio** channels:

- ISS Voice — `145.800` MHz
- ISS APRS — `145.825` MHz
- SO-50 — `436.795` MHz
- AO-91 — `435.250` MHz
- AO-92 — `437.715` MHz
- FO-29 — `145.950` MHz

## Keyboard Shortcuts

Global:

- `A` — APT dashboard
- `L` — LRPT dashboard
- `I` — ISM dashboard
- `R` — Satellite radio dashboard
- `Ctrl+C` — quit (fast teardown; second press force-exits)

APT / LRPT:

- `↑` / `↓` — select channel
- `g` / `G` — channel page up/down
- `s` — save PNG (or use Save in the live image window)

Satellite radio:

- `↑` / `↓` — select channel
- `g` / `G` — channel page up/down
- `[` / `]` — squelch down/up
- `-` / `+` — volume down/up

## Development

```bash
make dev-install
make format
make test
```

CI runs:

- `black --check`
- `pytest`
- Python `3.11`, `3.12`, and `3.13`

## License

MIT — Copyright (c) Eric Benner
