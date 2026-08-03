-- ============================================================
-- 登录时顺便记下客户端 IP(x-forwarded-for), 存进活动日志的 target_key。
-- 这样 admin 的 "🔑 Logins" 就能看到同一账号是不是从不同 IP 登录的。
-- 说明: IP 是客户端公网 IP —— 同一办公室/WiFi 的人会是同一个 IP;
--       换了地方/换了网络才会不同。只对"跑这段之后"的新登录生效。
-- 在 Supabase SQL Editor 整段跑一次即可(可重复跑)。
-- ============================================================
create or replace function public.rws_login(p_username text, p_password text)
returns jsonb language plpgsql security definer set search_path = public, extensions as $$
declare u record; tok uuid; ip text;
begin
  select * into u from rws_users where username = p_username and active limit 1;
  if not found or u.password_hash <> crypt(p_password, u.password_hash) then
    raise exception 'invalid username or password';
  end if;
  -- 从请求头取客户端 IP(x-forwarded-for 第一个); 取不到就留空
  begin
    ip := split_part(coalesce((current_setting('request.headers', true)::json)->>'x-forwarded-for', ''), ',', 1);
    if ip is null or trim(ip) = '' then
      ip := (current_setting('request.headers', true)::json)->>'x-real-ip';
    end if;
  exception when others then ip := null; end;
  insert into rws_sessions(user_id, expires_at) values (u.id, now() + interval '18 hours') returning token into tok;
  insert into rws_activity_log(user_id, username, action, target_key)
    values (u.id, u.username, 'login', nullif(trim(coalesce(ip,'')),''));
  return jsonb_build_object('token', tok, 'user_id', u.id, 'username', u.username,
    'display_name', u.display_name, 'role', u.role, 'allowed_scopes', u.allowed_scopes);
end;$$;
