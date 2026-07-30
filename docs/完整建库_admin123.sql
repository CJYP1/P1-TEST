-- =====================================================================
-- Zone Resource Map — Supabase 完整建库脚本 (含 admin 密码 = admin123)
-- Project ref: qjdmcvbagozoyebjbwyh
-- 用法: Supabase Dashboard > SQL Editor > 粘贴全部 > Run。可重复运行, 安全。
-- =====================================================================

create extension if not exists pgcrypto with schema extensions;

-- ---------------------------------------------------------------------
-- TABLES
-- ---------------------------------------------------------------------
create table if not exists public.rws_users (
  id             uuid primary key default gen_random_uuid(),
  username       text unique not null,
  password_hash  text not null,
  display_name   text not null default '',
  role           text not null default 'user' check (role in ('admin','user')),
  allowed_scopes jsonb not null default '[]'::jsonb,
  active         boolean not null default true,
  created_at     timestamptz not null default now()
);

create table if not exists public.rws_sessions (
  token      uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.rws_users(id) on delete cascade,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);
create index if not exists rws_sessions_user_idx on public.rws_sessions(user_id);

create table if not exists public.rws_element_status (
  element_key text primary key,
  level       text not null,
  zone_mk     text not null,
  elem_type   text not null,
  elem_id     text not null,
  status      text not null default 'todo' check (status in ('todo','wip','done')),
  updated_by  uuid references public.rws_users(id),
  updated_at  timestamptz not null default now()
);
create index if not exists rws_element_status_zone_idx on public.rws_element_status(level, zone_mk);

create table if not exists public.rws_slab_qty (
  qty_key    text primary key,
  level      text not null,
  zone_mk    text not null,
  qty        numeric,
  updated_by uuid references public.rws_users(id),
  updated_at timestamptz not null default now()
);
create index if not exists rws_slab_qty_zone_idx on public.rws_slab_qty(level, zone_mk);

create table if not exists public.rws_zone_updates (
  id          bigserial primary key,
  zone_mk     text not null,
  level       text,
  zone_label  text,
  pct         int,
  status      text,
  update_date text,
  note        text,
  crew        text,
  created_by  uuid references public.rws_users(id),
  created_at  timestamptz not null default now()
);

create table if not exists public.rws_activity_log (
  id         bigserial primary key,
  user_id    uuid references public.rws_users(id),
  username   text,
  action     text not null,
  target_key text,
  old_value  jsonb,
  new_value  jsonb,
  created_at timestamptz not null default now()
);
create index if not exists rws_activity_log_created_idx on public.rws_activity_log(created_at desc);
create index if not exists rws_activity_log_user_idx on public.rws_activity_log(user_id);

create table if not exists public.rws_qty_ov (
  qty_key    text primary key,
  level      text not null,
  zone_mk    text not null,
  field      text not null,
  value      numeric,
  updated_by uuid references public.rws_users(id),
  updated_at timestamptz not null default now()
);
create index if not exists rws_qty_ov_zone_idx on public.rws_qty_ov(level, zone_mk);

create table if not exists public.rws_zp_plan_ov (
  plan_key   text primary key,
  level      text,
  zone_mk    text,
  value      numeric,
  updated_by uuid references public.rws_users(id),
  updated_at timestamptz not null default now()
);
create index if not exists rws_zp_plan_ov_zone_idx on public.rws_zp_plan_ov(level, zone_mk);

alter table public.rws_users          enable row level security;
alter table public.rws_sessions       enable row level security;
alter table public.rws_element_status enable row level security;
alter table public.rws_slab_qty       enable row level security;
alter table public.rws_zone_updates   enable row level security;
alter table public.rws_activity_log   enable row level security;
alter table public.rws_qty_ov         enable row level security;
alter table public.rws_zp_plan_ov     enable row level security;

revoke all on public.rws_users, public.rws_sessions, public.rws_element_status,
  public.rws_slab_qty, public.rws_zone_updates, public.rws_activity_log,
  public.rws_qty_ov, public.rws_zp_plan_ov
  from anon, authenticated;

