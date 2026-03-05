(function(){
  var sel = function(q){ return document.querySelector(q); };
  var fmtMs = function(ms){ return (ms != null && Number.isFinite(Number(ms))) ? new Date(Number(ms)).toLocaleString() : '-'; };
  function paintState(s){
    var el = sel('#stateBadge');
    el.textContent = s || 'UNKNOWN';
    el.className = 'badge ' + (s || '');
  }
  function paintMeter(id, v){
    var el = sel(id);
    if (!el) return;
    var pct = (typeof v === 'number' && isFinite(v)) ? Math.max(0, Math.min(1, v)) * 100 : 0;
    el.style.width = pct + '%';
  }
  function paintReasons(list){
    var ul = sel('#reasonsList');
    ul.innerHTML = '';
    if (!list || !Array.isArray(list) || list.length === 0){ ul.innerHTML = '<li>-</li>'; return; }
    list.slice(0, 8).forEach(function(r){ var li = document.createElement('li'); li.textContent = String(r); ul.appendChild(li); });
  }
  function renderPublic(j){
    paintState(j && j.state);
    paintMeter('#SBar', j && j.drivers && j.drivers.S);
    paintMeter('#CBar', j && j.drivers && j.drivers.C);
    paintMeter('#PBar', j && j.drivers && j.drivers.P);
    sel('#hDepth').textContent = (j && j.hysteresis && j.hysteresis.depth) != null ? j.hysteresis.depth : '-';
    sel('#hRecent').textContent = (j && j.hysteresis && j.hysteresis.recent_len) != null ? j.hysteresis.recent_len : '-';
    sel('#hash').textContent = (j && j.last_receipt_hash) || '-';
    var ws = (j && j.window) || {};
    sel('#window').textContent = fmtMs(ws.start_ms) + ' -> ' + fmtMs(ws.end_ms);
    paintReasons(j && j.reasons);
  }
  function fetchPublicState(){
    fetch('/public/state', { cache: 'no-store' }).then(function(r){ return r.ok ? r.json() : null; }).then(function(j){
      if (j && j.ok && j.available) { renderPublic(j); return; }
      return fetch('/ui/replay_last', { method: 'POST', headers: {'Content-Type':'application/json'}, body: '{}', cache: 'no-store' }).then(function(r2){ return r2.ok ? r2.json() : null; });
    }).then(function(j){
      if (!j || !j.replay) return;
      var body = j.replay.receipt_body || j.replay.body || {};
      var drv = body.drivers || {};
      renderPublic({ ok: true, available: true, state: body.state || 'UNKNOWN', drivers: { S: drv.S, C: drv.C, P: drv.P }, hysteresis: { depth: (body.hysteresis||{}).depth, recent_len: ((body.hysteresis||{}).recent_inband||[]).length }, reasons: body.reasons || body.reason_codes || [], window: body.window || {}, last_receipt_hash: 'fallback' });
    }).catch(function(){ renderPublic({ ok: false, available: false }); });
  }
  sel('#refreshBtn').addEventListener('click', fetchPublicState);
  setInterval(fetchPublicState, 2500);
  fetchPublicState();
})();
