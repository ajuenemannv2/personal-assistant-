"""Daily Garmin -> Supabase sync. Read only on Garmin. Runs in GitHub Actions.

Env:
  SUPABASE_URL          https://<ref>.supabase.co
  SUPABASE_SERVICE_KEY  service role key (GitHub secret)
  GARMIN_TOKENS_SEED    optional, only for the very first run (from login_once.py)
  SYNC_DAYS             optional, days back to (re)sync, default 3
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

import requests
from garminconnect import Garmin

URL = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
KEY = os.environ["SUPABASE_SERVICE_KEY"]
HDRS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
TIMEOUT = 30


def sb_get(table: str, query: str) -> list:
    r = requests.get(f"{URL}/{table}?{query}", headers=HDRS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def sb_upsert(table: str, rows: list[dict]) -> None:
    h = {**HDRS, "Prefer": "resolution=merge-duplicates,return=minimal"}
    r = requests.post(f"{URL}/{table}", headers=h, data=json.dumps(rows, default=str), timeout=TIMEOUT)
    r.raise_for_status()


def sb_insert(table: str, row: dict) -> None:
    h = {**HDRS, "Prefer": "return=minimal"}
    r = requests.post(f"{URL}/{table}", headers=h, data=json.dumps(row), timeout=TIMEOUT)
    r.raise_for_status()


def load_tokens() -> str:
    rows = sb_get("garmin_auth", "id=eq.1&select=tokens")
    if rows:
        return rows[0]["tokens"]
    seed = os.environ.get("GARMIN_TOKENS_SEED", "").strip()
    if not seed:
        raise RuntimeError("No Garmin tokens in Supabase and no GARMIN_TOKENS_SEED secret. Run login_once.py.")
    return seed


def save_tokens(tokens: str) -> None:
    sb_upsert("garmin_auth", [{"id": 1, "tokens": tokens, "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()}])


def _num(d: dict | None, *keys):
    """Safe nested get; returns None for missing or non-numeric values."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur if isinstance(cur, (int, float)) else None


def build_day(day: str, stats: dict | None, sleep: dict | None, hrv: dict | None, acts: list | None) -> dict:
    mod = _num(stats, "moderateIntensityMinutes") or 0
    vig = _num(stats, "vigorousIntensityMinutes") or 0
    intensity = mod + 2 * vig if (_num(stats, "moderateIntensityMinutes") is not None
                                  or _num(stats, "vigorousIntensityMinutes") is not None) else None
    sleep_s = _num(sleep, "dailySleepDTO", "sleepTimeSeconds")
    acts = acts or []
    types = sorted({(a.get("activityType") or {}).get("typeKey", "other") for a in acts})
    return {
        "day": day,
        "steps": _num(stats, "totalSteps"),
        "resting_hr": _num(stats, "restingHeartRate"),
        "active_kcal": round(_num(stats, "activeKilocalories")) if _num(stats, "activeKilocalories") is not None else None,
        "intensity_min": intensity,
        "sleep_hours": round(sleep_s / 3600, 2) if sleep_s else None,
        "sleep_score": _num(sleep, "dailySleepDTO", "sleepScores", "overall", "value"),
        "hrv_last_night_ms": _num(hrv, "hrvSummary", "lastNightAvg"),
        "body_battery_high": _num(stats, "bodyBatteryHighestValue"),
        "body_battery_low": _num(stats, "bodyBatteryLowestValue"),
        "stress_avg": _num(stats, "averageStressLevel"),
        "activity_count": len(acts),
        "activity_minutes": round(sum((_num(a, "duration") or 0) for a in acts) / 60, 1),
        "activity_km": round(sum((_num(a, "distance") or 0) for a in acts) / 1000, 2),
        "activity_types": ", ".join(types) if types else None,
        "synced_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def safe(fn, *args):
    try:
        return fn(*args)
    except Exception as e:  # one missing metric shouldn't kill the day
        print(f"warn: {fn.__name__}{args} failed: {type(e).__name__}", file=sys.stderr)
        return None


def main() -> int:
    days_back = int(os.environ.get("SYNC_DAYS", "3"))
    try:
        g = Garmin()
        g.login(tokenstore=load_tokens())
        save_tokens(g.client.dumps())  # persist any rotated refresh token right away

        today = dt.date.today()
        rows = []
        for i in range(days_back):
            day = (today - dt.timedelta(days=i)).isoformat()
            rows.append(build_day(
                day,
                safe(g.get_stats, day),
                safe(g.get_sleep_data, day),
                safe(g.get_hrv_data, day),
                safe(g.get_activities_by_date, day, day),
            ))
        sb_upsert("garmin_daily", rows)
        save_tokens(g.client.dumps())
        sb_insert("garmin_sync_runs", {"ok": True, "days": len(rows)})
        print(f"ok: synced {len(rows)} days")
        return 0
    except Exception as e:
        msg = f"{type(e).__name__}: {str(e)[:300]}"
        try:
            sb_insert("garmin_sync_runs", {"ok": False, "error": msg})
        except Exception:
            pass
        print(f"error: {msg}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
