create table if not exists public.license_entitlements (
    product_id text not null,
    hwid_sha256 text not null check (hwid_sha256 ~ '^[0-9a-f]{64}$'),
    hwid_hint text not null default '',
    holder_name text not null default '',
    active boolean not null default true,
    expires_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (product_id, hwid_sha256)
);

alter table public.license_entitlements enable row level security;
revoke all on table public.license_entitlements from anon, authenticated;
grant all on table public.license_entitlements to service_role;

create index if not exists license_entitlements_active_idx
    on public.license_entitlements (product_id, active, expires_at);
