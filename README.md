# Intervals ICU Coach

An AI endurance coaching pipeline built on the **Section 11 Open Protocol**.  
Syncs your training data from [Intervals.icu](https://intervals.icu) and provides structured, science-based coaching input for Claude, ChatGPT, Gemini, Grok, and other AI platforms.

**Last successful sync:** 2026-05-03 20:06:15 UTC

---

## How It Works

```
Intervals.icu ──► sync.py ──► latest.json / history.json ──► AI Coach
                                    │
                              GitHub Actions                  (Claude / ChatGPT /
                              (every 15 min)                   Gemini / Grok …)
```

1. `sync.py` fetches your training data from the Intervals.icu API
2. Computes all Section 11 metrics (RI, ACWR, TID, phase, readiness…)
3. Outputs structured JSON files your AI coach can read
4. GitHub Actions keeps the data fresh every 15 minutes automatically

---

## Repository Structure

```
├── sync.py                        # Data sync & metric computation script
├── SECTION_11.md                  # AI coaching protocol (load into your AI)
├── DOSSIER_TEMPLATE.md            # Athlete profile template
├── DOSSIER.md                     # Your filled-in athlete profile (gitignored)
├── .github/workflows/
│   └── auto-sync.yml              # Automated 15-min sync via GitHub Actions
├── .env.example                   # Example environment variables
├── latest.json                    # Current 7-day snapshot (auto-generated)
├── history.json                   # 84-day longitudinal data (auto-generated)
├── ftp_history.json               # FTP tracking history (auto-generated)
└── archive/                       # Timestamped JSON archives (auto-generated)
```

---

## Setup

### Prerequisites

- [Intervals.icu](https://intervals.icu) account with a connected device (not Strava-only)
- GitHub account (for automated sync) or a local machine (for local sync)

### 1. Get Your Intervals.icu Credentials

1. Log into Intervals.icu
2. Go to **Settings → Developer Settings**
3. Copy your **Athlete ID** (e.g. `i153108`) and **API Key**

### 2. Configure GitHub Secrets

In your GitHub repo → **Settings → Secrets and variables → Actions**, add:

| Secret name | Value |
|-------------|-------|
| `ATHLETE_ID` | Your athlete ID (e.g. `i153108`) |
| `INTERVALS_KEY` | Your API key |

> ⚠️ Never commit your API key to any file in this repository.

### 3. Enable Workflow Permissions

Go to **Settings → Actions → General → Workflow permissions**  
Select **"Read and write permissions"** and save.

### 4. Run Your First Sync

Go to **Actions → Auto-Sync Intervals.icu Data → Run workflow**.

After a successful run you will see `latest.json` and `history.json` in the repo root.

### 5. Build Your Athlete Dossier

Copy `DOSSIER_TEMPLATE.md` to `DOSSIER.md` and fill in your profile.  
Keep it private or commit it to your repo — it is listed in `.gitignore` by default.

---

## Local Sync (no GitHub required)

```bash
# Install dependency
pip install requests

# Set credentials
export ATHLETE_ID=i153108
export INTERVALS_KEY=your_api_key_here

# Run sync
python sync.py
```

Output files (`latest.json`, `history.json`, `ftp_history.json`) will be written to the current directory.

For scheduled local sync on macOS/Linux, add a cron job:

```cron
*/15 * * * * cd /path/to/Intervals_icu_coach && python sync.py >> sync.log 2>&1
```

---

## Connecting to Your AI Coach

### Claude / ChatGPT / Gemini (web chat)

1. Connect your GitHub repo via the platform's GitHub connector
2. Attach `SECTION_11.md` as a file/instruction
3. Attach your `DOSSIER.md` as a file/instruction
4. The AI will read `latest.json` and `history.json` directly from the repo

### Claude Code (agentic)

Open the repo in Claude Code — the session-start hook loads automatically.  
Claude reads `SECTION_11.md`, `DOSSIER.md`, and `latest.json` at startup and delivers the coaching briefing without any manual prompt.

### Using Raw URLs

If your repo is public, you can reference raw file URLs in your AI's system prompt:

```
https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/latest.json
```

---

## JSON Output Schema

### `latest.json`

```json
{
  "generated_at": "2026-01-01T06:00:00Z",
  "protocol_version": "11.24",
  "athlete": { "id": "...", "name": "..." },
  "readiness": {
    "decision": "go | modify | skip",
    "priority": "P0 | P1 | P2 | P3",
    "confidence": "high | medium | low",
    "signals": { "hrv": "green", "rhr": "green", ... },
    "reason": "..."
  },
  "metrics": {
    "ctl": 72.4, "atl": 68.1, "tsb": 4.3,
    "acwr": 0.94, "monotony": 1.7, "strain": 420,
    "recovery_index": 0.97, "hrv_today": 58, "sleep_hours": 7.5
  },
  "phase": { "current": "Build", "confidence": "high" },
  "tid": {
    "28d": { "z1_pct": 79, "z2_pct": 4, "z3_pct": 17, "classification": "Polarized", "pi": 2.5 }
  },
  "alerts": [],
  "recent_activities": [ ... ]
}
```

---

## Science Foundation

Section 11 integrates 19 validated endurance science frameworks including:

- **Seiler** — 80/20 polarized training model
- **Banister** — impulse-response (CTL/ATL/TSB)
- **Gabbett** — ACWR safe-load progression
- **Foster** — monotony and strain indices
- **Treff** — polarization index (TID classification)
- **Coggan** — power-duration model
- **Maunder** — durability and decoupling

See `SECTION_11.md` for the full protocol and evidence base.

---

## Privacy

- Your training data stays in **your** GitHub repository
- No backend, no third-party storage, no telemetry
- API key is stored only in GitHub Secrets (encrypted)
- Credentials never appear in code or committed files

---

## License

MIT — see [LICENSE](LICENSE).  
Protocol based on [Section 11](https://github.com/CrankAddict/section-11) by CrankAddict (MIT).
