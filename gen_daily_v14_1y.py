"""生成V14(5%/4%)近1年每日操作明细及净值的HTML报告"""
import json

with open('v14_detail_1y.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

daily = d['daily_records']
switches = d['switches']

# 切换日集合，用于高亮
switch_dates = {s['date']: s for s in switches}

# 8个指数名称
stock_names = ['上证50', '创业板50', '纳斯达克100', '沪深300', '中证500', '中证1000', '标普500', '科创50']

# 构建表格行数据
rows_js = []
for i, r in enumerate(daily):
    sw = switch_dates.get(r['date'])
    is_sw = 1 if sw else 0
    sw_type = sw['switch_type'] if sw else ''
    sw_from = sw['from'] if sw else ''
    sw_to = sw['to'] if sw else ''
    sw_reason = sw['reason'] if sw else ''
    # bf值
    bf_vals = r.get('bf', {})
    row = {
        'date': r['date'],
        'position': r['position'],
        'signal': r['signal'],
        'ret': r['ret'],
        'nav': r['nav'],
        'raw_nav': r['raw_nav'],
        'raw_dd': r['raw_dd'],
        'cb_status': r['cb_status'],
        'is_switch': is_sw,
        'sw_type': sw_type,
        'sw_from': sw_from,
        'sw_to': sw_to,
        'sw_reason': sw_reason,
        'cost': r['cost'],
        'bf_vals': {k: bf_vals.get(k, 0) for k in stock_names},
        'idx': i,
    }
    rows_js.append(row)

rows_json = json.dumps(rows_js, ensure_ascii=False)

# 统计
n_days = len(daily)
n_switch = len(switches)
n_cb_days = sum(1 for r in daily if r['cb_status'] in ('TRIGGERED', 'IN_CB'))
n_normal_days = sum(1 for r in daily if r['cb_status'] == 'NORMAL')
n_released = sum(1 for r in daily if r['cb_status'] == 'RELEASED')

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>V14(5%/4%)策略 近1年每日操作明细及净值</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; background: #f5f6f8; color: #222; padding: 20px; }
h1 { font-size: 20px; margin-bottom: 6px; color: #1a1a2e; }
.subtitle { font-size: 13px; color: #666; margin-bottom: 16px; }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 18px; }
.card { background: #fff; border-radius: 8px; padding: 12px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.card .label { font-size: 11px; color: #888; margin-bottom: 4px; }
.card .value { font-size: 18px; font-weight: 600; color: #1a1a2e; }
.card .value.red { color: #d32f2f; }
.card .value.green { color: #2e7d32; }
.card .value.blue { color: #1565c0; }
.controls { background: #fff; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.controls input, .controls select { padding: 6px 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 13px; }
.controls input { width: 160px; }
.controls select { width: auto; }
.controls label { font-size: 12px; color: #555; display: flex; align-items: center; gap: 4px; }
.btn { padding: 6px 12px; border: none; border-radius: 5px; cursor: pointer; font-size: 12px; background: #e8eaf0; color: #333; }
.btn.active { background: #1565c0; color: #fff; }
.btn:hover { opacity: 0.85; }
.table-wrap { background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); overflow: hidden; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
thead th { position: sticky; top: 0; background: #f0f2f8; color: #333; font-weight: 600; padding: 9px 8px; text-align: center; border-bottom: 2px solid #d0d4e0; white-space: nowrap; cursor: pointer; user-select: none; z-index: 5; }
thead th:hover { background: #e4e7f0; }
thead th .sort-ind { font-size: 10px; color: #999; margin-left: 2px; }
tbody td { padding: 7px 8px; text-align: center; border-bottom: 1px solid #eef0f4; white-space: nowrap; }
tbody tr:hover { background: #f8f9fc; }
tbody tr.switch-row { background: #fff8e1; }
tbody tr.switch-row:hover { background: #fff3c4; }
tbody tr.cb-row { background: #fdecea; }
tbody tr.cb-row:hover { background: #f9d9d5; }
.pos { font-weight: 600; padding: 2px 8px; border-radius: 10px; font-size: 11px; display: inline-block; }
.pos-国债 { background: #e3f2fd; color: #1565c0; }
.pos-空仓 { background: #f5f5f5; color: #999; }
.pos-上证50, .pos-创业板50, .pos-沪深300, .pos-中证500, .pos-中证1000, .pos-标普500, .pos-科创50 { background: #e8f5e9; color: #2e7d32; }
.pos-纳斯达克100 { background: #fce4ec; color: #c2185b; }
.ret-pos { color: #d32f2f; font-weight: 600; }
.ret-neg { color: #2e7d32; font-weight: 600; }
.ret-zero { color: #999; }
.cb-NORMAL { color: #888; }
.cb-TRIGGERED { color: #d32f2f; font-weight: 700; }
.cb-IN_CB { color: #e65100; font-weight: 600; }
.cb-RELEASED { color: #2e7d32; font-weight: 600; }
.sw-badge { display: inline-block; padding: 1px 6px; border-radius: 8px; font-size: 10px; font-weight: 600; }
.sw-建仓 { background: #bbdefb; color: #0d47a1; }
.sw-轮动 { background: #c8e6c9; color: #1b5e20; }
.sw-触发 { background: #ffcdd2; color: #b71c1c; }
.sw-解除 { background: #fff9c4; color: #f57f17; }
.sw-空仓 { background: #e0e0e0; color: #555; }
.bf-cell { font-family: Consolas, monospace; font-size: 11px; }
.bf-top { background: #fff3e0; font-weight: 700; color: #e65100; }
.bf-neg { color: #2e7d32; }
.bf-pos { color: #d32f2f; }
.legend { background: #fff; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); font-size: 12px; color: #555; display: flex; flex-wrap: wrap; gap: 14px; align-items: center; }
.legend-item { display: flex; align-items: center; gap: 5px; }
.legend-swatch { width: 14px; height: 14px; border-radius: 3px; display: inline-block; }
.note { background: #fff; border-left: 4px solid #1565c0; border-radius: 4px; padding: 12px 16px; margin-top: 14px; font-size: 12px; color: #444; line-height: 1.7; }
.note b { color: #1565c0; }
.empty { padding: 30px; text-align: center; color: #999; }
</style>
</head>
<body>
<h1>V14 (5%/4%) 策略 — 近1年每日操作明细及净值</h1>
<div class="subtitle">期间: __START__ ~ __END__ | 交易日: __NDAYS__ 天 | 切换: __NSW__ 次 | 熔断天数: __NCB__ 天 (__CBPCT__%)</div>

<div class="summary">
  <div class="card"><div class="label">策略总收益</div><div class="value red">__TOT__</div></div>
  <div class="card"><div class="label">年化收益</div><div class="value red">__ANN__</div></div>
  <div class="card"><div class="label">最大回撤</div><div class="value green">__MDD__</div></div>
  <div class="card"><div class="label">夏普比率</div><div class="value blue">__SH__</div></div>
  <div class="card"><div class="label">切换次数</div><div class="value">__NSW2__</div></div>
  <div class="card"><div class="label">熔断天数占比</div><div class="value">__CBPCT2__%</div></div>
  <div class="card"><div class="label">总手续费</div><div class="value">__FEE__%</div></div>
  <div class="card"><div class="label">V8基线收益</div><div class="value">__V8__</div></div>
</div>

<div class="legend">
  <div class="legend-item"><span class="legend-swatch" style="background:#fff8e1;"></span>切换日</div>
  <div class="legend-item"><span class="legend-swatch" style="background:#fdecea;"></span>熔断中</div>
  <div class="legend-item"><span class="legend-swatch" style="background:#fff3e0;"></span>bf最高(选中)</div>
  <div class="legend-item"><span class="pos pos-国债">国债</span>避险资产</div>
  <div class="legend-item"><span class="pos pos-创业板50">创业板50</span>股票持仓</div>
  <div class="legend-item"><span class="sw-badge sw-建仓">建仓</span><span class="sw-badge sw-轮动">轮动</span><span class="sw-badge sw-触发">触发</span><span class="sw-badge sw-解除">解除</span></div>
</div>

<div class="controls">
  <input type="text" id="search" placeholder="搜索日期/持仓/原因...">
  <label>持仓: <select id="f-pos"><option value="">全部</option><option>上证50</option><option>创业板50</option><option>纳斯达克100</option><option>沪深300</option><option>中证500</option><option>中证1000</option><option>标普500</option><option>科创50</option><option>国债</option><option>空仓</option></select></label>
  <label>状态: <select id="f-cb"><option value="">全部</option><option>NORMAL</option><option>TRIGGERED</option><option>IN_CB</option><option>RELEASED</option></select></label>
  <label><input type="checkbox" id="f-sw"> 仅看切换日</label>
  <button class="btn" onclick="resetFilters()">重置</button>
  <span style="margin-left:auto;font-size:12px;color:#888;" id="count-info"></span>
</div>

<div class="table-wrap" style="max-height: 75vh; overflow: auto;">
<table id="tbl">
<thead>
<tr>
  <th data-sort="date">日期 <span class="sort-ind"></span></th>
  <th data-sort="idx">序号 <span class="sort-ind"></span></th>
  <th data-sort="position">当日持仓 <span class="sort-ind"></span></th>
  <th data-sort="signal">V8信号 <span class="sort-ind"></span></th>
  <th data-sort="ret">当日收益 <span class="sort-ind"></span></th>
  <th data-sort="nav">策略净值 <span class="sort-ind"></span></th>
  <th data-sort="raw_nav">V8净值 <span class="sort-ind"></span></th>
  <th data-sort="raw_dd">V8回撤 <span class="sort-ind"></span></th>
  <th data-sort="cb_status">熔断状态 <span class="sort-ind"></span></th>
  <th>切换事件</th>
  <th>原因</th>
  <th>手续费‱</th>
  <th class="bf-group" colspan="8">决策依据bf（前日收盘 close/MA20-1）</th>
</tr>
<tr>
  <th colspan="12"></th>
  <th>上证50</th><th>创业板50</th><th>纳斯达克100</th><th>沪深300</th>
  <th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th>
</tr>
</thead>
<tbody id="tbody"></tbody>
</table>
</div>

<div class="note">
  ℹ️ <b>字段说明</b><br>
  ① <b>当日持仓</b>：T日实际持有的资产（由T-1日收盘信号决定，T日开盘执行）。<br>
  ② <b>当日收益</b>：open(T+1)/open(T)-1 扣手续费，即T日开盘买入到T+1开盘卖出的收益。<br>
  ③ <b>策略净值</b>：从起始日1.0起累乘当日收益。<br>
  ④ <b>V8净值/回撤</b>：无熔断的V8基线策略净值，及距历史高点的回撤（熔断判断依据）。<br>
  ⑤ <b>熔断状态</b>：NORMAL=正常 / TRIGGERED=当日触发熔断 / IN_CB=熔断中持国债 / RELEASED=当日解除熔断。<br>
  ⑥ <b>决策依据bf</b>：前一交易日收盘后计算的 close/MA20-1，橙色高亮=当日最高（即被选中的标的）。<br>
  ⑦ <b>切换事件</b>：建仓/轮动/触发/解除/空仓，仅切换日有值。<br>
  ⑧ 黄色行=切换日，红色行=熔断中。可点表头排序，可用搜索框/下拉框筛选。
</div>

<script>
const DATA = __ROWS__;
const STOCKS = ['上证50','创业板50','纳斯达克100','沪深300','中证500','中证1000','标普500','科创50'];
let sortKey = 'date';
let sortAsc = true;
let filters = { search: '', pos: '', cb: '', swOnly: false };

function fmt(v, d) { if (v === null || v === undefined || v === '') return ''; return Number(v).toFixed(d); }
function fmtPct(v, d) { if (v === null || v === undefined || v === '') return ''; return (v >= 0 ? '+' : '') + Number(v*100).toFixed(d) + '%'; }
function posClass(p) { return 'pos pos-' + (p || '空仓'); }
function retClass(v) { if (v > 0.0001) return 'ret-pos'; if (v < -0.0001) return 'ret-neg'; return 'ret-zero'; }
function bfClass(v, isTop) { if (isTop) return 'bf-cell bf-top'; if (v < 0) return 'bf-cell bf-neg'; return 'bf-cell bf-pos'; }
function swBadge(t) { if (!t) return ''; const m = {'建仓':'sw-建仓','轮动':'sw-轮动','触发':'sw-触发','解除':'sw-解除','空仓':'sw-空仓'}; return '<span class="sw-badge ' + (m[t]||'') + '">' + t + '</span>'; }

function getFiltered() {
  return DATA.filter(r => {
    if (filters.search) {
      const s = filters.search.toLowerCase();
      const hay = (r.date + r.position + r.signal + (r.sw_reason||'') + r.sw_type + r.cb_status + r.sw_from + r.sw_to).toLowerCase();
      if (!hay.includes(s)) return false;
    }
    if (filters.pos && r.position !== filters.pos) return false;
    if (filters.cb && r.cb_status !== filters.cb) return false;
    if (filters.swOnly && !r.is_switch) return false;
    return true;
  });
}

function render() {
  const rows = getFiltered();
  const tb = document.getElementById('tbody');
  if (rows.length === 0) { tb.innerHTML = '<tr><td colspan="20" class="empty">无匹配记录</td></tr>'; document.getElementById('count-info').textContent = '0 / ' + DATA.length; return; }
  
  // 找每日最高bf
  let html = '';
  for (const r of rows) {
    let maxBf = -999, topName = '';
    for (const s of STOCKS) { const v = r.bf_vals[s]; if (v > maxBf) { maxBf = v; topName = s; } }
    
    const isSw = r.is_switch;
    const isCb = r.cb_status === 'TRIGGERED' || r.cb_status === 'IN_CB';
    let rowCls = '';
    if (isSw) rowCls = 'switch-row';
    else if (isCb) rowCls = 'cb-row';
    
    let swText = '';
    if (isSw) {
      swText = swBadge(r.sw_type);
      if (r.sw_from && r.sw_to) swText += '<br><span style="font-size:10px;color:#666;">' + r.sw_from + '→' + r.sw_to + '</span>';
    }
    
    let bfCells = '';
    for (const s of STOCKS) {
      const v = r.bf_vals[s];
      const isTop = (s === topName);
      bfCells += '<td class="' + bfClass(v, isTop) + '">' + fmtPct(v, 2) + '</td>';
    }
    
    const nav = r.nav;
    const rawNav = r.raw_nav;
    const rawDd = r.raw_dd;
    
    html += '<tr class="' + rowCls + '">'
      + '<td>' + r.date + '</td>'
      + '<td style="color:#999;">' + (r.idx + 1) + '</td>'
      + '<td><span class="' + posClass(r.position) + '">' + r.position + '</span></td>'
      + '<td style="color:#666;">' + r.signal + '</td>'
      + '<td class="' + retClass(r.ret) + '">' + fmtPct(r.ret, 2) + '</td>'
      + '<td style="font-weight:600;color:#1565c0;">' + fmt(nav, 4) + '</td>'
      + '<td style="color:#888;">' + fmt(rawNav, 4) + '</td>'
      + '<td class="' + (rawDd < -0.05 ? 'ret-neg' : (rawDd < -0.04 ? '' : 'ret-zero')) + '" style="font-weight:' + (rawDd < -0.05 ? 700 : 400) + ';">' + fmtPct(rawDd, 2) + '</td>'
      + '<td class="cb-' + r.cb_status + '">' + r.cb_status + '</td>'
      + '<td>' + swText + '</td>'
      + '<td style="font-size:11px;color:#666;text-align:left;max-width:220px;white-space:normal;">' + (r.sw_reason || '') + '</td>'
      + '<td>' + (r.cost > 0 ? (r.cost * 10000).toFixed(1) : '') + '</td>'
      + bfCells
      + '</tr>';
  }
  tb.innerHTML = html;
  document.getElementById('count-info').textContent = rows.length + ' / ' + DATA.length + ' 行';
}

function sortBy(key) {
  if (sortKey === key) sortAsc = !sortAsc;
  else { sortKey = key; sortAsc = (key === 'date' || key === 'idx'); }
  DATA.sort((a, b) => {
    let va = a[key], vb = b[key];
    if (key === 'idx') { va = a.idx; vb = b.idx; }
    if (typeof va === 'number' && typeof vb === 'number') return sortAsc ? va - vb : vb - va;
    va = String(va || ''); vb = String(vb || '');
    return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
  });
  // 更新排序指示器
  document.querySelectorAll('thead th .sort-ind').forEach(e => e.textContent = '');
  const th = document.querySelector('thead th[data-sort="' + key + '"]');
  if (th) th.querySelector('.sort-ind').textContent = sortAsc ? '▲' : '▼';
  render();
}

document.getElementById('search').addEventListener('input', e => { filters.search = e.target.value; render(); });
document.getElementById('f-pos').addEventListener('change', e => { filters.pos = e.target.value; render(); });
document.getElementById('f-cb').addEventListener('change', e => { filters.cb = e.target.value; render(); });
document.getElementById('f-sw').addEventListener('change', e => { filters.swOnly = e.target.checked; render(); });

function resetFilters() {
  filters = { search: '', pos: '', cb: '', swOnly: false };
  document.getElementById('search').value = '';
  document.getElementById('f-pos').value = '';
  document.getElementById('f-cb').value = '';
  document.getElementById('f-sw').checked = false;
  sortBy('date');
}

document.querySelectorAll('thead th[data-sort]').forEach(th => {
  th.addEventListener('click', () => sortBy(th.dataset.sort));
});

// 初始按日期升序
sortBy('date');
</script>
</body>
</html>'''

# 替换占位符
html = html.replace('__START__', d['start_date']).replace('__END__', d['end_date'])
html = html.replace('__NDAYS__', str(n_days))
html = html.replace('__NSW__', str(n_switch)).replace('__NSW2__', str(n_switch))
html = html.replace('__NCB__', str(n_cb_days))
html = html.replace('__CBPCT__', f"{d['cb_pct']*100:.1f}").replace('__CBPCT2__', f"{d['cb_pct']*100:.1f}")
html = html.replace('__TOT__', f"{d['strat_total']*100:.2f}%")
html = html.replace('__ANN__', f"{d['strat_ann']*100:.2f}%")
html = html.replace('__MDD__', f"{d['strat_mdd']*100:.2f}%")
html = html.replace('__SH__', f"{d['strat_sharpe']:.2f}")
html = html.replace('__FEE__', f"{d['total_fee']*100:.2f}")
# V8基线收益 = raw_nav最后一天 - 1
v8_tot = daily[-1]['raw_nav'] - 1
html = html.replace('__V8__', f"{v8_tot*100:+.2f}%")
html = html.replace('__ROWS__', rows_json)

out = 'V14策略5_4近1年每日明细净值.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'已生成: {out}')
print(f'记录数: {n_days} 天')
print(f'切换: {n_switch} 次, 熔断天数: {n_cb_days} ({d["cb_pct"]}%)')
print(f'策略总收益: {d["strat_total"]*100:.2f}%, V8基线: {v8_tot*100:+.2f}%')