-- ---------------------------------------------------------------------
-- HELPERS
-- ---------------------------------------------------------------------
create or replace function public._rws_session(p_token uuid)
returns table(user_id uuid, username text, role text, allowed_scopes jsonb)
language plpgsql security definer set search_path = public as $$
begin
  return query
    select u.id, u.username, u.role, u.allowed_scopes
    from rws_sessions s join rws_users u on u.id = s.user_id
    where s.token = p_token and s.expires_at > now() and u.active;
  if not found then raise exception 'invalid or expired session'; end if;
end;$$;

-- ---------------------------------------------------------------------
-- AUTH
-- ---------------------------------------------------------------------
create or replace function public.rws_login(p_username text, p_password text)
returns jsonb language plpgsql security definer set search_path = public, extensions as $$
declare u record; tok uuid;
begin
  select * into u from rws_users where username = p_username and active limit 1;
  if not found or u.password_hash <> crypt(p_password, u.password_hash) then
    raise exception 'invalid username or password';
  end if;
  insert into rws_sessions(user_id, expires_at) values (u.id, now() + interval '18 hours') returning token into tok;
  insert into rws_activity_log(user_id, username, action, target_key) values (u.id, u.username, 'login', null);
  return jsonb_build_object('token', tok, 'user_id', u.id, 'username', u.username,
    'display_name', u.display_name, 'role', u.role, 'allowed_scopes', u.allowed_scopes);
end;$$;

create or replace function public.rws_check_session(p_token uuid)
returns jsonb language plpgsql security definer set search_path = public as $$
declare r record;
begin
  select * into r from _rws_session(p_token);
  return jsonb_build_object('user_id', r.user_id, 'username', r.username, 'role', r.role, 'allowed_scopes', r.allowed_scopes);
exception when others then return null; end;$$;

create or replace function public.rws_logout(p_token uuid)
returns void language sql security definer set search_path = public as $$
  delete from rws_sessions where token = p_token;
$$;

-- ---------------------------------------------------------------------
-- area reference + permission helpers
-- ---------------------------------------------------------------------
create table if not exists public.rws_zone_area (
  level text not null, zone_mk text not null, area text not null,
  primary key (level, zone_mk)
);
alter table public.rws_zone_area enable row level security;
revoke all on public.rws_zone_area from anon, authenticated;

create or replace function public._rws_area_for(p_level text, p_zone_mk text)
returns text language sql stable security definer set search_path = public as $$
  select area from rws_zone_area where level = p_level and zone_mk = p_zone_mk;
$$;

create or replace function public._rws_area_ok(p_scopes jsonb, p_level text, p_zone_mk text)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from jsonb_array_elements_text(coalesce(p_scopes,'[]'::jsonb)) a
    where a = _rws_area_for(p_level, p_zone_mk));
$$;

