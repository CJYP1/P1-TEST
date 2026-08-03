-- ============================================================
-- 修复 "bad store / 未同步":后端补上 settings / edited / manpower 三个 store。
--   settings, edited  → 仅 admin 可写(全局设置 / 锁定标记)
--   manpower          → 有本区权限即可写(现场可填人数)
--   act_done_m        → 保留"非 admin 不能改小"的防改小规则
-- 同时 rws_get_state 把这三个返回,才能在各端读回来。
-- 在 Supabase SQL Editor 整段跑一次(可重复跑)。
-- ============================================================

create or replace function public.rws_set_kv(p_token uuid, p_store text, p_k text, p_value jsonb, p_level text, p_zone_mk text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; old jsonb;
begin
  select * into s from _rws_session(p_token);
  if p_store not in ('act_total','act_plan','act_done_m','act_hidden','elem_date','act_def','crit','zdate','act_date','col_month','act_cmt','settings','edited','manpower') then
    raise exception 'bad store'; end if;
  if s.role <> 'admin' then
    if p_store in ('act_total','act_plan','act_hidden','act_def','crit','zdate','act_date','col_month','settings','edited') then
      raise exception 'admin only'; end if;
    if p_store = 'act_cmt' then
      if not ( (coalesce(s.allowed_scopes,'[]'::jsonb) ? 'CMT') or _rws_area_ok(s.allowed_scopes, p_level, p_zone_mk) ) then raise exception 'not permitted: no comment or area permission'; end if;
    else
      -- act_done_m / elem_date / manpower: 需本区权限
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

create or replace function public.rws_get_state(p_token uuid)
returns jsonb language plpgsql security definer set search_path = public as $$
begin
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
    'settings',   (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='settings'),
    'edited',     (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='edited'),
    'manpower',   (select coalesce(jsonb_object_agg(k, value), '{}'::jsonb) from rws_kv where store='manpower'),
    'custom_cats', (select coalesce(jsonb_agg(jsonb_build_object('code',code,'label',label) order by created_at), '[]'::jsonb) from rws_custom_cat),
    'custom_items', (select coalesce(jsonb_agg(jsonb_build_object('item_key',item_key,'level',level,'zone_mk',zone_mk,'type',type,'elem_id',elem_id) order by created_at), '[]'::jsonb) from rws_custom_item),
    'zone_updates', (select coalesce(jsonb_agg(row_to_json(t)), '[]'::jsonb) from (
       select zone_mk, level, zone_label, pct, status, update_date, note, crew, created_at from rws_zone_updates order by created_at) t)
  );
end;$$;
