# -*- coding: utf-8 -*-
"""生成V14(5%/4%)近20年逐年持仓占比及收益HTML报告"""
import json

with open('v14_yearly.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

yearly = data['yearly']
assets_order = ['上证50', '纳斯达克100', '沪深300', '中证1000', '国债']
colors = {
    '上证50': '#e53935', '纳斯达克100': '#00acc1', '沪深300': '#8e24aa',
    '中证1000': '#3949ab', '国债': '#7cb342',
}

years = [y['year'] for y in yearly]

# 年度收益柱状图数据
ret_chart = {
    'labels': years,
    'datasets': [
        {
            'label': 'V14 (5%/4%)',
            'data': [round(y['v14_ret']*100, 2) for y in yearly],
            'backgroundColor': '#d32f2f',
        },
        {
            'label': 'V8 基线',
            'data': [round(y['v8_ret']*100, 2) for y in yearly],
            'backgroundColor': '#bdbdbd',
        }
    ]
}

# 持仓占比堆叠柱状图
holding_chart = {
    'labels': years,
    'datasets': [{
        'label': a,
        'data': [y['holding'].get(a, {}).get('pct', 0) for y in yearly],
        'backgroundColor': colors[a],
    } for a in assets_order]
}

# 累计净值曲线
cum_nav = []
nav = 1.0
for y in yearly:
    nav *= (1 + y['v14_ret'])
    cum_nav.append(round(nav, 4))
cum_nav_v8 = []
nav8 = 1.0
for y in yearly:
    nav8 *= (1 + y['v8_ret'])
    cum_nav_v8.append(round(nav8, 4))

nav_chart = {
    'labels': years,
    'datasets': [
        {
            'label': 'V14 累计净值',
            'data': cum_nav,
            'borderColor': '#d32f2f',
            'backgroundColor': 'rgba(211,47,47,0.1)',
            'fill': True, 'tension': 0.1, 'pointRadius': 3,
        },
        {
            'label': 'V8 累计净值',
            'data': cum_nav_v8,
            'borderColor': '#888',
            'backgroundColor': 'rgba(136,136,136,0.05)',
            'fill': False, 'tension': 0.1, 'pointRadius': 3,
        }
    ]
}

yearly_json = json.dumps(yearly, ensure_ascii=False)
ret_chart_json = json.dumps(ret_chart, ensure_ascii=False)
holding_chart_json = json.dumps(holding_chart, ensure_ascii=False)
nav_chart_json = json.dumps(nav_chart, ensure_ascii=False)

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>V14(5%/4%)近20年逐年持仓占比及收益</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; background: #f5f6f8; color: #222; padding: 20px; }
h1 { font-size: 20px; margin-bottom: 4px; color: #1a1a2e; }
.subtitle { font-size: 13px; color: #666; margin-bottom: 16px; }
section { background: #fff; border-radius: 10px; padding: 18px 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
h2 { font-size: 16px; margin-bottom: 12px; color: #1a1a2e; border-left: 4px solid #1565c0; padding-left: 10px; }
.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 4px; }
@media(max-width:800px){ .summary-grid { grid-template-columns: repeat(2,1fr); } }
.sum-card { background: #f8f9fc; border-radius: 8px; padding: 14px 16px; border: 1px solid #eef0f4; }
.sum-card .lbl { font-size: 11px; color: #888; margin-bottom: 4px; }
.sum-card .val { font-size: 22px; font-weight: 700; }
.sum-card .val.red { color: #d32f2f; }
.sum-card .val.green { color: #2e7d32; }
.sum-card .val.blue { color: #1565c0; }
.sum-card .sub { font-size: 11px; color: #999; margin-top: 2px; }
.canvas-wrap { position: relative; height: 380px; }
.canvas-wrap-sm { position: relative; height: 300px; }
table { width: 100%; border-collapse: collapse; font-size: 11px; }
th, td { padding: 7px 6px; text-align: center; border-bottom: 1px solid #eef0f4; }
th { background: #f0f2f8; color: #333; font-weight: 600; position: sticky; top: 0; z-index: 5; }
tbody tr:hover { background: #f8f9fc; }
.tbl-wrap { max-height: 600px; overflow: auto; border-radius: 6px; }
.ret-pos { color: #d32f2f; font-weight: 700; }
.ret-neg { color: #2e7d32; font-weight: 700; }
.ret-zero { color: #888; }
.excess-pos { color: #d32f2f; font-weight: 600; }
.excess-neg { color: #1565c0; font-weight: 600; }
.pct-cell { font-family: Consolas, monospace; }
.pct-high { background: #fff3e0; font-weight: 700; color: #e65100; }
.pct-mid { color: #555; }
.pct-zero { color: #ddd; }
.year-cell { font-weight: 700; color: #1a1a2e; }
.bar-cell { position: relative; min-width: 50px; }
.bar-bg { position: absolute; left: 0; top: 0; height: 100%; border-radius: 3px; opacity: 0.25; }
.bar-val { position: relative; z-index: 1; }
.note { background: #fff; border-left: 4px solid #1565c0; border-radius: 4px; padding: 12px 16px; margin-top: 14px; font-size: 12px; color: #444; line-height: 1.7; }
.note b { color: #1565c0; }
.legend-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 10px; font-size: 12px; }
.legend-item { display: flex; align-items: center; gap: 5px; }
.legend-swatch { width: 14px; height: 14px; border-radius: 3px; }
</style>
</head>
<body>
<h1>V14 (5%/4%) 策略 — 近20年逐年持仓占比及收益</h1>
<div class="subtitle">标的池: 上证50 + 纳斯达克100 + 沪深300 + 中证1000 + 国债 | 期间: __START__ ~ __END__</div>

<section>
<h2>📊 近20年总览</h2>
<div class="summary-grid">
  <div class="sum-card"><div class="lbl">V14 总收益</div><div class="val red">__TOT_V14__</div><div class="sub">年化 __ANN_V14__</div></div>
  <div class="sum-card"><div class="lbl">V8 基线总收益</div><div class="val">__TOT_V8__</div><div class="sub">年化 __ANN_V8__</div></div>
  <div class="sum-card"><div class="lbl">超额收益</div><div class="val green">__EXCESS__</div><div class="sub">年化差 __ANN_DIFF__</div></div>
  <div class="sum-card"><div class="lbl">国债平均持仓占比</div><div class="val blue">__CB_AVG__</div><div class="sub">避险为主</div></div>
</div>
</section>

<section>
<h2>📈 累计净值曲线（按年复利）</h2>
<div class="canvas-wrap"><canvas id="chart-nav"></canvas></div>
</section>

<section>
<h2>📉 年度收益对比（V14 vs V8）</h2>
<div class="canvas-wrap"><canvas id="chart-ret"></canvas></div>
</section>

<section>
<h2>📊 每年持仓占比（堆叠柱状图）</h2>
<div class="legend-row" id="holding-legend"></div>
<div class="canvas-wrap"><canvas id="chart-holding"></canvas></div>
</section>

<section>
<h2>📋 逐年明细表</h2>
<div class="tbl-wrap">
<table>
<thead>
<tr>
  <th rowspan="2">年份</th>
  <th rowspan="2">交易日</th>
  <th colspan="3">年度收益</th>
  <th rowspan="2">V14回撤</th>
  <th rowspan="2">切换次</th>
  <th colspan="5">持仓占比（天数）</th>
</tr>
<tr>
  <th>V14</th><th>V8</th><th>超额</th>
  <th>上证50</th><th>纳指100</th><th>沪深300</th><th>中证1000</th><th>国债</th>
</tr>
</thead>
<tbody id="tbody"></tbody>
</table>
</div>
</section>

<div class="note">
  ℹ️ <b>说明</b><br>
  ① <b>标的池</b>：近20年仅使用全程可用的4个股票指数（上证50/纳指100/沪深300/中证1000）+国债，与近5/3/1年的8股池不同。<br>
  ② <b>年度收益</b> = 当年每日收益累乘 - 1，未做年化（完整年即年化，不完整年标注天数）。<br>
  ③ <b>V14回撤</b> = 当年策略净值距当年内高点的最大回撤（不跨年）。<br>
  ④ <b>持仓占比</b> = 该资产当年持仓天数 / 当年交易日数。国债占比高 = 当年熔断避险时间多。<br>
  ⑤ <b>关键规律</b>：熊市年份（2008/2011/2016/2018/2022）国债占比极高（90-100%），策略靠避险躲过大跌；牛市年份（2007/2014/2015/2024）股票占比提升，吃到主升浪。<br>
  ⑥ <b>注意</b>：2006年只有90天（8月起）、2026年只有125天（截至7月），非完整年。
</div>

<script>
const YEARLY = __YEARLY__;
const ASSETS = ['上证50','纳斯达克100','沪深300','中证1000','国债'];
const COLORS = {"上证50":"#e53935","纳斯达克100":"#00acc1","沪深300":"#8e24aa","中证1000":"#3949ab","国债":"#7cb342"};
const RET_CHART = __RET_CHART__;
const HOLDING_CHART = __HOLDING_CHART__;
const NAV_CHART = __NAV_CHART__;

// 持仓图例
const hl = document.getElementById('holding-legend');
ASSETS.forEach(a => {
  const el = document.createElement('div');
  el.className = 'legend-item';
  el.innerHTML = '<span class="legend-swatch" style="background:'+COLORS[a]+';"></span>'+a;
  hl.appendChild(el);
});

// 净值曲线
new Chart(document.getElementById('chart-nav'), {
  type: 'line',
  data: NAV_CHART,
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: c => c.dataset.label + ': ' + c.parsed.y.toFixed(2) } } },
    scales: {
      y: { type: 'logarithmic', title: { display: true, text: '累计净值（对数轴）' } },
      x: { title: { display: true, text: '年份' } }
    }
  }
});

// 年度收益柱状图
new Chart(document.getElementById('chart-ret'), {
  type: 'bar',
  data: RET_CHART,
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: c => c.dataset.label + ': ' + c.parsed.y.toFixed(2) + '%' } } },
    scales: {
      y: { title: { display: true, text: '年度收益 (%)' }, ticks: { callback: v => v + '%' } },
      x: { title: { display: true, text: '年份' } }
    }
  }
});

// 持仓占比堆叠柱状图
new Chart(document.getElementById('chart-holding'), {
  type: 'bar',
  data: HOLDING_CHART,
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom', labels: { boxWidth: 12 } }, tooltip: { callbacks: { label: c => c.dataset.label + ': ' + c.parsed.y.toFixed(1) + '%' } } },
    scales: {
      x: { stacked: true, title: { display: true, text: '年份' } },
      y: { stacked: true, max: 100, title: { display: true, text: '持仓占比 (%)' }, ticks: { callback: v => v + '%' } }
    }
  }
});

// 表格
const tb = document.getElementById('tbody');
let html = '';
YEARLY.forEach(y => {
  const vr = y.v14_ret * 100, v8r = y.v8_ret * 100, ex = y.excess * 100;
  const retCls = vr >= 0 ? 'ret-pos' : 'ret-neg';
  const exCls = ex >= 0 ? 'excess-pos' : 'excess-neg';
  let cells = '';
  ASSETS.forEach(a => {
    const h = y.holding[a];
    if (h && h.pct > 0) {
      let cls = 'pct-mid';
      if (h.pct >= 50) cls = 'pct-high';
      else if (h.pct < 1) cls = 'pct-zero';
      cells += '<td class="pct-cell ' + cls + '">' + h.pct.toFixed(1) + '%<br><span style="font-size:10px;color:#999;">' + h.days + '天</span></td>';
    } else {
      cells += '<td class="pct-zero">--</td>';
    }
  });
  html += '<tr>'
    + '<td class="year-cell">' + y.year + '</td>'
    + '<td>' + y.n_days + '</td>'
    + '<td class="' + retCls + '">' + (vr >= 0 ? '+' : '') + vr.toFixed(2) + '%</td>'
    + '<td style="color:#666;">' + (v8r >= 0 ? '+' : '') + v8r.toFixed(2) + '%</td>'
    + '<td class="' + exCls + '">' + (ex >= 0 ? '+' : '') + ex.toFixed(2) + '%</td>'
    + '<td style="color:#e65100;">' + (y.v14_mdd * 100).toFixed(2) + '%</td>'
    + '<td>' + y.v14_switches + '</td>'
    + cells
    + '</tr>';
});
tb.innerHTML = html;
</script>
</body>
</html>'''

# 汇总数据
tot_v14 = data['total_v14']
tot_v8 = data['total_v8']
ann_v14 = data['ann_v14']
ann_v8 = data['ann_v8']
cb_avg = sum(y['v14_cb_pct'] for y in yearly) / len(yearly) * 100

html = html.replace('__START__', data['start']).replace('__END__', data['end'])
html = html.replace('__TOT_V14__', f"{tot_v14*100:.0f}%")
html = html.replace('__TOT_V8__', f"{tot_v8*100:.0f}%")
html = html.replace('__ANN_V14__', f"{ann_v14*100:.2f}%")
html = html.replace('__ANN_V8__', f"{ann_v8*100:.2f}%")
html = html.replace('__EXCESS__', f"{(tot_v14-tot_v8)*100:+.0f}%")
html = html.replace('__ANN_DIFF__', f"{(ann_v14-ann_v8)*100:+.2f}%")
html = html.replace('__CB_AVG__', f"{cb_avg:.1f}%")
html = html.replace('__YEARLY__', yearly_json)
html = html.replace('__RET_CHART__', ret_chart_json)
html = html.replace('__HOLDING_CHART__', holding_chart_json)
html = html.replace('__NAV_CHART__', nav_chart_json)

out = 'V14策略5_4近20年逐年持仓占比及收益.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'已生成: {out}')
