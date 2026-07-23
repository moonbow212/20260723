# -*- coding: utf-8 -*-
"""生成V14(5%/4%)各时段持仓占比HTML报告"""
import json

with open('v14_holding_pct.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

periods = ['近20年', '近10年', '近5年', '近3年', '近1年']

# 收集所有出现过的资产名
all_assets = []
seen = set()
for p in periods:
    for a in data[p]['v14_counts']:
        if a not in seen:
            all_assets.append(a)
            seen.add(a)
# 调整顺序：国债放最后，空仓不放
order = ['上证50','创业板50','沪深300','中证500','中证1000','科创50','纳斯达克100','标普500','国债','空仓']
all_assets = [a for a in order if a in seen]

# 颜色映射
colors = {
    '上证50': '#e53935', '创业板50': '#d81b60', '沪深300': '#8e24aa',
    '中证500': '#5e35b1', '中证1000': '#3949ab', '科创50': '#1e88e5',
    '纳斯达克100': '#00acc1', '标普500': '#00897b', '国债': '#7cb342', '空仓': '#bdbdbd',
}

# 构建各时段V14占比数据
v14_chart_data = {}
v8_chart_data = {}
for p in periods:
    n = data[p]['n_days']
    v14_chart_data[p] = {a: data[p]['v14_counts'].get(a, 0) / n * 100 for a in all_assets}
    v8_chart_data[p] = {a: data[p]['v8_counts'].get(a, 0) / n * 100 for a in all_assets}

# 构建表格行
table_rows_v14 = []
table_rows_v8 = []
for a in all_assets:
    row_v14 = {'asset': a}
    row_v8 = {'asset': a}
    for p in periods:
        row_v14[p] = v14_chart_data[p].get(a, 0)
        row_v8[p] = v8_chart_data[p].get(a, 0)
    table_rows_v14.append(row_v14)
    table_rows_v8.append(row_v8)

v14_chart_json = json.dumps({
    'labels': periods,
    'datasets': [{
        'label': a,
        'data': [v14_chart_data[p].get(a, 0) for p in periods],
        'backgroundColor': colors.get(a, '#999'),
    } for a in all_assets]
}, ensure_ascii=False)

v8_chart_json = json.dumps({
    'labels': periods,
    'datasets': [{
        'label': a,
        'data': [v8_chart_data[p].get(a, 0) for p in periods],
        'backgroundColor': colors.get(a, '#999'),
    } for a in all_assets]
}, ensure_ascii=False)

# 各时段饼图数据
pie_data = {}
for p in periods:
    labels = []
    values = []
    bg = []
    for a in all_assets:
        v = v14_chart_data[p].get(a, 0)
        if v > 0.01:
            labels.append(a)
            values.append(round(v, 2))
            bg.append(colors.get(a, '#999'))
    pie_data[p] = {'labels': labels, 'data': values, 'bg': bg}
pie_json = json.dumps(pie_data, ensure_ascii=False)

# 表格数据
tbl_v14_json = json.dumps(table_rows_v14, ensure_ascii=False)
tbl_v8_json = json.dumps(table_rows_v8, ensure_ascii=False)

# 汇总卡片数据
summary = []
for p in periods:
    d = data[p]
    summary.append({
        'period': p,
        'n_days': d['n_days'],
        'date_range': f"{d['start']}~{d['end']}",
        'pool': '+'.join(d['stock_names']) + '+国债',
        'v14_cb_pct': round(d['v14_cb_pct'] * 100, 1),
        'v8_cb_pct': round(d['v8_cb_pct'] * 100, 1),
        'v14_sw': d['v14_switches'],
        'v8_sw': d['v8_switches'],
    })
summary_json = json.dumps(summary, ensure_ascii=False)

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>V14(5%/4%)策略 各时段持仓占比分析</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; background: #f5f6f8; color: #222; padding: 20px; }
h1 { font-size: 20px; margin-bottom: 4px; color: #1a1a2e; }
.subtitle { font-size: 13px; color: #666; margin-bottom: 16px; }
section { background: #fff; border-radius: 10px; padding: 18px 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
h2 { font-size: 16px; margin-bottom: 12px; color: #1a1a2e; border-left: 4px solid #1565c0; padding-left: 10px; }
.summary-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 8px; }
@media(max-width:900px){ .summary-grid { grid-template-columns: repeat(2,1fr); } }
.sum-card { background: #f8f9fc; border-radius: 8px; padding: 10px 12px; border: 1px solid #eef0f4; }
.sum-card .p { font-size: 13px; font-weight: 600; color: #1a1a2e; margin-bottom: 4px; }
.sum-card .dr { font-size: 10px; color: #888; margin-bottom: 6px; }
.sum-card .pool { font-size: 10px; color: #666; margin-bottom: 6px; line-height: 1.4; }
.sum-card .stat { display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 2px; }
.sum-card .stat .lbl { color: #888; }
.sum-card .stat .v14 { color: #d32f2f; font-weight: 600; }
.sum-card .stat .v8 { color: #888; }
.chart-row { display: flex; gap: 16px; flex-wrap: wrap; }
.chart-box { flex: 1; min-width: 320px; }
.chart-box h3 { font-size: 13px; color: #555; margin-bottom: 8px; }
.canvas-wrap { position: relative; height: 360px; }
.pie-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
@media(max-width:1200px){ .pie-grid { grid-template-columns: repeat(2,1fr); } }
.pie-box { text-align: center; }
.pie-box h3 { font-size: 13px; color: #1a1a2e; margin-bottom: 6px; }
.pie-box .dr { font-size: 10px; color: #888; margin-bottom: 6px; }
.pie-canvas-wrap { position: relative; height: 220px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { padding: 8px 10px; text-align: center; border-bottom: 1px solid #eef0f4; }
th { background: #f0f2f8; color: #333; font-weight: 600; }
tbody tr:hover { background: #f8f9fc; }
.asset-cell { text-align: left; font-weight: 600; padding-left: 14px; position: relative; }
.asset-cell::before { content: ''; position: absolute; left: 0; top: 50%; transform: translateY(-50%); width: 10px; height: 10px; border-radius: 2px; background: var(--c, #999); }
.pct { font-family: Consolas, monospace; }
.pct-high { color: #d32f2f; font-weight: 700; }
.pct-mid { color: #e65100; }
.pct-zero { color: #ccc; }
.note { background: #fff; border-left: 4px solid #1565c0; border-radius: 4px; padding: 12px 16px; margin-top: 14px; font-size: 12px; color: #444; line-height: 1.7; }
.note b { color: #1565c0; }
.tabs { display: flex; gap: 6px; margin-bottom: 12px; }
.tab { padding: 6px 16px; border: 1px solid #ddd; border-radius: 6px; cursor: pointer; font-size: 13px; background: #fff; color: #555; }
.tab.active { background: #1565c0; color: #fff; border-color: #1565c0; }
</style>
</head>
<body>
<h1>V14 (5%/4%) 策略 — 各时段持仓占比分析</h1>
<div class="subtitle">对比 V14 熔断策略 vs V8 基线策略 在 近1/3/5/10/20年 各资产的持仓天数占比</div>

<section>
<h2>📊 时段概览</h2>
<div class="summary-grid" id="summary-grid"></div>
</section>

<section>
<h2>📈 V14 持仓占比堆叠柱状图 vs V8 基线</h2>
<div class="chart-row">
  <div class="chart-box"><h3>V14 (5%/4% 熔断策略)</h3><div class="canvas-wrap"><canvas id="chart-v14"></canvas></div></div>
  <div class="chart-box"><h3>V8 基线（无熔断）</h3><div class="canvas-wrap"><canvas id="chart-v8"></canvas></div></div>
</div>
</section>

<section>
<h2>🥧 V14 各时段持仓占比饼图</h2>
<div class="pie-grid" id="pie-grid"></div>
</section>

<section>
<h2>📋 持仓占比明细表</h2>
<div class="tabs">
  <div class="tab active" onclick="switchTab('v14')">V14 (5%/4%)</div>
  <div class="tab" onclick="switchTab('v8')">V8 基线</div>
</div>
<div id="tbl-v14"></div>
<div id="tbl-v8" style="display:none;"></div>
</section>

<div class="note">
  ℹ️ <b>说明</b><br>
  ① <b>持仓占比</b> = 该资产作为当日持仓的天数 / 总交易日数。每个交易日只持有1个资产。<br>
  ② <b>V14</b>：5%/4%回撤熔断策略。回撤>5%强制转国债，<4%解除。国债占比高=避险时间多。<br>
  ③ <b>V8</b>：无熔断基线。仅按MA20买入因子轮动，全部跌破MA20才买国债。<br>
  ④ <b>标的池差异</b>：近20年仅4股（上证50/纳指100/沪深300/中证1000），近10年7股（+创业板50/中证500/标普500），近5/3/1年8股（+科创50）。标的池越大，单一资产占比越分散。<br>
  ⑤ <b>关键观察</b>：V14的国债占比远高于V8（63-81% vs 10-16%），说明熔断机制让策略大部分时间在避险；股票持仓集中于少数强势指数（创业板50/纳指100/中证1000）。
</div>

<script>
const PERIODS = ['近20年','近10年','近5年','近3年','近1年'];
const ASSETS = __ASSETS__;
const COLORS = __COLORS__;
const V14_CHART = __V14_CHART__;
const V8_CHART = __V8_CHART__;
const PIE_DATA = __PIE__;
const SUMMARY = __SUMMARY__;
const TBL_V14 = __TBL_V14__;
const TBL_V8 = __TBL_V8__;

// 概览卡片
const sg = document.getElementById('summary-grid');
SUMMARY.forEach(s => {
  const el = document.createElement('div');
  el.className = 'sum-card';
  el.innerHTML = `
    <div class="p">${s.period}</div>
    <div class="dr">${s.date_range} (${s.n_days}天)</div>
    <div class="pool">${s.pool}</div>
    <div class="stat"><span class="lbl">国债占比 V14/V8</span><span><span class="v14">${s.v14_cb_pct}%</span> / <span class="v8">${s.v8_cb_pct}%</span></span></div>
    <div class="stat"><span class="lbl">切换次数 V14/V8</span><span><span class="v14">${s.v14_sw}</span> / <span class="v8">${s.v8_sw}</span></span></div>
  `;
  sg.appendChild(el);
});

// 堆叠柱状图配置
function makeStackedChart(ctx, chartData) {
  return new Chart(ctx, {
    type: 'bar',
    data: chartData,
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        title: { display: false },
        tooltip: { callbacks: { label: c => c.dataset.label + ': ' + c.parsed.y.toFixed(2) + '%' } },
        legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
      },
      scales: {
        x: { stacked: true, grid: { display: false } },
        y: { stacked: true, max: 100, ticks: { callback: v => v + '%' }, title: { display: true, text: '持仓占比 (%)' } }
      }
    }
  });
}
makeStackedChart(document.getElementById('chart-v14'), V14_CHART);
makeStackedChart(document.getElementById('chart-v8'), V8_CHART);

// 饼图
const pg = document.getElementById('pie-grid');
PIE_DATA && PERIODS.forEach((p, idx) => {
  const pd = PIE_DATA[p];
  const box = document.createElement('div');
  box.className = 'pie-box';
  box.innerHTML = `<h3>${p}</h3><div class="pie-canvas-wrap"><canvas id="pie-${idx}"></canvas></div>`;
  pg.appendChild(box);
  new Chart(box.querySelector('canvas'), {
    type: 'doughnut',
    data: { labels: pd.labels, datasets: [{ data: pd.data, backgroundColor: pd.bg, borderWidth: 1, borderColor: '#fff' }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { boxWidth: 10, font: { size: 10 }, padding: 6 } },
        tooltip: { callbacks: { label: c => c.label + ': ' + c.parsed.toFixed(2) + '%' } }
      }
    }
  });
});

// 表格渲染
function renderTable(rows, containerId) {
  const c = document.getElementById(containerId);
  let html = '<table><thead><tr><th style="text-align:left;padding-left:14px;">资产</th>';
  PERIODS.forEach(p => html += `<th>${p}<br><span style="font-size:10px;color:#999;font-weight:400;">(天/占比)</span></th>`);
  html += '</tr></thead><tbody>';
  rows.forEach(r => {
    const color = COLORS[r.asset] || '#999';
    html += `<tr><td class="asset-cell" style="--c:${color};">${r.asset}</td>`;
    PERIODS.forEach(p => {
      const v = r[p];
      let cls = 'pct-zero';
      if (v >= 10) cls = 'pct-high';
      else if (v >= 1) cls = 'pct-mid';
      const n = Math.round(v / 100 * SUMMARY.find(s=>s.period===p).n_days);
      html += `<td class="pct ${cls}">${v.toFixed(2)}%<br><span style="font-size:10px;color:#999;">${n}天</span></td>`;
    });
    html += '</tr>';
  });
  html += '</tbody></table>';
  c.innerHTML = html;
}
renderTable(TBL_V14, 'tbl-v14');
renderTable(TBL_V8, 'tbl-v8');

function switchTab(t) {
  document.querySelectorAll('.tab').forEach(e => e.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('tbl-v14').style.display = t==='v14'?'block':'none';
  document.getElementById('tbl-v8').style.display = t==='v8'?'block':'none';
}
</script>
</body>
</html>'''

html = html.replace('__ASSETS__', json.dumps(all_assets, ensure_ascii=False))
html = html.replace('__COLORS__', json.dumps(colors, ensure_ascii=False))
html = html.replace('__V14_CHART__', v14_chart_json)
html = html.replace('__V8_CHART__', v8_chart_json)
html = html.replace('__PIE__', pie_json)
html = html.replace('__SUMMARY__', summary_json)
html = html.replace('__TBL_V14__', tbl_v14_json)
html = html.replace('__TBL_V8__', tbl_v8_json)

out = 'V14策略5_4各时段持仓占比分析.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'已生成: {out}')
