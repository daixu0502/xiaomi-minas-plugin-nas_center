(function () {
  'use strict';
  var document = window.XiaomiPluginClient.document;
  var panel = document.getElementById('processDetail'), body = document.getElementById('processBody');
  var mode = '', generation = 0, busy = false, timer = null, data = null, focus = null, limit = 50;
  var id = function (s) { return document.getElementById(s); };
  function node(tag, cls, text) { var e = document.createElement(tag); e.className = cls || ''; if (text !== undefined) e.textContent = text; return e; }
  function bytes(n) { if (n == null) return '—'; var u = ['B', 'KB', 'MB', 'GB'], i = 0; while (n >= 1024 && i < 3) { n /= 1024; i++; } return n.toFixed(i ? 1 : 0) + ' ' + u[i]; }
  function rate(n) { return n == null ? '暂不可用' : bytes(n) + '/s'; }
  function cpu(n) { return n == null ? '采样中' : n.toFixed(2) + '%'; }
  function request(action, payload) {
    return window.XiaomiPluginClient.request({plugin:'nascenter', cgi:'nascenter.cgi', action:action,
      options:{method:'POST', credentials:'same-origin', cache:'no-store', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload || {})}})
      .then(function (r) { return r.json(); }).then(function (d) { if (!d.ok) throw Error(d.error || '读取失败'); return d; });
  }
  function processRow(row, kind) {
    var e = node('article', 'process-row'), copy = node('div', 'process-copy');
    copy.appendChild(node('strong', '', row.name));
    copy.appendChild(node('small', '', 'PID ' + row.pid + ' · ' + row.description));
    e.appendChild(copy); var value = node('div', 'process-value');
    value.appendChild(node('strong', '', kind === 'memory' ? bytes(row.rss) : cpu(row.cpu)));
    value.appendChild(node('small', '', kind === 'memory' ? row.memoryPercent.toFixed(2) + '% · RSS' : '内存 ' + bytes(row.rss)));
    e.appendChild(value); return e;
  }
  function draw() {
    if (!data) return;
    var expanded = new Set(Array.prototype.map.call(body.querySelectorAll('details[open]'), function (e) { return e.dataset.key; }));
    var fragment = document.createDocumentFragment(), query = id('processSearch').value.trim().toLowerCase();
    if (mode === 'health') {
      var reasons = node('section', 'process-reasons');
      reasons.appendChild(node('h3', '', data.reasons.length ? '本次触发原因' : '本次采样未达到告警阈值'));
      (data.reasons.length ? data.reasons : ['首页提示与当前采样可能因负载波动不同。以下为当前占用最高的进程，不代表它们一定异常。']).forEach(function (s) { reasons.appendChild(node('p', '', s)); });
      fragment.appendChild(reasons);
      ['cpu', 'memory'].forEach(function (kind) {
        fragment.appendChild(node('h3', 'process-heading', kind === 'cpu' ? 'CPU 占用前 10' : '内存占用前 10'));
        data[kind].forEach(function (r) { fragment.appendChild(processRow(r, kind)); });
      });
      fragment.appendChild(node('p', 'process-note', data.note + ' 高负载只表示资源压力，可能是正常下载、备份或索引；未执行终止进程或清理操作。'));
    } else {
      var rows = data.rows.filter(function (r) { return !query || (r.name + ' ' + (r.pid || (r.pids || []).join(' ')) + ' ' + r.description).toLowerCase().indexOf(query) >= 0; });
      fragment.appendChild(node('p', 'process-note', mode === 'network' ? data.warnings.join('\n') : data.note));
      fragment.appendChild(node('p', 'process-note', '共 ' + rows.length + ' 项 · ' + (mode === 'network' ? '按已测 TCP 收发速度合计降序；展开查看目标' : '从高到低实时排序')));
      rows.slice(0, limit).forEach(function (r) {
        if (mode !== 'network') { fragment.appendChild(processRow(r, mode)); return; }
        var details = node('details', 'process-network'); details.dataset.key = r.key; details.open = expanded.has(r.key);
        var summary = node('summary'), copy = node('div', 'process-copy');
        copy.appendChild(node('strong', '', r.name));
        copy.appendChild(node('small', '', 'PID ' + (r.pids.join(', ') || '未知') + ' · ' + r.connections.length + ' 个连接' + (r.pids.length > 1 ? ' · 共享套接字' : '')));
        copy.appendChild(node('small', '', r.description)); summary.appendChild(copy);
        summary.appendChild(node('span', 'process-value', '↓ ' + rate(r.measured ? r.rx : null) + '\n↑ ' + rate(r.measured ? r.tx : null)));
        details.appendChild(summary);
        r.connections.forEach(function (c) {
          var line = node('div', 'process-connection');
          line.appendChild(node('strong', '', c.protocol + ' · ' + c.remote));
          line.appendChild(node('span', '', c.scope + ' · 本地 ' + c.local));
          line.appendChild(node('span', '', c.reason || '↓ ' + rate(c.rx) + '  ↑ ' + rate(c.tx)));
          details.appendChild(line);
        }); fragment.appendChild(details);
      });
      if (!rows.length) fragment.appendChild(node('p', 'empty-detail', '没有符合条件的进程或连接'));
      if (rows.length > limit) { var more = node('button', 'secondary-button', '再显示 50 项'); more.type = 'button'; more.addEventListener('click', function () { limit += 50; draw(); }); fragment.appendChild(more); }
    }
    var scroll = body.scrollTop; body.replaceChildren(fragment); body.scrollTop = scroll;
  }
  function poll() {
    if (!mode || busy || window.document.hidden || !panel.isConnected) return;
    var token = generation, requestedMode = mode; busy = true; id('refreshProcess').disabled = true;
    id('refreshProcess').textContent = '采样中…';
    request(mode === 'network' ? 'process_network' : mode === 'health' ? 'health_details' : 'processes', {kind:mode})
      .then(function (d) { if (token !== generation) return; data = d; draw(); id('processStatus').textContent = '更新于 ' + new Date(d.timestamp * 1000).toLocaleTimeString() + ' · 采样完成后 3 秒刷新'; })
      .catch(function (e) { if (token !== generation) return; id('processStatus').textContent = '读取失败：' + e.message + (data ? '（以下保留上次数据）' : ''); })
      .finally(function () { busy = false; id('refreshProcess').disabled = false; id('refreshProcess').textContent = '刷新'; if (mode && panel.isConnected) { clearTimeout(timer); timer = setTimeout(poll, token === generation ? 3000 : 0); } });
  }
  function open(kind) {
    focus = document.activeElement; generation++; mode = kind; data = null; limit = 50;
    id('processTitle').textContent = {cpu:'CPU 进程', memory:'内存进程', network:'进程网络', health:'负载与健康详情'}[kind];
    id('processSearch').hidden = kind === 'health'; id('processSearch').value = '';
    id('processStatus').textContent = '正在采样，请稍候…'; body.textContent = ''; body.scrollTop = 0;
    panel.hidden = false; id('processBackdrop').hidden = false; id('closeProcess').focus(); clearTimeout(timer); poll();
  }
  function close() { mode = ''; generation++; clearTimeout(timer); panel.hidden = true; id('processBackdrop').hidden = true; if (focus) focus.focus({preventScroll:true}); }
  function entry(e, kind, label) {
    e.classList.add('process-entry'); e.setAttribute('role', 'button'); e.tabIndex = 0; e.setAttribute('aria-label', label); e.setAttribute('aria-haspopup', 'dialog');
    e.addEventListener('click', function () { open(kind); });
    e.addEventListener('keydown', function (event) { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open(kind); } });
    e.appendChild(node('span', 'process-entry-hint', '查看详情 ›'));
  }
  entry(id('cpuUsage').closest('.metric'), 'cpu', '查看 CPU 进程');
  entry(id('memoryUsage').closest('.metric'), 'memory', '查看内存进程');
  entry(id('rxSpeed').closest('.panel'), 'network', '查看进程网络');
  entry(id('healthBadge').closest('.plugin-status'), 'health', '查看负载与健康详情');
  id('closeProcess').addEventListener('click', close); id('processBackdrop').addEventListener('click', close);
  id('refreshProcess').addEventListener('click', function () { clearTimeout(timer); poll(); });
  id('processSearch').addEventListener('input', function () { limit = 50; draw(); });
  document.addEventListener('keydown', function (e) {
    if (panel.hidden) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); close(); }
    if (e.key === 'Tab') {
      var items = Array.prototype.filter.call(panel.querySelectorAll('button,input,summary,[tabindex="0"]'), function (n) { return !n.hidden && !n.disabled; });
      var first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }, true);
  window.document.addEventListener('visibilitychange', function () { if (!window.document.hidden && mode) poll(); });
})();
