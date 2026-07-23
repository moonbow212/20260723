# -*- coding: utf-8 -*-
"""生成V2 HTML回测报告"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v2_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

periods = ['近10年', '近5年', '近3年', '近1年']

def fmt_pct(v):
    return f"{v*100:.2f}%"

table_rows = []
for p in periods:
    r = data['results'][p]
    table_rows.append({
        'period': p,
        'date_range': f"{r['start_date']} ~ {r['end_date']}",
        'n_days': r['n_days'],
        'strat_total': fmt_pct(r['strat_total']),
        'bh1_total': fmt_pct(r['bh1_total']),
        'bh2_total': fmt_pct(r['bh2_total']),
        'strat_ann': fmt_pct(r['strat_ann']),
        'bh1_ann': fmt_pct(r['bh1_ann']),
        'bh2_ann': fmt_pct(r['bh2_ann']),
        'strat_mdd': fmt_pct(r['strat_mdd']),
        'bh1_mdd': fmt_pct(r['bh1_mdd']),
        'bh2_mdd': fmt_pct(r['bh2_mdd']),
        'strat_sharpe': f"{r['strat_sharpe']:.2f}",
        'bh1_sharpe': f"{r['bh1_sharpe']:.2f}",
        'bh2_sharpe': f"{r['bh2_sharpe']:.2f}",
        'switches': r['switches'],
        'total_fee': fmt_pct(r['total_fee']),
        'hold1_pct': fmt_pct(r['hold1_pct']),
        'hold2_pct': fmt_pct(r['hold2_pct']),
        'hold3_pct': fmt_pct(r['hold3_pct']),
        'cash_pct': fmt_pct(r['cash_pct']),
        '_strat_total': r['strat_total'],
        '_bh1_total': r['bh1_total'],
        '_bh2_total': r['bh2_total'],
        '_strat_ann': r['strat_ann'],
        '_bh1_ann': r['bh1_ann'],
        '_bh2_ann': r['bh2_ann'],
    })

# 降采样
full = data['full_nav']
n = len(full['dates'])
step = max(1, n // 800)
chart_full = {
    'dates': full['dates'][::step],
    'strat': full['strat'][::step],
    'bh1': full['bh1'][::step],
    'bh2': full['bh2'][::step],
}

chart_periods = {}
for p in periods:
    pn = data['period_navs'][p]
    np_ = len(pn['dates'])
    sp = max(1, np_ // 600)
    chart_periods[p] = {
        'dates': pn['dates'][::sp],
        'strat': pn['strat'][::sp],
        'bh1': pn['bh1'][::sp],
        'bh2': pn['bh2'][::sp],
    }

all_data = {
    'table_rows': table_rows,
    'chart_full': chart_full,
    'chart_periods': chart_periods,
    'div_start': data['div_start_date'],
}

data_json = json.dumps(all_data, ensure_ascii=False)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MA20轮动策略V2回测报告 - 叠加中证红利+手续费</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #f5f7fa; color: #1a1a2e; line-height: 1.6;
    padding: 20px; max-width: 1200px; margin: 0 auto;
  }}
  h1 {{ font-size: 26px; margin-bottom: 6px; color: #1a1a2e; }}
  .subtitle {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
  .card {{
    background: #fff; border-radius: 12px; padding: 24px;
    margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  .card h2 {{ font-size: 18px; margin-bottom: 16px; color: #1a1a2e;
    border-left: 4px solid #4f6df5; padding-left: 12px; }}
  .strategy-box {{
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #fff; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px;
  }}
  .strategy-box h2 {{ color: #fff; border-left-color: rgba(255,255,255,0.5); }}
  .strategy-box p {{ font-size: 14px; opacity: 0.95; margin-top: 8px; }}
  .strategy-box .formula {{
    display: inline-block; background: rgba(255,255,255,0.15);
    padding: 4px 12px; border-radius: 6px; font-family: monospace;
    font-size: 14px; margin: 4px 4px 4px 0;
  }}
  .warning {{
    background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px;
    padding: 12px 16px; margin-top: 12px; font-size: 13px; color: #856404;
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #f0f2f5; padding: 10px 8px; text-align: center;
    font-weight: 600; color: #555; white-space: nowrap; }}
  th.group {{ background: #e8eaf6; color: #333; }}
  td {{ padding: 10px 8px; text-align: center; border-bottom: 1px solid #eee;
    white-space: nowrap; }}
  td.period {{ font-weight: 700; color: #333; font-size: 14px; }}
  td.date-range {{ font-size: 11px; color: #999; }}
  .pos {{ color: #d32f2f; font-weight: 600; }}
  .neg {{ color: #2e7d32; font-weight: 600; }}
  .best {{ background: #fff3e0; border-radius: 4px; }}
  .chart-container {{ position: relative; height: 400px; margin-top: 12px; }}
  .chart-container-small {{ position: relative; height: 320px; margin-top: 12px; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .pos-bar {{
    display: flex; height: 24px; border-radius: 6px; overflow: hidden;
    margin-top: 8px; font-size: 11px;
  }}
  .pos-bar div {{ display: flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 600; }}
  .legend {{ display: flex; gap: 20px; margin-top: 12px; font-size: 13px; flex-wrap: wrap; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  .legend-dot {{ width: 12px; height: 12px; border-radius: 3px; }}
  .highlight {{
    font-size: 13px; color: #555; margin-top: 12px;
    background: #f9f9f9; padding: 12px; border-radius: 8px; border-left: 3px solid #ffc107;
  }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px; }}
  .stat-box {{ background: #f8f9fa; border-radius: 8px; padding: 12px; text-align: center; }}
  .stat-box .label {{ font-size: 12px; color: #888; }}
  .stat-box .value {{ font-size: 20px; font-weight: 700; margin-top: 4px; }}
</style>
</head>
<body>

<h1>MA20轮动策略V2回测报告</h1>
<p class="subtitle">上证50 / 创业板50 / 中证红利全收益 三指数轮动 &nbsp;|&nbsp; 含手续费万分之二/单边 &nbsp;|&nbsp; 2026-07-20</p>

<div class="strategy-box">
  <h2>策略说明（V2升级版）</h2>
  <p><span class="formula">买入因子 = 当日收盘价 / 当日MA20 - 1</span></p>
  <p>1. 每日收盘后计算上证50和创业板50的买入因子</p>
  <p>2. 哪个买入因子更高 → 次日开盘价买入该指数</p>
  <p>3. 两个买入因子<strong>均小于0</strong>（均跌破MA20）→ 次日开盘价买入<strong>中证红利全收益指数</strong></p>
  <p>4. 每次买入或卖出收取<strong>万分之二</strong>(0.02%)手续费，切换持仓(卖A买B)总成本万分之四(0.04%)</p>
  <div class="warning">
    ⚠️ <b>数据限制</b>：中证红利全收益指数数据仅从 <b>{data['div_start_date']}</b> 起可用（348个交易日）。
    在此之前，当两个买入因子均小于0时，策略回退为空仓（与V1一致）。
    因此近10年/5年/3年的结果中，红利指数仅在最后约1.4年生效。
  </div>
</div>

<div class="card">
  <h2>各时段核心指标</h2>
  <table id="mainTable">
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th rowspan="2">日期范围</th>
        <th rowspan="2">交易日</th>
        <th colspan="3" class="group">总收益率</th>
        <th colspan="3" class="group">年化收益率</th>
        <th colspan="3" class="group">最大回撤</th>
        <th colspan="3" class="group">夏普比率</th>
      </tr>
      <tr>
        <th>轮动策略</th><th>上证50</th><th>创业板50</th>
        <th>轮动策略</th><th>上证50</th><th>创业板50</th>
        <th>轮动策略</th><th>上证50</th><th>创业板50</th>
        <th>轮动策略</th><th>上证50</th><th>创业板50</th>
      </tr>
    </thead>
    <tbody id="tableBody"></tbody>
  </table>
</div>

<div class="card">
  <h2>全周期净值曲线（2014年至今）</h2>
  <p style="font-size:13px;color:#666;">含手续费 | 灰色虚线标注中证红利数据起始点 {data['div_start_date']}</p>
  <div class="chart-container"><canvas id="chartFull"></canvas></div>
  <div class="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#e53935"></div>轮动策略V2</div>
    <div class="legend-item"><div class="legend-dot" style="background:#1e88e5"></div>上证50 买入持有</div>
    <div class="legend-item"><div class="legend-dot" style="background:#43a047"></div>创业板50 买入持有</div>
  </div>
</div>

<div class="grid-2">
  <div class="card">
    <h2>近5年净值曲线</h2>
    <div class="chart-container-small"><canvas id="chart5y"></canvas></div>
  </div>
  <div class="card">
    <h2>近3年净值曲线</h2>
    <div class="chart-container-small"><canvas id="chart3y"></canvas></div>
  </div>
</div>

<div class="card">
  <h2>近1年净值曲线（红利指数全覆盖）</h2>
  <p style="font-size:13px;color:#666;">近1年区间内中证红利全收益指数全程可用，空仓占比为0%</p>
  <div class="chart-container-small"><canvas id="chart1y"></canvas></div>
</div>

<div class="card">
  <h2>持仓分布与交易成本</h2>
  <table>
    <thead>
      <tr>
        <th>时段</th>
        <th>切换次数</th>
        <th>总手续费</th>
        <th>上证50</th>
        <th>创业板50</th>
        <th>中证红利</th>
        <th>空仓</th>
        <th>持仓分布</th>
      </tr>
    </thead>
    <tbody id="posBody"></tbody>
  </table>
  <div class="highlight">
    <b>关键发现：</b><br>
    • <b>手续费侵蚀明显</b>：10年累计手续费成本达11.56%，年均约1.1%，频繁轮动(年均42次切换)是主因<br>
    • <b>红利指数替代空仓</b>：近1年红利持仓占比20.2%，空仓降为0%，但红利指数在防守时段也有波动，并未显著增厚收益<br>
    • <b>策略仍跑赢单指数</b>：近10年年化9.92%远超上证50(3.09%)和创业板50(5.73%)，最大回撤-35.56%优于两指数的-46.51%/-60.15%<br>
    • <b>近1年创业板强势</b>：创业板50单边大涨59.61%，策略因择时和费率跑输(21.27%)，但回撤-23.76%可控<br>
    • <b>夏普比率</b>：近1年0.81、近10年0.51，均高于上证50持有，低于创业板50持有(近1年1.54)
  </div>
</div>

<div class="card">
  <h2>V1 vs V2 对比（费率+红利影响）</h2>
  <table>
    <thead>
      <tr>
        <th>时段</th>
        <th colspan="2">V1（空仓·无费率）</th>
        <th colspan="2">V2（红利+费率）</th>
        <th>差异</th>
        <th>累计手续费</th>
      </tr>
      <tr>
        <th></th><th>总收益</th><th>夏普</th><th>总收益</th><th>夏普</th><th>收益差</th><th></th>
      </tr>
    </thead>
    <tbody>
      <tr><td class="period">近10年</td><td class="pos">183.16%</td><td>0.57</td><td class="pos">148.63%</td><td>0.51</td><td class="neg">-34.53%</td><td class="neg">-11.56%</td></tr>
      <tr><td class="period">近5年</td><td class="pos">21.19%</td><td>0.28</td><td class="pos">11.55%</td><td>0.21</td><td class="neg">-9.64%</td><td class="neg">-6.84%</td></tr>
      <tr><td class="period">近3年</td><td class="pos">42.74%</td><td>0.54</td><td class="pos">34.29%</td><td>0.47</td><td class="neg">-8.45%</td><td class="neg">-4.66%</td></tr>
      <tr><td class="period">近1年</td><td class="pos">23.36%</td><td>0.88</td><td class="pos">21.27%</td><td>0.81</td><td class="neg">-2.09%</td><td class="neg">-2.08%</td></tr>
    </tbody>
  </table>
  <div class="highlight" style="border-left-color:#2196f3;">
    <b>V1→V2 收益下降主因是手续费</b>：近1年收益差(-2.09%)几乎完全等于手续费(-2.08%)，说明红利替代空仓基本持平。
    长周期差异更大是因为费率复利累积。若需降低费率影响，可考虑降低切换频率（如加入持仓最短持有期约束）。
  </div>
</div>

<script>
const DATA = {data_json};

function colorClass(v) {{ return v >= 0 ? 'pos' : 'neg'; }}
function bestClass(val, arr) {{ return val === Math.max(...arr) ? 'best' : ''; }}

const tbody = document.getElementById('tableBody');
DATA.table_rows.forEach(row => {{
  const tots = [row._strat_total, row._bh1_total, row._bh2_total];
  const anns = [row._strat_ann, row._bh1_ann, row._bh2_ann];
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="period">${{row.period}}</td>
    <td class="date-range">${{row.date_range}}</td>
    <td>${{row.n_days}}</td>
    <td class="${{colorClass(row._strat_total)}} ${{bestClass(row._strat_total, tots)}}">${{row.strat_total}}</td>
    <td class="${{colorClass(row._bh1_total)}} ${{bestClass(row._bh1_total, tots)}}">${{row.bh1_total}}</td>
    <td class="${{colorClass(row._bh2_total)}} ${{bestClass(row._bh2_total, tots)}}">${{row.bh2_total}}</td>
    <td class="${{colorClass(row._strat_ann)}} ${{bestClass(row._strat_ann, anns)}}">${{row.strat_ann}}</td>
    <td class="${{colorClass(row._bh1_ann)}} ${{bestClass(row._bh1_ann, anns)}}">${{row.bh1_ann}}</td>
    <td class="${{colorClass(row._bh2_ann)}} ${{bestClass(row._bh2_ann, anns)}}">${{row.bh2_ann}}</td>
    <td class="neg">${{row.strat_mdd}}</td>
    <td class="neg">${{row.bh1_mdd}}</td>
    <td class="neg">${{row.bh2_mdd}}</td>
    <td>${{row.strat_sharpe}}</td>
    <td>${{row.bh1_sharpe}}</td>
    <td>${{row.bh2_sharpe}}</td>
  `;
  tbody.appendChild(tr);
}});

const posBody = document.getElementById('posBody');
DATA.table_rows.forEach(row => {{
  const h1 = parseFloat(row.hold1_pct);
  const h2 = parseFloat(row.hold2_pct);
  const h3 = parseFloat(row.hold3_pct);
  const cash = parseFloat(row.cash_pct);
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="period">${{row.period}}</td>
    <td>${{row.switches}}</td>
    <td class="neg">${{row.total_fee}}</td>
    <td>${{row.hold1_pct}}</td>
    <td>${{row.hold2_pct}}</td>
    <td>${{row.hold3_pct}}</td>
    <td>${{row.cash_pct}}</td>
    <td style="min-width:220px;">
      <div class="pos-bar">
        <div style="width:${{h1}}%;background:#1e88e5">${{h1>12?row.hold1_pct:''}}</div>
        <div style="width:${{h2}}%;background:#43a047">${{h2>12?row.hold2_pct:''}}</div>
        <div style="width:${{h3}}%;background:#ff9800">${{h3>12?row.hold3_pct:''}}</div>
        <div style="width:${{cash}}%;background:#bbb">${{cash>12?row.cash_pct:''}}</div>
      </div>
    </td>
  `;
  posBody.appendChild(tr);
}});

Chart.defaults.font.family = "'PingFang SC', 'Microsoft YaHei', sans-serif";
Chart.defaults.font.size = 12;

function makeChart(canvasId, chartData, showLegend) {{
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  return new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: chartData.dates,
      datasets: [
        {{ label: '轮动策略V2', data: chartData.strat,
          borderColor: '#e53935', backgroundColor: 'rgba(229,57,53,0.08)',
          borderWidth: 2, pointRadius: 0, fill: true, tension: 0.1 }},
        {{ label: '上证50 买入持有', data: chartData.bh1,
          borderColor: '#1e88e5', backgroundColor: 'transparent',
          borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1 }},
        {{ label: '创业板50 买入持有', data: chartData.bh2,
          borderColor: '#43a047', backgroundColor: 'transparent',
          borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1 }}
      ]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: showLegend, position: 'top' }},
        tooltip: {{ callbacks: {{ label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(4) }} }}
      }},
      scales: {{
        x: {{ ticks: {{ maxTicksLimit: 8, maxRotation: 0 }}, grid: {{ display: false }} }},
        y: {{ ticks: {{ callback: v => v.toFixed(2) }}, grid: {{ color: '#f0f0f0' }} }}
      }}
    }}
  }});
}}

makeChart('chartFull', DATA.chart_full, true);
makeChart('chart5y', DATA.chart_periods['近5年'], false);
makeChart('chart3y', DATA.chart_periods['近3年'], false);
makeChart('chart1y', DATA.chart_periods['近1年'], false);
</script>

</body>
</html>
'''

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/MA20轮动策略V2回测报告.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("HTML报告已生成: MA20轮动策略V2回测报告.html")
