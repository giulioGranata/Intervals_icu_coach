#!/usr/bin/env python3
"""
Intervals.icu → JSON Sync Script
Section 11 Open Protocol for AI Endurance Coaching
Version 3.95 | MIT License | https://github.com/CrankAddict/section-11
"""

import argparse
import base64
import datetime
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library not found. Run: pip install requests")
    sys.exit(1)

VERSION = "3.95"
PROTOCOL_VERSION = "11.24"
BASE_URL = "https://intervals.icu/api/v1"


class IntervalsSync:
    """Data pipeline for the Section 11 AI Endurance Coaching Protocol."""

    def __init__(self, athlete_id: str, api_key: str, days: int = 7):
        self.athlete_id = athlete_id
        self.days = days
        self.session = requests.Session()
        creds = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
        self.session.headers.update({
            "Authorization": f"Basic {creds}",
            "Accept": "application/json",
        })

    # ── API helpers ────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict = None) -> Any:
        url = f"{BASE_URL}/{path}"
        r = self.session.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def _date_range(self, days_back: int):
        end = datetime.date.today()
        start = end - datetime.timedelta(days=days_back)
        return start.isoformat(), end.isoformat()

    # ── Data fetchers ──────────────────────────────────────────────────────────

    def fetch_athlete(self) -> dict:
        return self._get(f"athlete/{self.athlete_id}")

    def fetch_activities(self, days_back: int = 84) -> list:
        oldest, newest = self._date_range(days_back)
        fields = (
            "id,name,type,sport_type,start_date_local,moving_time,distance,"
            "average_watts,normalized_watts,icu_weighted_avg_watts,icu_average_watts,"
            "average_heartrate,max_heartrate,"
            "tss,icu_training_load,icu_atl,icu_ctl,icu_tsb,"
            "icu_zone_times,icu_hr_zone_times,calories,"
            "total_elevation_gain,average_speed,average_cadence"
        )
        data = self._get(
            f"athlete/{self.athlete_id}/activities",
            {"oldest": oldest, "newest": newest, "fields": fields},
        )
        return data if isinstance(data, list) else []

    def fetch_wellness(self, days_back: int = 42) -> list:
        oldest, newest = self._date_range(days_back)
        data = self._get(
            f"athlete/{self.athlete_id}/wellness",
            {"oldest": oldest, "newest": newest},
        )
        return data if isinstance(data, list) else []

    def fetch_events(self, days_ahead: int = 42) -> list:
        start = datetime.date.today().isoformat()
        end = (datetime.date.today() + datetime.timedelta(days=days_ahead)).isoformat()
        data = self._get(
            f"athlete/{self.athlete_id}/events",
            {"oldest": start, "newest": end},
        )
        return data if isinstance(data, list) else []

    def fetch_ftp_history(self) -> list:
        try:
            data = self._get(f"athlete/{self.athlete_id}/ftp")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    # ── Metric computation ─────────────────────────────────────────────────────

    def compute_recovery_index(self, wellness: list) -> dict:
        """
        Section 11 Recovery Index.
        RI = (HRV_today / HRV_baseline) ÷ (RHR_today / RHR_baseline)
        Baseline = 7-day rolling mean (days 2–8, excludes today).
        """
        if not wellness:
            return {
                "ri": None, "hrv_today": None, "hrv_baseline": None,
                "rhr_today": None, "rhr_baseline": None, "sleep_hours": None,
            }

        sorted_w = sorted(wellness, key=lambda x: x.get("id", ""), reverse=True)
        today_w = sorted_w[0]

        hrv_today = today_w.get("hrv") or today_w.get("hrvSDNN")
        rhr_today = today_w.get("restingHR")
        sleep_secs = today_w.get("sleepSecs") or today_w.get("sleepSeconds") or 0
        sleep_hours = round(sleep_secs / 3600, 1) if sleep_secs else None

        baseline_w = sorted_w[1:8]
        hrv_values = [w.get("hrv") or w.get("hrvSDNN") for w in baseline_w
                      if (w.get("hrv") or w.get("hrvSDNN"))]
        rhr_values = [w.get("restingHR") for w in baseline_w if w.get("restingHR")]

        hrv_baseline = sum(hrv_values) / len(hrv_values) if hrv_values else None
        rhr_baseline = sum(rhr_values) / len(rhr_values) if rhr_values else None

        ri = None
        if hrv_today and hrv_baseline and rhr_today and rhr_baseline and rhr_baseline > 0:
            ri = round((hrv_today / hrv_baseline) / (rhr_today / rhr_baseline), 3)

        return {
            "ri": ri,
            "hrv_today": hrv_today,
            "hrv_baseline": round(hrv_baseline, 1) if hrv_baseline else None,
            "rhr_today": rhr_today,
            "rhr_baseline": round(rhr_baseline, 1) if rhr_baseline else None,
            "sleep_hours": sleep_hours,
        }

    def compute_acwr(self, activities: list) -> dict:
        """
        Gabbett's Acute-to-Chronic Workload Ratio.
        Acute = 7-day mean daily load, Chronic = 28-day mean daily load.
        Optimal range: 0.8–1.3.
        """
        today = datetime.date.today()
        load_by_date: dict[str, float] = defaultdict(float)
        for act in activities:
            d = act.get("start_date_local", "")[:10]
            tss = act.get("tss") or act.get("icu_training_load") or 0
            load_by_date[d] += tss

        acute_loads, chronic_loads = [], []
        for i in range(28):
            d = (today - datetime.timedelta(days=i)).isoformat()
            load = load_by_date.get(d, 0)
            chronic_loads.append(load)
            if i < 7:
                acute_loads.append(load)

        acute = sum(acute_loads) / 7 if acute_loads else 0
        chronic = sum(chronic_loads) / 28 if chronic_loads else 0
        acwr = round(acute / chronic, 3) if chronic > 0 else None

        return {
            "acwr": acwr,
            "acute_load_7d": round(acute, 1),
            "chronic_load_28d": round(chronic, 1),
        }

    def compute_monotony_strain(self, activities: list) -> dict:
        """
        Foster's Monotony and Strain indices (7-day window).
        Monotony = mean(daily_load) / std(daily_load)
        Strain = monotony × weekly_load
        Warning ≥2.3, Alarm ≥2.5.
        """
        today = datetime.date.today()
        load_by_date: dict[str, float] = defaultdict(float)
        for act in activities:
            d = act.get("start_date_local", "")[:10]
            tss = act.get("tss") or act.get("icu_training_load") or 0
            load_by_date[d] += tss

        daily = [load_by_date.get((today - datetime.timedelta(days=i)).isoformat(), 0)
                 for i in range(7)]

        weekly_load = sum(daily)
        mean_load = weekly_load / 7
        variance = sum((x - mean_load) ** 2 for x in daily) / 7
        std_load = math.sqrt(variance)

        monotony = round(mean_load / std_load, 2) if std_load > 0 else None
        strain = round(monotony * weekly_load, 1) if monotony else None

        return {
            "monotony": monotony,
            "strain": strain,
            "weekly_load": round(weekly_load, 1),
        }

    def compute_tid(self, activities: list, days: int = 28) -> dict:
        """
        Training Intensity Distribution — Seiler 3-zone model.
        Maps Coggan 7-zones: Z1-Z2 → S-Z1, Z3-Z4 → S-Z2, Z5-Z7 → S-Z3.
        Treff PI = log10((Z1/Z2) × Z3).
        5-class classifier: Base, Polarized, Pyramidal, Threshold, High Intensity.
        """
        today = datetime.date.today()
        cutoff = (today - datetime.timedelta(days=days)).isoformat()
        z1 = z2 = z3 = 0

        def _zt_val(v):
            if isinstance(v, dict):
                return v.get("secs") or v.get("seconds") or v.get("time") or 0
            return v or 0

        for act in activities:
            if act.get("start_date_local", "")[:10] < cutoff:
                continue
            zt = act.get("icu_zone_times") or act.get("icu_hr_zone_times") or []
            if not zt:
                continue
            if len(zt) >= 7:
                z1 += _zt_val(zt[0]) + _zt_val(zt[1])
                z2 += _zt_val(zt[2]) + _zt_val(zt[3])
                z3 += sum(_zt_val(v) for v in zt[4:7])
            elif len(zt) == 3:
                z1 += _zt_val(zt[0])
                z2 += _zt_val(zt[1])
                z3 += _zt_val(zt[2])

        total = z1 + z2 + z3
        if total == 0:
            return {
                "z1_pct": None, "z2_pct": None, "z3_pct": None,
                "z1_sec": 0, "z2_sec": 0, "z3_sec": 0,
                "classification": None, "pi": None, "window_days": days,
            }

        z1p = round(z1 / total * 100, 1)
        z2p = round(z2 / total * 100, 1)
        z3p = round(z3 / total * 100, 1)

        pi = None
        if z2p > 0 and z3p > 0:
            pi = round(math.log10((z1p / z2p) * z3p), 3)

        classification = self._classify_tid(z1p, z2p, z3p, pi)

        return {
            "z1_pct": z1p, "z2_pct": z2p, "z3_pct": z3p,
            "z1_sec": int(z1), "z2_sec": int(z2), "z3_sec": int(z3),
            "classification": classification,
            "pi": pi,
            "window_days": days,
        }

    def _classify_tid(self, z1: float, z2: float, z3: float, pi: Optional[float]) -> str:
        if z3 < 0.01:
            return "Base"
        if z1 > z3 > z2 and pi and pi > 2.0:
            return "Polarized"
        if z1 > z2 > z3:
            return "Pyramidal"
        if z2 >= z1 and z2 >= z3:
            return "Threshold"
        if z3 >= z1 and z3 >= z2:
            return "High Intensity"
        return "Mixed"

    def compute_ctl_atl_tsb(self, activities: list) -> dict:
        """
        CTL/ATL/TSB from Intervals.icu (Banister impulse-response model).
        Uses platform-computed values from the most recent activity.
        Ramp rate = weekly CTL change.
        """
        recent = sorted(
            activities,
            key=lambda x: x.get("start_date_local", ""),
            reverse=True,
        )

        ctl = atl = tsb = ramp_rate = None

        if recent:
            a = recent[0]
            ctl = a.get("icu_ctl")
            atl = a.get("icu_atl")
            tsb = a.get("icu_tsb")
            # TSB not always returned by the API — compute as CTL − ATL
            if tsb is None and ctl is not None and atl is not None:
                tsb = ctl - atl

        # Ramp rate from previous week's CTL
        if ctl and len(recent) > 1:
            for prev in recent[1:]:
                if prev.get("icu_ctl"):
                    ramp_rate = round(ctl - prev["icu_ctl"], 1)
                    break

        return {
            "ctl": round(ctl, 1) if ctl is not None else None,
            "atl": round(atl, 1) if atl is not None else None,
            "tsb": round(tsb, 1) if tsb is not None else None,
            "ramp_rate": ramp_rate,
        }

    def detect_phase(self, activities: list, events: list) -> dict:
        """
        Section 11 dual-stream phase detection.
        Retrospective: 4-week CTL slope + ACWR + hard-day density.
        Prospective: race calendar (days to next A/B/C event).
        8 phases: Overreached, Taper, Peak, Deload, Build, Base, Recovery, null.
        """
        today = datetime.date.today()
        cutoff = (today - datetime.timedelta(days=28)).isoformat()
        recent = [a for a in activities if a.get("start_date_local", "")[:10] >= cutoff]

        # CTL slope (per week)
        ctl_pairs = sorted(
            [(a["start_date_local"][:10], a["icu_ctl"])
             for a in recent if a.get("icu_ctl")],
        )
        ctl_slope = 0.0
        if len(ctl_pairs) >= 2:
            d0 = datetime.date.fromisoformat(ctl_pairs[0][0])
            d1 = datetime.date.fromisoformat(ctl_pairs[-1][0])
            span = max((d1 - d0).days, 1)
            ctl_slope = (ctl_pairs[-1][1] - ctl_pairs[0][1]) / span * 7

        acwr = self.compute_acwr(activities).get("acwr")
        hard_density = (
            sum(1 for a in recent if (a.get("tss") or 0) > 80) / max(len(recent), 1)
        )

        # Days to next race
        days_to_race = None
        race_events = [
            e for e in events
            if e.get("category") in ("RACE_A", "RACE_B", "RACE_C")
            or (e.get("name") or "").upper().startswith("RACE")
        ]
        if race_events:
            race_events.sort(key=lambda x: x.get("start_date_local", ""))
            try:
                rd = datetime.date.fromisoformat(race_events[0]["start_date_local"][:10])
                days_to_race = (rd - today).days
            except Exception:
                pass

        phase = self._determine_phase(ctl_slope, acwr, hard_density, days_to_race)
        confidence = self._phase_confidence(ctl_slope, acwr, hard_density)

        return {
            "current": phase,
            "confidence": confidence,
            "ctl_slope_per_week": round(ctl_slope, 2),
            "hard_day_density": round(hard_density, 2),
            "days_to_next_race": days_to_race,
        }

    def _determine_phase(self, ctl_slope, acwr, hard_density, days_to_race) -> str:
        if acwr and acwr > 1.5:
            return "Overreached"
        if days_to_race is not None:
            if days_to_race <= 7:
                return "Peak"
            if days_to_race <= 21:
                return "Taper"
        if ctl_slope < -1.5:
            return "Deload"
        if acwr and acwr < 0.6:
            return "Recovery"
        if ctl_slope > 2.0:
            return "Build"
        if ctl_slope > 0.3:
            return "Base"
        return "Base"

    def _phase_confidence(self, ctl_slope, acwr, hard_density) -> str:
        strong = sum([
            abs(ctl_slope) > 2,
            acwr is not None and (acwr > 1.3 or acwr < 0.7),
            hard_density > 0.4 or hard_density < 0.1,
        ])
        if strong >= 3:
            return "high"
        if strong >= 2:
            return "medium"
        return "low"

    def compute_readiness(
        self,
        recovery: dict,
        acwr_data: dict,
        ctl_data: dict,
    ) -> dict:
        """
        Section 11 readiness decision ladder (v11.13).
        P0: RI < 0.6 → skip (non-negotiable)
        P1: ACWR > 1.5 OR (TSB < -30 AND HRV ↓>10%) → skip
        P2: ≥2 red signals → modify
        P3: all clear → go
        """
        ri = recovery.get("ri")
        hrv_today = recovery.get("hrv_today")
        hrv_baseline = recovery.get("hrv_baseline")
        rhr_today = recovery.get("rhr_today")
        rhr_baseline = recovery.get("rhr_baseline")
        sleep_hours = recovery.get("sleep_hours")
        acwr = acwr_data.get("acwr")
        tsb = ctl_data.get("tsb")

        def _sig(val, red_fn, amber_fn):
            if val is None:
                return "unknown"
            if red_fn(val):
                return "red"
            if amber_fn(val):
                return "amber"
            return "green"

        hrv_pct = None
        if hrv_today and hrv_baseline:
            hrv_pct = (hrv_today - hrv_baseline) / hrv_baseline * 100

        signals = {
            "hrv": _sig(
                hrv_pct,
                lambda v: v < -20,
                lambda v: v < -10,
            ) if hrv_pct is not None else "unknown",
            "rhr": _sig(
                (rhr_today - rhr_baseline) if rhr_today and rhr_baseline else None,
                lambda v: v >= 5,
                lambda v: v >= 3,
            ),
            "sleep": _sig(sleep_hours, lambda v: v < 5, lambda v: v < 7),
            "tsb": _sig(tsb, lambda v: v < -30, lambda v: v < -20),
            "acwr": _sig(
                acwr,
                lambda v: v > 1.5 or v < 0.6,
                lambda v: v > 1.35 or v < 0.75,
            ),
            "ri": _sig(ri, lambda v: v < 0.6, lambda v: v < 0.8),
        }

        red_count = sum(1 for v in signals.values() if v == "red")
        known = sum(1 for v in signals.values() if v != "unknown")
        confidence = "high" if known >= 4 else ("medium" if known >= 2 else "low")

        # Priority ladder
        if ri is not None and ri < 0.6:
            return {
                "decision": "skip", "priority": "P0", "confidence": confidence,
                "signals": signals, "red_count": red_count,
                "reason": f"RI = {ri} (< 0.6 — non-negotiable deload threshold)",
            }
        if acwr and acwr > 1.5:
            return {
                "decision": "skip", "priority": "P1", "confidence": confidence,
                "signals": signals, "red_count": red_count,
                "reason": f"ACWR = {acwr} (> 1.5 — acute overload)",
            }
        if tsb is not None and tsb < -30 and signals.get("hrv") == "red":
            return {
                "decision": "skip", "priority": "P1", "confidence": confidence,
                "signals": signals, "red_count": red_count,
                "reason": f"TSB = {tsb} with HRV depressed > 10%",
            }
        if red_count >= 2:
            reds = [k for k, v in signals.items() if v == "red"]
            return {
                "decision": "modify", "priority": "P2", "confidence": confidence,
                "signals": signals, "red_count": red_count,
                "reason": f"Multiple red signals: {', '.join(reds)}",
            }
        return {
            "decision": "go", "priority": "P3", "confidence": confidence,
            "signals": signals, "red_count": red_count,
            "reason": "All signals within acceptable range",
        }

    def generate_alerts(
        self,
        acwr_data: dict,
        monotony_data: dict,
        recovery: dict,
        ctl_data: dict,
    ) -> list:
        """Section 11 validated alert thresholds."""
        alerts = []
        acwr = acwr_data.get("acwr")
        monotony = monotony_data.get("monotony")
        ri = recovery.get("ri")
        rhr_today = recovery.get("rhr_today")
        rhr_baseline = recovery.get("rhr_baseline")

        if acwr is not None:
            if acwr > 1.5:
                alerts.append({
                    "type": "ALARM", "metric": "ACWR", "value": acwr,
                    "message": f"ACWR {acwr} exceeds alarm threshold (>1.5). Elevated injury risk.",
                })
            elif acwr > 1.35:
                alerts.append({
                    "type": "WARNING", "metric": "ACWR", "value": acwr,
                    "message": f"ACWR {acwr} above optimal range (0.8–1.3).",
                })
            elif acwr < 0.6:
                alerts.append({
                    "type": "WARNING", "metric": "ACWR", "value": acwr,
                    "message": f"ACWR {acwr} very low — detraining risk.",
                })

        if monotony is not None:
            if monotony >= 2.5:
                alerts.append({
                    "type": "ALARM", "metric": "Monotony", "value": monotony,
                    "message": f"Monotony {monotony} at alarm level (≥2.5). Overuse risk.",
                })
            elif monotony >= 2.3:
                alerts.append({
                    "type": "WARNING", "metric": "Monotony", "value": monotony,
                    "message": f"Monotony {monotony} approaching alarm threshold.",
                })

        if ri is not None:
            if ri < 0.6:
                alerts.append({
                    "type": "ALARM", "metric": "RecoveryIndex", "value": ri,
                    "message": f"RI {ri} below deload threshold (<0.6). Load reduction mandatory.",
                })
            elif ri < 0.8:
                alerts.append({
                    "type": "WARNING", "metric": "RecoveryIndex", "value": ri,
                    "message": f"RI {ri} below optimal (≥0.8). Monitor recovery.",
                })

        if rhr_today and rhr_baseline:
            delta = rhr_today - rhr_baseline
            if delta >= 5:
                alerts.append({
                    "type": "ALARM", "metric": "RHR", "value": rhr_today,
                    "message": f"RHR elevated +{delta} bpm above baseline. Possible overreaching.",
                })
            elif delta >= 3:
                alerts.append({
                    "type": "WARNING", "metric": "RHR", "value": rhr_today,
                    "message": f"RHR elevated +{delta} bpm above baseline.",
                })

        return alerts

    # ── JSON builders ──────────────────────────────────────────────────────────

    def build_latest_json(
        self,
        athlete: dict,
        activities: list,
        wellness: list,
        events: list,
    ) -> dict:
        """latest.json — 7-day snapshot with full Section 11 metrics."""
        today = datetime.date.today()
        cutoff_7d = (today - datetime.timedelta(days=7)).isoformat()
        recent_7d = [a for a in activities if a.get("start_date_local", "")[:10] >= cutoff_7d]

        recovery = self.compute_recovery_index(wellness)
        acwr_data = self.compute_acwr(activities)
        monotony_data = self.compute_monotony_strain(activities)
        ctl_data = self.compute_ctl_atl_tsb(activities)
        tid_28d = self.compute_tid(activities, days=28)
        tid_7d = self.compute_tid(activities, days=7)
        phase = self.detect_phase(activities, events)
        readiness = self.compute_readiness(recovery, acwr_data, ctl_data)
        alerts = self.generate_alerts(acwr_data, monotony_data, recovery, ctl_data)

        formatted = []
        for act in sorted(recent_7d, key=lambda x: x.get("start_date_local", ""), reverse=True):
            formatted.append({
                "id": act.get("id"),
                "date": act.get("start_date_local", "")[:10],
                "name": act.get("name"),
                "type": act.get("type") or act.get("sport_type"),
                "duration_sec": act.get("moving_time"),
                "distance_m": act.get("distance"),
                "avg_watts": (act.get("average_watts")
                              or act.get("icu_average_watts")
                              or act.get("icu_weighted_avg_watts")),
                "np_watts": (act.get("normalized_watts")
                             or act.get("icu_weighted_avg_watts")),
                "avg_hr": act.get("average_heartrate"),
                "max_hr": act.get("max_heartrate"),
                "tss": act.get("tss") or act.get("icu_training_load"),
                "elevation_m": act.get("total_elevation_gain"),
                "avg_cadence": act.get("average_cadence"),
            })

        weekly_tss = sum((a.get("tss") or a.get("icu_training_load") or 0) for a in recent_7d)
        weekly_hours = sum((a.get("moving_time") or 0) for a in recent_7d) / 3600

        return {
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "protocol_version": PROTOCOL_VERSION,
            "script_version": VERSION,
            "athlete": {
                "id": self.athlete_id,
                "name": (
                    f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
                    or athlete.get("name", "")
                ),
            },
            "readiness": readiness,
            "metrics": {
                **ctl_data,
                **acwr_data,
                **monotony_data,
                "recovery_index": recovery.get("ri"),
                "hrv_today": recovery.get("hrv_today"),
                "hrv_baseline": recovery.get("hrv_baseline"),
                "rhr_today": recovery.get("rhr_today"),
                "rhr_baseline": recovery.get("rhr_baseline"),
                "sleep_hours": recovery.get("sleep_hours"),
            },
            "phase": phase,
            "tid": {"28d": tid_28d, "7d": tid_7d},
            "weekly_totals": {
                "tss": round(weekly_tss, 1),
                "hours": round(weekly_hours, 1),
                "sessions": len(recent_7d),
            },
            "upcoming_events": [
                {
                    "name": e.get("name"),
                    "date": e.get("start_date_local", "")[:10],
                    "category": e.get("category"),
                }
                for e in events[:10]
            ],
            "alerts": alerts,
            "recent_activities": formatted,
        }

    def build_history_json(self, activities: list, wellness: list) -> dict:
        """history.json — 84-day longitudinal data (12 weeks)."""
        today = datetime.date.today()
        load_by_date: dict[str, float] = defaultdict(float)
        acts_by_date: dict[str, list] = defaultdict(list)

        for act in activities:
            d = act.get("start_date_local", "")[:10]
            tss = act.get("tss") or act.get("icu_training_load") or 0
            load_by_date[d] += tss
            acts_by_date[d].append(act)

        wellness_by_date = {w.get("id"): w for w in wellness}

        days_list = []
        for i in range(84):
            d = (today - datetime.timedelta(days=i)).isoformat()
            w = wellness_by_date.get(d, {})
            day_acts = acts_by_date.get(d, [])
            sleep_secs = w.get("sleepSecs") or w.get("sleepSeconds") or 0

            entry = {
                "date": d,
                "tss": round(load_by_date.get(d, 0), 1),
                "duration_sec": sum(a.get("moving_time") or 0 for a in day_acts),
                "sessions": len(day_acts),
                "hrv": w.get("hrv") or w.get("hrvSDNN"),
                "rhr": w.get("restingHR"),
                "sleep_hours": round(sleep_secs / 3600, 1) if sleep_secs else None,
            }
            if day_acts:
                last = day_acts[-1]
                entry["ctl"] = last.get("icu_ctl")
                entry["atl"] = last.get("icu_atl")
                entry["tsb"] = last.get("icu_tsb")

            if any(v is not None and v != 0 for k, v in entry.items() if k != "date"):
                days_list.append(entry)

        return {
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "protocol_version": PROTOCOL_VERSION,
            "days": days_list,
        }

    def build_ftp_history_json(self, ftp_history: list) -> dict:
        """ftp_history.json — FTP tracking (indoor/outdoor)."""
        return {
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "protocol_version": PROTOCOL_VERSION,
            "history": sorted(ftp_history, key=lambda x: x.get("date", ""), reverse=True),
        }

    # ── Main entry point ───────────────────────────────────────────────────────

    def collect_and_save(self, output_dir: str = ".") -> dict:
        output = Path(output_dir)
        output.mkdir(exist_ok=True)

        def log(msg):
            ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
            print(f"[{ts}] {msg}", flush=True)

        log("Fetching athlete profile...")
        athlete = self.fetch_athlete()

        log("Fetching activities (84 days)...")
        activities = self.fetch_activities(days_back=84)
        log(f"  → {len(activities)} activities")

        log("Fetching wellness data (42 days)...")
        wellness = self.fetch_wellness(days_back=42)
        log(f"  → {len(wellness)} wellness entries")

        log("Fetching upcoming events (42 days)...")
        events = self.fetch_events(days_ahead=42)
        log(f"  → {len(events)} events")

        log("Fetching FTP history...")
        ftp_history = self.fetch_ftp_history()

        log("Computing Section 11 metrics...")
        latest = self.build_latest_json(athlete, activities, wellness, events)
        history = self.build_history_json(activities, wellness)
        ftp_hist = self.build_ftp_history_json(ftp_history)

        files = {
            "latest.json": latest,
            "history.json": history,
            "ftp_history.json": ftp_hist,
        }

        for filename, data in files.items():
            fp = output / filename
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            log(f"  ✅ {fp} ({fp.stat().st_size:,} bytes)")

        # Summary
        r = latest["readiness"]
        m = latest["metrics"]
        print(f"\n{'─'*52}")
        print(f"  READINESS : {r['decision'].upper():6}  ({r['priority']})")
        print(f"  RI        : {m.get('recovery_index')}    "
              f"HRV today: {m.get('hrv_today')}  baseline: {m.get('hrv_baseline')}")
        print(f"  ACWR      : {m.get('acwr')}  "
              f"CTL: {m.get('ctl')}  ATL: {m.get('atl')}  TSB: {m.get('tsb')}")
        print(f"  Monotony  : {m.get('monotony')}  Strain: {m.get('strain')}")
        phase = latest["phase"]
        print(f"  Phase     : {phase['current']} ({phase['confidence']})")
        tid = latest["tid"]["28d"]
        print(f"  TID 28d   : Z1={tid.get('z1_pct')}%  Z2={tid.get('z2_pct')}%  "
              f"Z3={tid.get('z3_pct')}%  → {tid.get('classification')}  PI={tid.get('pi')}")
        if latest["alerts"]:
            print(f"  ALERTS    : {len(latest['alerts'])}")
            for a in latest["alerts"]:
                print(f"    [{a['type']}] {a['message']}")
        print(f"{'─'*52}\n")

        return latest


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=f"Section 11 AI Coaching Protocol — Data Sync v{VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Credentials can be set via environment variables:\n"
            "  ATHLETE_ID    Your Intervals.icu athlete ID (e.g. i123456)\n"
            "  INTERVALS_KEY Your Intervals.icu API key\n"
        ),
    )
    parser.add_argument("--athlete-id", default=os.environ.get("ATHLETE_ID"))
    parser.add_argument("--intervals-key", default=os.environ.get("INTERVALS_KEY"))
    parser.add_argument("--days", type=int, default=7,
                        help="Snapshot window in days (default: 7)")
    parser.add_argument("--output-dir", default=".",
                        help="Directory for JSON output (default: current dir)")
    # Accepted but unused locally — used by GitHub Actions workflow
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--github-repo", default=os.environ.get("GITHUB_REPO"))

    args = parser.parse_args()

    if not args.athlete_id:
        parser.error("--athlete-id required (or set ATHLETE_ID env var)")
    if not args.intervals_key:
        parser.error("--intervals-key required (or set INTERVALS_KEY env var)")

    sync = IntervalsSync(args.athlete_id, args.intervals_key, args.days)

    try:
        sync.collect_and_save(output_dir=args.output_dir)
    except requests.HTTPError as e:
        print(f"\nERROR: API request failed: {e}")
        if e.response is not None and e.response.status_code == 401:
            print("  → Check your ATHLETE_ID and INTERVALS_KEY")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
