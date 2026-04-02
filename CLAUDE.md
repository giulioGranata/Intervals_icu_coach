# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

**Intervals ICU Coach** fetches endurance training data from the [Intervals.icu](https://intervals.icu) API and computes Section 11 AI coaching metrics, writing structured JSON files that AI systems can consume to give evidence-based coaching recommendations.

## Running the Sync

```bash
pip install requests

# Local run
python sync.py --athlete-id i153108 --intervals-key YOUR_KEY

# Optional flags
python sync.py --athlete-id ... --intervals-key ... --days 7 --output-dir ./output
```

The GitHub Actions workflow (`.github/workflows/auto-sync.yml`) runs this automatically every 15 minutes using `ATHLETE_ID` and `INTERVALS_KEY` repository secrets.

## Architecture

Everything lives in a single file: **`sync.py`** (~810 lines, one class: `IntervalsSync`).

**Data flow:**

```
Intervals.icu API
  → fetch phase   (athlete, 84d activities, 42d wellness, 42d events, FTP history)
  → compute phase (see metrics below)
  → output phase  (latest.json, history.json, ftp_history.json)
  → GitHub Actions auto-commits every 15 min
  → AI coaches read the JSON + SECTION_11.md + DOSSIER.md
```

**Key methods:**

| Method | Purpose |
|---|---|
| `collect_and_save()` | Orchestrates the full pipeline |
| `build_latest_json()` | 7-day snapshot with all current metrics & alerts |
| `build_history_json()` | 84-day time series (TSS, HRV, RHR, CTL/ATL/TSB) |
| `compute_recovery_index()` | `RI = (HRV_today/HRV_baseline) ÷ (RHR_today/RHR_baseline)` |
| `compute_acwr()` | Acute (7d) / Chronic (28d) workload ratio |
| `compute_monotony_strain()` | Foster overuse indices (7-day window) |
| `compute_tid()` | Training Intensity Distribution — Seiler 3-zone model, Treff PI |
| `compute_ctl_atl_tsb()` | Banister impulse-response model |
| `compute_readiness()` | P0/P1/P2/P3 decision ladder |
| `detect_phase()` | Dual-stream phase detection (CTL slope + race calendar, 8 phases) |
| `generate_alerts()` | Threshold-based alerts |

## Key Documents

- **`SECTION_11.md`** — The AI coaching protocol spec (v11.24). Defines signal thresholds, the P0–P3 readiness ladder, phase detection logic, TID classification, and 10 non-negotiable AI behavior rules.
- **`DOSSIER_TEMPLATE.md`** — Template for the personal athlete profile (`DOSSIER.md`). AI coaches load this alongside `latest.json` to make coaching decisions.

## Output Files

| File | Contents |
|---|---|
| `latest.json` | 7-day snapshot: current metrics, alerts, readiness decision |
| `history.json` | 84-day time series |
| `ftp_history.json` | FTP tracking history |
| `archive/YYYY-MM/timestamp.json` | Timestamped backups (auto-created by CI) |

`DOSSIER.md` and all JSON outputs are gitignored by default (private athlete data).

## Section 11 Readiness Ladder

| Priority | Condition | Decision |
|---|---|---|
| P0 | RI < 0.6 | Skip (non-negotiable) |
| P1 | ACWR > 1.5 or (TSB < −30 AND HRV ↓ > 10%) | Skip |
| P2 | ≥ 2 red signals | Modify session |
| P3 | All signals within range | Go |

## Credentials

Never commit `.env`. Credentials live in GitHub Secrets (`ATHLETE_ID`, `INTERVALS_KEY`) or a local `.env` file (see `.env.example`).
