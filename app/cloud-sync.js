
/* ---- Supabase cloud sync: accounts, per-record sync, offline queue ---- */
const SUPABASE_URL = 'https://qjdmcvbagozoyebjbwyh.supabase.co';
const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_ARZCPR5OQxq_Xa3_CbGT6g_yzKG47ni';
const rwsSb = window.supabase.createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);
// Hidden admin entry: open this file with #zradmin92 in the URL. Change this
// string to your own private one before you hand the file to anyone else —
// treat it like a second password. Nobody sees an admin option without it
// AND a logged-in admin account.
const RWS_ADMIN_HASH = '#zradmin92';
function rwsIsAdminEntryRequested(){ return window.location.hash === RWS_ADMIN_HASH; }
const RWS_SESSION_KEY = 'rws_session';
function rwsGetSession(){ try{ return JSON.parse(localStorage.getItem(RWS_SESSION_KEY)||'null'); }catch(e){ return null; } }
function rwsSetSession(s){ try{ localStorage.setItem(RWS_SESSION_KEY, JSON.stringify(s)); }catch(e){} }
function rwsClearSession(){ try{ localStorage.removeItem(RWS_SESSION_KEY); }catch(e){} }
function rwsHandleExpired(){
  rwsClearSession();
  const app=window.__rwsApp;
  if(app){ app._rwsUser=null; try{app.rwsRenderUserBar();}catch(e){} const g=app.root&&app.root.querySelector('#rwsAuthGate'); if(g)g.style.display='flex'; const err=app.root&&app.root.querySelector('#rwsLoginErr'); if(err){err.textContent='Your session expired — please sign in again.';err.style.display='';} }
}
async function rwsCall(fn, args){
  try{
    const { data, error } = await rwsSb.rpc(fn, args);
    if (error) {
      const msg = (error.message || '').toLowerCase();
      const expired = msg.includes('invalid or expired');
      const rejected = msg.includes('not permitted') || msg.includes('admin only') ||
        msg.includes('bad ') || msg.includes('invalid username') || expired;
      if (expired && fn !== 'rws_check_session') rwsHandleExpired();
      return { ok:false, error, rejected, offline:false };
    }
    return { ok:true, data };
  }catch(networkErr){ return { ok:false, error:networkErr, offline:true }; }
}
async function rwsLogin(username, password){
  const r = await rwsCall('rws_login', { p_username:username, p_password:password });
  if (!r.ok) throw new Error(r.error && r.error.message ? r.error.message : 'login failed');
  rwsSetSession(r.data); return r.data;
}
async function rwsLogout(){ const s=rwsGetSession(); if(s) await rwsCall('rws_logout',{p_token:s.token}); rwsClearSession(); }
async function rwsRestoreSession(){
  const s = rwsGetSession(); if (!s) return null;
  const r = await rwsCall('rws_check_session', { p_token: s.token });
  if (r.ok && r.data===null){ rwsClearSession(); return null; } // confirmed expired -> force re-login
  if (!r.ok || !r.data) return s; // offline / transient — keep the cached session so the app still works
  const merged = { ...s, ...r.data }; rwsSetSession(merged); return merged;
}
const RWS_QUEUE_KEY = 'rws_offline_queue';
function rwsQueueList(){ try{ return JSON.parse(localStorage.getItem(RWS_QUEUE_KEY)||'[]'); }catch(e){ return []; } }
function rwsQueueSave(q){ try{ localStorage.setItem(RWS_QUEUE_KEY, JSON.stringify(q)); }catch(e){} }
function rwsQueuePush(fn, args){ const q=rwsQueueList(); q.push({id:Date.now()+'_'+Math.random().toString(36).slice(2),fn,args,ts:Date.now()}); rwsQueueSave(q); }
function rwsQueueSize(){ return rwsQueueList().length; }
let _rwsFlushing = false;
async function rwsQueueFlush(){
  if (_rwsFlushing) return; _rwsFlushing = true;
  try{
    let q = rwsQueueList();
    while (q.length) {
      const item = q[0];
      const r = await rwsCall(item.fn, item.args);
      if (r.ok) { q.shift(); rwsQueueSave(q); }
      else if (r.offline) { break; }
      else { console.warn('[rws] dropping queued edit, server rejected it:', item, r.error); q.shift(); rwsQueueSave(q); }
    }
  } finally { _rwsFlushing = false; }
  rwsNotifyFail(r); if (window.__rwsApp) window.__rwsApp.rwsOnQueueChange();
}
window.addEventListener('online', rwsQueueFlush);
setInterval(rwsQueueFlush, 20000);
/* 同步被后端拒绝(非离线)时提示一下 —— 以前是静默失败, 用户以为存了其实没进云端 */
function rwsNotifyFail(r){
  if (r && !r.ok && !r.offline && window.__rwsApp && window.__rwsApp._toast){
    var m = (r.error && r.error.message) ? r.error.message : 'change not saved to cloud';
    window.__rwsApp._toast('⚠ 未同步 / not saved: ' + m);
  }
}
async function rwsSyncKV(store, key, value, level, zoneMk){
  if (rwsSnapBlocked()) return { ok:false, readonly:true };
  const s = rwsGetSession(); if (!s) return { ok:false };
  const args = { p_token:s.token, p_store:store, p_k:key, p_value:(value==null?null:value), p_level:level||null, p_zone_mk:zoneMk||null };
  const r = await rwsCall('rws_set_kv', args);
  if (!r.ok && r.offline) rwsQueuePush('rws_set_kv', args);
  rwsNotifyFail(r); if (window.__rwsApp) window.__rwsApp.rwsOnQueueChange();
  return r;
}
async function rwsAddCat(code,label){const s=rwsGetSession();if(!s)return{ok:false};const a={p_token:s.token,p_code:code,p_label:label};const r=await rwsCall('rws_add_cat',a);if(!r.ok&&r.offline)rwsQueuePush('rws_add_cat',a);rwsNotifyFail(r);if(window.__rwsApp)window.__rwsApp.rwsOnQueueChange();return r;}
async function rwsDelCat(code){const s=rwsGetSession();if(!s)return{ok:false};const a={p_token:s.token,p_code:code};const r=await rwsCall('rws_del_cat',a);if(!r.ok&&r.offline)rwsQueuePush('rws_del_cat',a);rwsNotifyFail(r);if(window.__rwsApp)window.__rwsApp.rwsOnQueueChange();return r;}
async function rwsAddItem(itemKey,level,zoneMk,type,elemId){const s=rwsGetSession();if(!s)return{ok:false};const a={p_token:s.token,p_item_key:itemKey,p_level:level,p_zone_mk:zoneMk,p_type:type,p_elem_id:elemId};const r=await rwsCall('rws_add_item',a);if(!r.ok&&r.offline)rwsQueuePush('rws_add_item',a);rwsNotifyFail(r);if(window.__rwsApp)window.__rwsApp.rwsOnQueueChange();return r;}
async function rwsDelItem(itemKey){const s=rwsGetSession();if(!s)return{ok:false};const a={p_token:s.token,p_item_key:itemKey};const r=await rwsCall('rws_del_item',a);if(!r.ok&&r.offline)rwsQueuePush('rws_del_item',a);rwsNotifyFail(r);if(window.__rwsApp)window.__rwsApp.rwsOnQueueChange();return r;}
async function rwsGetState(token){
  const r = await rwsCall('rws_get_state', { p_token: token });
  if (!r.ok) throw new Error(r.error && r.error.message ? r.error.message : 'failed to load state');
  return r.data;
}
async function rwsSyncElementStatus(elementKey, status){
  if (rwsSnapBlocked()) return { ok:false, readonly:true };
  const s = rwsGetSession(); if (!s) return { ok:false };
  const args = { p_token:s.token, p_element_key:elementKey, p_status:status };
  const r = await rwsCall('rws_update_element', args);
  if (!r.ok && r.offline) rwsQueuePush('rws_update_element', args);
  rwsNotifyFail(r); if (window.__rwsApp) window.__rwsApp.rwsOnQueueChange();
  return r;
}
async function rwsSyncSlabQty(qtyKey, level, zoneMk, qty){
  if (rwsSnapBlocked()) return { ok:false, readonly:true };
  const s = rwsGetSession(); if (!s) return { ok:false };
  const args = { p_token:s.token, p_qty_key:qtyKey, p_level:level, p_zone_mk:zoneMk, p_qty:qty };
  const r = await rwsCall('rws_update_slab_qty', args);
  if (!r.ok && r.offline) rwsQueuePush('rws_update_slab_qty', args);
  rwsNotifyFail(r); if (window.__rwsApp) window.__rwsApp.rwsOnQueueChange();
  return r;
}
async function rwsAddZoneUpdate(a){
  if (rwsSnapBlocked()) return { ok:false, readonly:true };
  const s = rwsGetSession(); if (!s) return { ok:false };
  const args = { p_token:s.token, p_zone_mk:a.zoneMk, p_level:a.level, p_zone_label:a.zoneLabel, p_pct:a.pct, p_status:a.status, p_date:a.date, p_note:a.note, p_crew:a.crew };
  const r = await rwsCall('rws_add_zone_update', args);
  if (!r.ok && r.offline) rwsQueuePush('rws_add_zone_update', args);
  rwsNotifyFail(r); if (window.__rwsApp) window.__rwsApp.rwsOnQueueChange();
  return r;
}
async function rwsSyncQty(qtyKey, level, zoneMk, field, value){
  const s = rwsGetSession(); if (!s) return { ok:false };
  const args = { p_token:s.token, p_qty_key:qtyKey, p_level:level, p_zone_mk:zoneMk, p_field:field, p_value:value };
  const r = await rwsCall('rws_update_qty', args);
  if (!r.ok && r.offline) rwsQueuePush('rws_update_qty', args);
  rwsNotifyFail(r); if (window.__rwsApp) window.__rwsApp.rwsOnQueueChange();
  return r;
}
async function rwsSyncPlanQty(planKey, level, zoneMk, value){
  const s = rwsGetSession(); if (!s) return { ok:false };
  const args = { p_token:s.token, p_plan_key:planKey, p_level:level, p_zone_mk:zoneMk, p_value:value };
  const r = await rwsCall('rws_update_plan_qty', args);
  if (!r.ok && r.offline) rwsQueuePush('rws_update_plan_qty', args);
  rwsNotifyFail(r); if (window.__rwsApp) window.__rwsApp.rwsOnQueueChange();
  return r;
}
/* ---- 进度快照(存/列/取/删) ---- */
function rwsSnapBlocked(){ return !!(window.__rwsApp && window.__rwsApp._snapView); }   // 正在看历史快照时禁止一切写入
async function rwsSnapshotSave(label, data){ const s=rwsGetSession(); if(!s) return {ok:false}; const r=await rwsCall('rws_snapshot_save',{p_token:s.token,p_label:label||null,p_data:data}); /* 失败不弹"未同步"红字, 由调用方(rwsSaveSnapshot)决定是否提示, 避免误以为进度没存 */ return r; }
async function rwsSnapshotList(){ const s=rwsGetSession(); if(!s) return {ok:false}; return await rwsCall('rws_snapshot_list',{p_token:s.token}); }
async function rwsSnapshotGet(id){ const s=rwsGetSession(); if(!s) return {ok:false}; return await rwsCall('rws_snapshot_get',{p_token:s.token,p_id:id}); }
async function rwsSnapshotDelete(id){ const s=rwsGetSession(); if(!s) return {ok:false}; const r=await rwsCall('rws_snapshot_delete',{p_token:s.token,p_id:id}); rwsNotifyFail(r); return r; }
async function rwsAdminActivityLog(limit){ const s=rwsGetSession(); if(!s) throw new Error('not logged in'); const r=await rwsCall('rws_admin_activity_log',{p_token:s.token,p_limit:limit||300}); if(!r.ok) throw new Error(r.error&&r.error.message||'failed'); return r.data; }
async function rwsAdminListUsers(){ const s=rwsGetSession(); if(!s) throw new Error('not logged in'); const r=await rwsCall('rws_admin_list_users',{p_token:s.token}); if(!r.ok) throw new Error(r.error&&r.error.message||'failed'); return r.data; }
async function rwsAdminUpsertUser(u){ const s=rwsGetSession(); if(!s) throw new Error('not logged in'); const r=await rwsCall('rws_admin_upsert_user',{p_token:s.token,p_username:u.username,p_password:u.password||null,p_display_name:u.displayName||'',p_role:u.role,p_allowed_scopes:u.allowedScopes||[],p_active:u.active!==false}); if(!r.ok) throw new Error(r.error&&r.error.message||'failed'); return r.data; }
