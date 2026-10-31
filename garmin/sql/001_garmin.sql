-- Garmin daily sync storage. No anon access: only the service role (GitHub Actions)
-- and the Supabase MCP (weekly report) can read or write.

create table if not exists public.garmin_daily (
  day                 date primary key,
  steps               integer,
  resting_hr          integer,
  active_kcal         integer,
  intensity_min       integer,      -- moderate + 2x vigorous, Garmin's own formula
  sleep_hours         numeric(4,2),
  sleep_score         integer,
  hrv_last_night_ms   integer,
  body_battery_high   integer,
  body_battery_low    integer,
  stress_avg          integer,
  activity_count      integer,
  activity_minutes    numeric(6,1),
  activity_km         numeric(7,2),
  activity_types      text,
  synced_at           timestamptz not null default now()
);

-- Token store. Garmin rotates the refresh token, so each run writes the new one back.
create table if not exists public.garmin_auth (
  id          smallint primary key default 1 check (id = 1),
  tokens      text not null,
  updated_at  timestamptz not null default now()
);

-- One row per run so the weekly report can say "sync stale" instead of failing quietly.
create table if not exists public.garmin_sync_runs (
  id          bigint generated always as identity primary key,
  ran_at      timestamptz not null default now(),
  ok          boolean not null,
  days        integer,
  error       text
);

alter table public.garmin_daily     enable row level security;
alter table public.garmin_auth      enable row level security;
alter table public.garmin_sync_runs enable row level security;
-- Deliberately no policies: anon and authenticated roles get nothing.
revoke all on public.garmin_daily, public.garmin_auth, public.garmin_sync_runs from anon, authenticated;