-- ---------------------------------------------------------------------
-- WRITES
-- ---------------------------------------------------------------------
create or replace function public.rws_update_element(p_token uuid, p_element_key text, p_status text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; parts text[]; lv text; zmk text; etype text; eid text; old_status text;
begin
  select * into s from _rws_session(p_token);
  if p_status not in ('todo','wip','done') then raise exception 'bad status'; end if;
  parts := string_to_array(p_element_key, '||');
  if array_length(parts,1) <> 4 then raise exception 'bad element key'; end if;
  lv := parts[1]; zmk := parts[2]; etype := parts[3]; eid := parts[4];
  if s.role <> 'admin' then
    if etype <> 'col' then raise exception 'not permitted: only column status can be edited'; end if;
    if not _rws_area_ok(s.allowed_scopes, lv, zmk) then raise exception 'not permitted: outside your assigned area'; end if;
  end if;
  select status into old_status from rws_element_status where element_key = p_element_key;
  insert into rws_element_status(element_key, level, zone_mk, elem_type, elem_id, status, updated_by, updated_at)
    values (p_element_key, lv, zmk, etype, eid, p_status, s.user_id, now())
  on conflict (element_key) do update set status = excluded.status, updated_by = excluded.updated_by, updated_at = now();
  insert into rws_activity_log(user_id, username, action, target_key, old_value, new_value)
    values (s.user_id, s.username, 'element_status', p_element_key, to_jsonb(old_status), to_jsonb(p_status));
  return jsonb_build_object('ok', true, 'element_key', p_element_key, 'status', p_status);
end;$$;

create or replace function public.rws_update_slab_qty(p_token uuid, p_qty_key text, p_level text, p_zone_mk text, p_qty numeric)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; old_qty numeric;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' and not _rws_area_ok(s.allowed_scopes, p_level, p_zone_mk) then
    raise exception 'not permitted: outside your assigned area'; end if;
  select qty into old_qty from rws_slab_qty where qty_key = p_qty_key;
  insert into rws_slab_qty(qty_key, level, zone_mk, qty, updated_by, updated_at)
    values (p_qty_key, p_level, p_zone_mk, p_qty, s.user_id, now())
  on conflict (qty_key) do update set qty = excluded.qty, updated_by = excluded.updated_by, updated_at = now();
  insert into rws_activity_log(user_id, username, action, target_key, old_value, new_value)
    values (s.user_id, s.username, 'slab_qty', p_qty_key, to_jsonb(old_qty), to_jsonb(p_qty));
  return jsonb_build_object('ok', true, 'qty_key', p_qty_key, 'qty', p_qty);
end;$$;

create or replace function public.rws_add_zone_update(p_token uuid, p_zone_mk text, p_level text, p_zone_label text,
  p_pct int, p_status text, p_date text, p_note text, p_crew text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; new_id bigint;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  insert into rws_zone_updates(zone_mk, level, zone_label, pct, status, update_date, note, crew, created_by)
    values (p_zone_mk, p_level, p_zone_label, p_pct, p_status, p_date, p_note, p_crew, s.user_id)
    returning id into new_id;
  insert into rws_activity_log(user_id, username, action, target_key, new_value)
    values (s.user_id, s.username, 'zone_update', p_zone_mk, jsonb_build_object('id', new_id,'pct',p_pct,'status',p_status,'note',p_note));
  return jsonb_build_object('ok', true, 'id', new_id);
end;$$;

create or replace function public.rws_update_qty(p_token uuid, p_qty_key text, p_level text, p_zone_mk text, p_field text, p_value numeric)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; old_val numeric;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  if p_field not in ('columns','pilecap','mainbeam','steelbeam','liftcw','stair','liftstair','area') then raise exception 'bad field'; end if;
  select value into old_val from rws_qty_ov where qty_key = p_qty_key;
  insert into rws_qty_ov(qty_key, level, zone_mk, field, value, updated_by, updated_at)
    values (p_qty_key, p_level, p_zone_mk, p_field, p_value, s.user_id, now())
  on conflict (qty_key) do update set value = excluded.value, updated_by = excluded.updated_by, updated_at = now();
  insert into rws_activity_log(user_id, username, action, target_key, old_value, new_value)
    values (s.user_id, s.username, 'qty_ov', p_qty_key, to_jsonb(old_val), to_jsonb(p_value));
  return jsonb_build_object('ok', true);
end;$$;

create or replace function public.rws_update_plan_qty(p_token uuid, p_plan_key text, p_level text, p_zone_mk text, p_value numeric)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; old_val numeric;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  select value into old_val from rws_zp_plan_ov where plan_key = p_plan_key;
  insert into rws_zp_plan_ov(plan_key, level, zone_mk, value, updated_by, updated_at)
    values (p_plan_key, p_level, p_zone_mk, p_value, s.user_id, now())
  on conflict (plan_key) do update set value = excluded.value, updated_by = excluded.updated_by, updated_at = now();
  insert into rws_activity_log(user_id, username, action, target_key, old_value, new_value)
    values (s.user_id, s.username, 'plan_qty', p_plan_key, to_jsonb(old_val), to_jsonb(p_value));
  return jsonb_build_object('ok', true);
end;$$;

-- ---------------------------------------------------------------------
-- ADMIN reads / account mgmt
-- ---------------------------------------------------------------------
create or replace function public.rws_admin_activity_log(p_token uuid, p_limit int default 300)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  return (select coalesce(jsonb_agg(row_to_json(t)), '[]'::jsonb) from (
    select id, username, action, target_key, old_value, new_value, created_at
    from rws_activity_log order by created_at desc limit p_limit) t);
end;$$;

create or replace function public.rws_admin_list_users(p_token uuid)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  return (select coalesce(jsonb_agg(row_to_json(t)), '[]'::jsonb) from (
    select id, username, display_name, role, allowed_scopes, active, created_at
    from rws_users order by created_at) t);
end;$$;

create or replace function public.rws_admin_upsert_user(p_token uuid, p_username text, p_password text,
  p_display_name text, p_role text, p_allowed_scopes jsonb, p_active boolean)
returns jsonb language plpgsql security definer set search_path = public, extensions as $$
declare s record; uid uuid;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  if p_role not in ('admin','user') then raise exception 'bad role'; end if;
  insert into rws_users(username, password_hash, display_name, role, allowed_scopes, active)
    values (p_username, crypt(coalesce(p_password,''), gen_salt('bf')), coalesce(p_display_name,''), p_role,
      coalesce(p_allowed_scopes,'[]'::jsonb), coalesce(p_active,true))
  on conflict (username) do update set
    password_hash = case when p_password is not null and p_password <> '' then crypt(p_password, gen_salt('bf')) else rws_users.password_hash end,
    display_name  = coalesce(p_display_name, rws_users.display_name),
    role           = p_role,
    allowed_scopes = coalesce(p_allowed_scopes, rws_users.allowed_scopes),
    active         = coalesce(p_active, rws_users.active)
  returning id into uid;
  return jsonb_build_object('ok', true, 'id', uid);
end;$$;

-- ---------------------------------------------------------------------
-- custom cats / items
-- ---------------------------------------------------------------------
create table if not exists public.rws_custom_cat (
  code text primary key, label text not null,
  created_by uuid references public.rws_users(id), created_at timestamptz not null default now());
create table if not exists public.rws_custom_item (
  item_key text primary key, level text not null, zone_mk text not null,
  type text not null, elem_id text not null,
  created_by uuid references public.rws_users(id), created_at timestamptz not null default now());
create index if not exists rws_custom_item_zone_idx on public.rws_custom_item(level, zone_mk);
alter table public.rws_custom_cat  enable row level security;
alter table public.rws_custom_item enable row level security;
revoke all on public.rws_custom_cat, public.rws_custom_item from anon, authenticated;

create or replace function public.rws_add_cat(p_token uuid, p_code text, p_label text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  if p_code is null or p_code = '' or position('||' in p_code) > 0 then raise exception 'bad code'; end if;
  insert into rws_custom_cat(code,label,created_by) values (p_code, coalesce(p_label,p_code), s.user_id)
    on conflict (code) do update set label = excluded.label;
  insert into rws_activity_log(user_id,username,action,target_key,new_value)
    values (s.user_id,s.username,'add_cat',p_code,to_jsonb(p_label));
  return jsonb_build_object('ok',true);
end;$$;

create or replace function public.rws_del_cat(p_token uuid, p_code text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  delete from rws_custom_item where type = p_code;
  delete from rws_custom_cat where code = p_code;
  insert into rws_activity_log(user_id,username,action,target_key) values (s.user_id,s.username,'del_cat',p_code);
  return jsonb_build_object('ok',true);
end;$$;

create or replace function public.rws_add_item(p_token uuid, p_item_key text, p_level text, p_zone_mk text, p_type text, p_elem_id text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  if p_elem_id is null or p_elem_id = '' or position('||' in p_elem_id) > 0 then raise exception 'bad id'; end if;
  insert into rws_custom_item(item_key,level,zone_mk,type,elem_id,created_by)
    values (p_item_key,p_level,p_zone_mk,p_type,p_elem_id,s.user_id)
    on conflict (item_key) do nothing;
  insert into rws_activity_log(user_id,username,action,target_key,new_value)
    values (s.user_id,s.username,'add_item',p_item_key,to_jsonb(p_elem_id));
  return jsonb_build_object('ok',true);
end;$$;

create or replace function public.rws_del_item(p_token uuid, p_item_key text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  delete from rws_custom_item where item_key = p_item_key;
  delete from rws_element_status where element_key = p_item_key;
  insert into rws_activity_log(user_id,username,action,target_key) values (s.user_id,s.username,'del_item',p_item_key);
  return jsonb_build_object('ok',true);
end;$$;

-- ---------------------------------------------------------------------
-- generic kv store (act_total/act_plan/act_done_m/act_hidden/elem_date/
-- act_def/crit/zdate/act_date/col_month/act_cmt)
-- ---------------------------------------------------------------------
create table if not exists public.rws_kv (
  store text not null, k text not null, value jsonb,
  level text, zone_mk text,
  updated_by uuid references public.rws_users(id),
  updated_at timestamptz not null default now(),
  primary key (store, k));
create index if not exists rws_kv_store_idx on public.rws_kv(store);
alter table public.rws_kv enable row level security;
revoke all on public.rws_kv from anon, authenticated;

create or replace function public.rws_set_kv(p_token uuid, p_store text, p_k text, p_value jsonb, p_level text, p_zone_mk text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; old jsonb;
begin
  select * into s from _rws_session(p_token);
  if p_store not in ('act_total','act_plan','act_done_m','act_hidden','elem_date','act_def','crit','zdate','act_date','col_month','act_cmt') then raise exception 'bad store'; end if;
  if s.role <> 'admin' then
    if p_store in ('act_total','act_plan','act_hidden','act_def','crit','zdate','act_date','col_month') then raise exception 'admin only'; end if;
    if p_store = 'act_cmt' then
      -- 评论/标完成: 有 CMT(写评论) 或 有本区编辑权限(现场做工的可标完成) 即可; 精确到区由前端控制
      if not ( (coalesce(s.allowed_scopes,'[]'::jsonb) ? 'CMT') or _rws_area_ok(s.allowed_scopes, p_level, p_zone_mk) ) then raise exception 'not permitted: no comment or area permission'; end if;
    else
      if not _rws_area_ok(s.allowed_scopes, p_level, p_zone_mk) then raise exception 'not permitted: outside your assigned area'; end if;
    end if;
  end if;
  select value into old from rws_kv where store = p_store and k = p_k;
  if p_value is null then delete from rws_kv where store = p_store and k = p_k;
  else insert into rws_kv(store,k,value,level,zone_mk,updated_by,updated_at) values (p_store,p_k,p_value,p_level,p_zone_mk,s.user_id,now())
    on conflict (store,k) do update set value=excluded.value, level=excluded.level, zone_mk=excluded.zone_mk, updated_by=excluded.updated_by, updated_at=now(); end if;
  insert into rws_activity_log(user_id,username,action,target_key,old_value,new_value) values (s.user_id,s.username,p_store,p_k,old,p_value);
  return jsonb_build_object('ok',true);
end;$$;

-- FINAL rws_get_state — returns everything
create or replace function public.rws_get_state(p_token uuid)
returns jsonb language plpgsql security definer set search_path = public as $$
begin
  perform * from _rws_session(p_token);
  return jsonb_build_object(
    'elements', (select coalesce(jsonb_object_agg(element_key, status), '{}'::jsonb) from rws_element_status),
    'slab_qty', (select coalesce(jsonb_object_agg(qty_key, qty), '{}'::jsonb) from rws_slab_qty),
    'qty_ov', (select coalesce(jsonb_object_agg(qty_key, value), '{}'::jsonb) from rws_qty_ov),
    'plan_qty_ov', (select coalesce(jsonb_object_agg(plan_key, value), '{}'::jsonb) from rws_zp_plan_ov),
    'act_total',  (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='act_total'),
    'act_plan',   (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='act_plan'),
    'act_done_m', (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='act_done_m'),
    'act_hidden', (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='act_hidden'),
    'act_def',    (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='act_def'),
    'crit',       (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='crit'),
    'zdate',      (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='zdate'),
    'act_date',   (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='act_date'),
    'col_month',  (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='col_month'),
    'act_cmt',    (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='act_cmt'),
    'elem_date',  (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='elem_date'),
    'custom_cats', (select coalesce(jsonb_agg(jsonb_build_object('code',code,'label',label) order by created_at), '[]'::jsonb) from rws_custom_cat),
    'custom_items', (select coalesce(jsonb_agg(jsonb_build_object('item_key',item_key,'level',level,'zone_mk',zone_mk,'type',type,'elem_id',elem_id) order by created_at), '[]'::jsonb) from rws_custom_item),
    'zone_updates', (select coalesce(jsonb_agg(row_to_json(t)), '[]'::jsonb) from (
       select zone_mk, level, zone_label, pct, status, update_date, note, crew, created_at from rws_zone_updates order by created_at) t)
  );
end;$$;

-- ---------------------------------------------------------------------
-- edit-lock (锁定: import 不覆盖锁住的值) — 用 uuid token
-- ---------------------------------------------------------------------
create table if not exists public.rws_lock (
  k text primary key, locked boolean not null default true,
  updated_by text, updated_at timestamptz not null default now());
alter table public.rws_lock enable row level security;
revoke all on public.rws_lock from anon, authenticated;

create or replace function public.rws_set_lock(p_token uuid, p_k text, p_locked boolean)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record;
begin
  select * into s from _rws_session(p_token);
  if coalesce(p_locked,false) then
    insert into rws_lock(k,locked,updated_by,updated_at) values (p_k,true,s.username,now())
      on conflict (k) do update set locked=true, updated_by=s.username, updated_at=now();
  else delete from rws_lock where k = p_k; end if;
  return jsonb_build_object('ok',true);
end;$$;

create or replace function public.rws_get_locks(p_token uuid)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; v jsonb;
begin
  select * into s from _rws_session(p_token);
  select coalesce(jsonb_object_agg(k,true),'{}'::jsonb) into v from rws_lock where locked;
  return jsonb_build_object('ok',true,'locks',v);
end;$$;

-- ---------------------------------------------------------------------
-- GRANTS
-- ---------------------------------------------------------------------
grant execute on function
  public.rws_login(text,text),
  public.rws_check_session(uuid),
  public.rws_logout(uuid),
  public.rws_get_state(uuid),
  public.rws_update_element(uuid,text,text),
  public.rws_update_slab_qty(uuid,text,text,text,numeric),
  public.rws_add_zone_update(uuid,text,text,text,int,text,text,text,text),
  public.rws_update_qty(uuid,text,text,text,text,numeric),
  public.rws_update_plan_qty(uuid,text,text,text,numeric),
  public.rws_admin_activity_log(uuid,int),
  public.rws_admin_list_users(uuid),
  public.rws_admin_upsert_user(uuid,text,text,text,text,jsonb,boolean),
  public.rws_add_cat(uuid,text,text),
  public.rws_del_cat(uuid,text),
  public.rws_add_item(uuid,text,text,text,text,text),
  public.rws_del_item(uuid,text),
  public.rws_set_kv(uuid,text,text,jsonb,text,text),
  public.rws_set_lock(uuid,text,boolean),
  public.rws_get_locks(uuid)
to anon, authenticated;

-- ---------------------------------------------------------------------
-- BOOTSTRAP admin 账号 (密码 = admin123)
-- ---------------------------------------------------------------------
insert into rws_users (username, password_hash, display_name, role, allowed_scopes, active)
values ('admin', crypt('admin123', gen_salt('bf')), 'Site Admin', 'admin', '[]'::jsonb, true)
on conflict (username) do nothing;

-- 兜底: 若 admin 已存在, 也把密码强制设为 admin123
update rws_users set password_hash = crypt('admin123', gen_salt('bf')) where username = 'admin';

-- =====================================================================
-- 完成! 登录: admin / admin123
-- =====================================================================
