-- ============================================================
-- 账号管理补两个能力: 删除账号 / 改名(不新建).
--   rws_admin_delete_user  — 删除账号(连它的登录会话一起删); 不能删自己
--   rws_admin_rename_user  — 把账号改名(更新原行, 不会多出一个新账号); 新名不能和已有账号重名
-- 两者都仅 admin 可用(security definer + 会话校验).
-- 在 Supabase SQL Editor 整段跑一次即可(可重复跑).
-- ============================================================

create or replace function public.rws_admin_delete_user(p_token uuid, p_username text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record; uid uuid;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  if p_username = s.username then raise exception 'cannot delete your own account'; end if;
  select id into uid from rws_users where username = p_username;
  if uid is null then raise exception 'user not found: %', p_username; end if;
  delete from rws_sessions where user_id = uid;   -- 让该账号已登录的会话失效
  delete from rws_users where id = uid;
  return jsonb_build_object('ok', true);
end;$$;

create or replace function public.rws_admin_rename_user(p_token uuid, p_old text, p_new text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s record;
begin
  select * into s from _rws_session(p_token);
  if s.role <> 'admin' then raise exception 'admin only'; end if;
  p_new := trim(p_new);
  if p_new = '' then raise exception 'new username is empty'; end if;
  if p_old = p_new then return jsonb_build_object('ok', true); end if;
  if exists(select 1 from rws_users where username = p_new) then raise exception 'username already exists: %', p_new; end if;
  update rws_users set username = p_new where username = p_old;
  if not found then raise exception 'user not found: %', p_old; end if;
  return jsonb_build_object('ok', true);
end;$$;
