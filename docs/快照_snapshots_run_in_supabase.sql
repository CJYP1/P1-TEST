-- ============================================================
-- 进度快照:把某一刻的完整"实际进度"状态存到云端, 以后可以调出来看
-- (七月看六月做到哪)。存的是 rws_get_state 的完整结果。
-- 在 Supabase SQL Editor 整段跑一次即可(可重复跑)。
-- ============================================================

create table if not exists public.rws_snapshots(
  id         bigserial primary key,
  taken_at   timestamptz not null default now(),
  label      text,
  data       jsonb not null,
  created_by uuid
);
create index if not exists rws_snapshots_taken_idx on public.rws_snapshots(taken_at desc);

-- 存快照:admin only
create or replace function public.rws_snapshot_save(p_token uuid, p_label text, p_data jsonb)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; new_id bigint; ts timestamptz;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  insert into rws_snapshots(label, data, created_by) values (p_label, p_data, s.user_id)
    returning id, taken_at into new_id, ts;
  return jsonb_build_object('ok', true, 'id', new_id, 'taken_at', ts);
end;$$;

-- 列快照(不含 data, 只列日期/标签):admin 或有 HIST 权限
create or replace function public.rws_snapshot_list(p_token uuid)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; out jsonb;
begin
  select * into s from _rws_session(p_token);   -- 校验登录(过期会 raise)
  if s.role <> 'admin' and not (coalesce(s.allowed_scopes,'[]'::jsonb) ? 'HIST') then
    raise exception 'not permitted: no history access'; end if;
  select coalesce(jsonb_agg(jsonb_build_object('id',id,'taken_at',taken_at,'label',label) order by taken_at desc), '[]'::jsonb)
    into out from rws_snapshots;
  return out;
end;$$;

-- 取某个快照的完整数据:admin 或有 HIST 权限
create or replace function public.rws_snapshot_get(p_token uuid, p_id bigint)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; row rws_snapshots%rowtype;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' and not (coalesce(s.allowed_scopes,'[]'::jsonb) ? 'HIST') then
    raise exception 'not permitted: no history access'; end if;
  select * into row from rws_snapshots where id = p_id;
  if not found then raise exception 'snapshot not found'; end if;
  return jsonb_build_object('id',row.id,'taken_at',row.taken_at,'label',row.label,'data',row.data);
end;$$;

-- 删快照:admin only
create or replace function public.rws_snapshot_delete(p_token uuid, p_id bigint)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  delete from rws_snapshots where id = p_id;
  return jsonb_build_object('ok', true);
end;$$;
