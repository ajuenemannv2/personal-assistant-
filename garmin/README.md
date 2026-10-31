# garmin-sync

Pulls yesterday-ish Garmin data (last 3 days, so late watch syncs get filled in) into Supabase once a day. Read only on Garmin. The Concierge weekly report reads the `garmin_daily` table.

**Data:** steps, resting HR, active kcal, intensity minutes, sleep hours and score, HRV, Body Battery high/low, average stress, and workouts (count, minutes, km, types).

## Setup (one time)

1. **Supabase:** project `alex-personal-data` (https://cytdhunpcdvotkcuwgcu.supabase.co). The tables are already created from `sql/001_garmin.sql`.
2. **Garmin login on your PC:**
   ```
   py -m venv .venv
   .venv\Scripts\activate
   cd garmin
   pip install --require-hashes -r requirements.txt
   python login_once.py
   ```
   Enter your email, password and MFA code. This creates `garmin_tokens.json`.
3. **GitHub secrets** (repo → Settings → Secrets and variables → Actions):
   - `SUPABASE_URL`: the project URL
   - `SUPABASE_SERVICE_KEY`: Project Settings → API Keys → service_role / secret key
   - `GARMIN_TOKENS_SEED`: the full contents of `garmin_tokens.json`
4. **Delete `garmin_tokens.json`** from your PC.
5. Actions tab → "Garmin daily sync" → Run workflow. Check that it goes green.
6. After the first green run, delete the `GARMIN_TOKENS_SEED` secret. The live token now lives in Supabase and rotates there.

## If it breaks

- Check `garmin_sync_runs` for the error. A login error usually means Garmin changed its auth. Bump `garminconnect` in `requirements.in`, re-run `pip-compile --generate-hashes`, review the diff, then re-run `login_once.py` and redo step 3.
- Never put your Garmin password in a secret. Only the token goes there.

## Security notes

- garminconnect 0.3.20 was reviewed on Oct 30, 2026. Credentials go only to sso.garmin.com, there's no telemetry, and tokens are written with 0600 permissions. ua-generator 2.1.7 makes no network calls. All dependencies are hash-pinned.
- The Supabase tables have RLS on with no policies, so the public anon key can't read them.
