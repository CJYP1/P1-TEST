-- ============================================================
-- 防止"有权限但非 admin"的人把已录入的数字改小(例如把 Done 3 改成 2)
-- 规则:非 admin 只能把完成量/数量往上加或持平, 不能改小;要改小请用 admin 账号。
-- admin 不受限制(可以更正)。所有改动仍照旧写进 rws_activity_log。
-- 在 Supabase 的 SQL Editor 里整段跑一次即可(可重复跑, create or replace)。
-- ============================================================

-- 1) 月度完成量 act_done_m(活动卡里手填的 Done)---------------------
create or replace function public.rws_set_kv(p_token uuid, p_store text, p_k text, p_value jsonb, p_level text, p_zone_mk text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; old jsonb;
begin
  select * into s from _rws_session(p_token);
  if p_store not in ('act_total','act_plan','act_done_m','act_hidden','elem_date','act_def','crit','zdate','act_date','col_month','act_cmt') then raise exception 'bad store'; end if;
  if s.role <> 'admin' then
    if p_store in ('act_total','act_plan','act_hidden','act_def','crit','zdate','act_date','col_month') then raise exception 'admin only'; end if;
    if p_store = 'act_cmt' then
      if not ( (coalesce(s.allowed_scopes,'[]'::jsonb) ? 'CMT') or _rws_area_ok(s.allowed_scopes, p_level, p_zone_mk) ) then raise exception 'not permitted: no comment or area permission'; end if;
    else
      if not _rws_area_ok(s.allowed_scopes, p_level, p_zone_mk) then raise exception 'not permitted: outside your assigned area'; end if;
    end if;
  end if;
  select value into old from rws_kv where store = p_store and k = p_k;
  -- 防改小:非 admin 不能把已录入的 Done(act_done_m)改小
  if s.role <> 'admin' and p_store = 'act_done_m' and p_value is not null and old is not null
     and jsonb_typeof(p_value) = 'number' and jsonb_typeof(old) = 'number'
     and (p_value#>>'{}')::numeric < (old#>>'{}')::numeric then
    raise exception 'not permitted: 已录入的 Done 不能改小(% -> %),要改小请找 admin', (old#>>'{}'), (p_value#>>'{}');
  end if;
  if p_value is null then delete from rws_kv where store = p_store and k = p_k;
  else insert into rws_kv(store,k,value,level,zone_mk,updated_by,updated_at) values (p_store,p_k,p_value,p_level,p_zone_mk,s.user_id,now())
    on conflict (store,k) do update set value=excluded.value, level=excluded.level, zone_mk=excluded.zone_mk, updated_by=excluded.updated_by, updated_at=now(); end if;
  insert into rws_activity_log(user_id,username,action,target_key,old_value,new_value) values (s.user_id,s.username,p_store,p_k,old,p_value);
  return jsonb_build_object('ok',true);
end;$$;

-- 2) Slab / Pilecap 数量 rws_slab_qty ------------------------------
create or replace function public.rws_update_slab_qty(p_token uuid, p_qty_key text, p_level text, p_zone_mk text, p_qty numeric)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; old_qty numeric;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' and not _rws_area_ok(s.allowed_scopes, p_level, p_zone_mk) then
    raise exception 'not permitted: outside your assigned area'; end if;
  select qty into old_qty from rws_slab_qty where qty_key = p_qty_key;
  -- 防改小:非 admin 不能把已录入的数量改小
  if s.role <> 'admin' and old_qty is not null and p_qty < old_qty then
    raise exception 'not permitted: 已录入的数量不能改小(% -> %),要改小请找 admin', old_qty, p_qty;
  end if;
  insert into rws_slab_qty(qty_key, level, zone_mk, qty, updated_by, updated_at)
    values (p_qty_key, p_level, p_zone_mk, p_qty, s.user_id, now())
  on conflict (qty_key) do update set qty = excluded.qty, updated_by = excluded.updated_by, updated_at = now();
  insert into rws_activity_log(user_id, username, action, target_key, old_value, new_value)
    values (s.user_id, s.username, 'slab_qty', p_qty_key, to_jsonb(old_qty), to_jsonb(p_qty));
  return jsonb_build_object('ok', true, 'qty_key', p_qty_key, 'qty', p_qty);
end;$$;
