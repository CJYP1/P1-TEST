-- =====================================================================
-- 追加功能: 用户自助注册 + 修改 admin 密码
-- 在你那份主 SQL 跑完之后, 再单独跑这一段(Supabase SQL Editor)。
-- 可重复运行, 安全。
-- =====================================================================

-- 1) 把 admin 密码改成 admin123
update public.rws_users
   set password_hash = crypt('admin123', gen_salt('bf'))
 where username = 'admin';

-- 2) 自助注册函数: 任何人可注册, 但注册后 active=false(停用),
--    必须由 admin 在后台激活后才能登录。角色固定为 'user'。
create or replace function public.rws_register(p_username text, p_password text, p_display_name text)
returns jsonb language plpgsql security definer set search_path = public, extensions as $$
declare uid uuid;
begin
  -- 基本校验
  if p_username is null or length(trim(p_username)) < 2 then
    raise exception '用户名太短';
  end if;
  if p_password is null or length(p_password) < 4 then
    raise exception '密码至少4位';
  end if;
  -- 用户名占用检查
  if exists (select 1 from rws_users where username = trim(p_username)) then
    raise exception '该用户名已被注册';
  end if;
  -- 建号: active=false(等管理员激活), role=user
  insert into rws_users(username, password_hash, display_name, role, allowed_scopes, active)
    values (trim(p_username), crypt(p_password, gen_salt('bf')),
            coalesce(nullif(trim(p_display_name),''), trim(p_username)),
            'user', '[]'::jsonb, false)
    returning id into uid;
  insert into rws_activity_log(user_id, username, action, target_key)
    values (uid, trim(p_username), 'register', null);
  return jsonb_build_object('ok', true, 'pending', true);
end;
$$;

-- 3) 开放给匿名 key 调用(注册是登录前的动作, 必须匿名可调)
grant execute on function public.rws_register(text,text,text) to anon, authenticated;

-- =====================================================================
-- 说明:
-- * 用户在网页点"注册" -> 填用户名/密码 -> 提交后提示"等待管理员激活"
-- * 你以 admin 登录 -> 账号管理里, 把该用户 active 打开(激活)
-- * 激活后该用户才能登录, 权限是普通 user
-- * 以后若要加"注册邀请码", 告诉我, 给 rws_register 加个 p_code 参数
--   和一行校验即可, 不影响已注册的人。
-- =====================================================================
