# -*- coding: utf-8 -*-
"""生成V4 HTML回测报告 - 国债替代中证红利"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v4_data.json', 'r', encoding='utf-8') as f:
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
        'bh3_total': fmt_pct(r['bh3_total']),
        'strat_ann': fmt_pct(r['strat_ann']),
        'bh1_ann': fmt_pct(r['bh1_ann']),
        'bh2_ann': fmt_pct(r['bh2_ann']),
        'bh3_ann': fmt_pct(r['bh3_ann']),
        'strat_mdd': fmt_pct(r['strat_mdd']),
        'bh1_mdd': fmt_pct(r['bh1_mdd']),
        'bh2_mdd': fmt_pct(r['bh2_mdd']),
        'bh3_mdd': fmt_pct(r['bh3_mdd']),
        'strat_sharpe': f"{r['strat_sharpe']:.2f}",
        'bh1_sharpe': f"{r['bh1_sharpe']:.2f}",
        'bh2_sharpe': f"{r['bh2_sharpe']:.2f}",
        'bh3_sharpe': f"{r['bh3_sharpe']:.2f}",
        'switches': r['switches'],
        'total_fee': fmt_pct(r['total_fee']),
        'hold1_pct': fmt_pct(r['hold1_pct']),
        'hold2_pct': fmt_pct(r['hold2_pct']),
        'hold3_pct': fmt_pct(r['hold3_pct']),
        'cash_pct': fmt_pct(r['cash_pct']),
        '_strat_total': r['strat_total'],
        '_bh1_total': r['bh1_total'],
        '_bh2_total': r['bh2_total'],
        '_bh3_total': r['bh3_total'],
        '_strat_ann': r['strat_ann'],
        '_bh1_ann': r['bh1_ann'],
        '_bh2_ann': r['bh2_ann'],
        '_bh3_ann': r['bh3_ann'],
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
    'bh3': full['bh3'][::step],
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
        'bh3': pn['bh3'][::sp],
    }

all_data = {
    'table_rows': table_rows,
    'chart_full': chart_full,
    'chart_periods': chart_periods,
}

data_json = json.dumps(all_data, ensure_ascii=False)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MA20轮动策略V4回测报告 - 国债避险</title>
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
  .info {{
    background: #e8f5e9; border: 1px solid #66bb6a; border-radius: 8px;
    padding: 12px 16px; margin-top: 12px; font-size: 13px; color: #2e7d32;
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{ background: #f0f2f5; padding: 8px 6px; text-align: center;
    font-weight: 600; color: #555; white-space: nowrap; }}
  th.group {{ background: #e8eaf6; color: #333; }}
  td {{ padding: 8px 6px; text-align: center; border-bottom: 1px solid #eee;
    white-space: nowrap; }}
  td.period {{ font-weight: 700; color: #333; font-size: 13px; }}
  td.date-range {{ font-size: 10px; color: #999; }}
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
  .legend {{ display: flex; gap: 16px; margin-top: 12px; font-size: 13px; flex-wrap: wrap; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  .legend-dot {{ width: 12px; height: 12px; border-radius: 3px; }}
  .highlight {{
    font-size: 13px; color: #555; margin-top: 12px;
    background: #f9f9f9; padding: 12px; border-radius: 8px; border-left: 3px solid #8e24aa;
  }}
  .compare-table td {{ font-size: 13px; padding: 10px 8px; }}
</style>
</head>
<body>

<h1>MA20轮动策略V4回测报告</h1>
<p class="subtitle">上证50 / 创业板50 / 国债指数 三资产轮动 &nbsp;|&nbsp; 国债全程覆盖(2003年起) &nbsp;|&nbsp; 手续费万分之二/单边 &nbsp;|&nbsp; 2026-07-20</p>

<div class="strategy-box">
  <h2>策略说明（V4 — 国债避险版）</h2>
  <p><span class="formula">买入因子 = 当日收盘价 / 当日MA20 - 1</span></p>
  <p>1. 每日收盘后计算上证50和创业板50的买入因子</p>
  <p>2. 哪个买入因子更高 → 次日开盘价买入该指数</p>
  <p>3. 两个买入因子<strong>均小于0</strong>（均跌破MA20）→ 次日开盘价买入<strong>国债指数</strong></p>
  <p>4. 每次买入或卖出收取<strong>万分之二</strong>(0.02%)手续费，切换持仓总成本万分之四(0.04%)</p>
  <div class="info">
    ℹ️ <b>数据说明</b>：国债指数数据从2003年起全程覆盖（5654天），无数据缺口。
    国债作为避险资产，在股市下跌时通常保值甚至上涨，最大回撤仅-1.02%（近10年），
    是真正的"防守资产"，理论上比股票类红利指数更适合作为空仓替代。
  </div>
</div>

<div class="card">
  <h2>各时段核心指标（四路对比）</h2>
  <table id="mainTable">
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th rowspan="2">日期范围</th>
        <th rowspan="2">交易日</th>
        <th colspan="4" class="group">总收益率</th>
        <th colspan="4" class="group">年化收益率</th>
        <th colspan="4" class="group">最大回撤</th>
        <th colspan="4" class="group">夏普比率</th>
      </tr>
      <tr>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>国债</th>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>国债</th>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>国债</th>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>国债</th>
      </tr>
    </thead>
    <tbody id="tableBody"></tbody>
  </table>
</div>

<div class="card">
  <h2>全周期净值曲线（2014年至今）</h2>
  <p style="font-size:13px;color:#666;">含手续费 | 四条净值线对比</p>
  <div class="chart-container"><canvas id="chartFull"></canvas></div>
  <div class="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#e53935"></div>轮动策略V4</div>
    <div class="legend-item"><div class="legend-dot" style="background:#1e88e5"></div>上证50 买入持有</div>
    <div class="legend-item"><div class="legend-dot" style="background:#43a047"></div>创业板50 买入持有</div>
    <div class="legend-item"><div class="legend-dot" style="background:#8e24aa"></div>国债 买入持有</div>
  </div>
</div>

<div class="grid-2">
  <div class="card">
    <h2>近3年净值曲线</h2>
    <div class="chart-container-small"><canvas id="chart3y"></canvas></div>
  </div>
  <div class="card">
    <h2>近1年净值曲线</h2>
    <div class="chart-container-small"><canvas id="chart1y"></canvas></div>
  </div>
</div>

<div class="card">
  <h2>持仓分布与交易成本</h2>
  <table>
    <thead>
      <tr>
        <th>时段</th>
        <th>切换次数</th>
        <th>累计手续费</th>
        <th>上证50</th>
        <th>创业板50</th>
        <th>国债</th>
        <th>持仓分布</th>
      </tr>
    </thead>
    <tbody id="posBody"></tbody>
  </table>
</div>

<div class="card">
  <h2>四版策略对比（V1空仓 / V3红利 / V4国债）</h2>
  <table class="compare-table">
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th colspan="2">V1（空仓·无费率）</th>
        <th colspan="2">V3（价格红利·费率·全程）</th>
        <th colspan="2">V4（国债·费率·全程）</th>
      </tr>
      <tr>
        <th>总收益</th><th>最大回撤</th>
        <th>总收益</th><th>最大回撤</th>
        <th>总收益</th><th>最大回撤</th>
      </tr>
    </thead>
    <tbody>
      <tr><td class="period">近10年</td><td class="pos">183.16%</td><td class="neg">-33.64%</td><td class="pos">174.25%</td><td class="neg">-44.42%</td><td class="pos">181.66%</td><td class="neg">-32.70%</td></tr>
      <tr><td class="period">近5年</td><td class="pos">21.19%</td><td class="neg">-33.64%</td><td class="pos">5.83%</td><td class="neg">-44.42%</td><td class="pos">21.29%</td><td class="neg">-32.70%</td></tr>
      <tr><td class="period">近3年</td><td class="pos">42.74%</td><td class="neg">-21.79%</td><td class="pos">35.65%</td><td class="neg">-28.43%</td><td class="pos">42.32%</td><td class="neg">-21.44%</td></tr>
      <tr><td class="period">近1年</td><td class="pos">23.36%</td><td class="neg">-19.81%</td><td class="pos">20.90%</td><td class="neg">-23.67%</td><td class="pos">21.04%</td><td class="neg">-21.05%</td></tr>
    </tbody>
  </table>
  <div class="highlight">
    <b>关键发现：</b><br>
    • <b>V4 vs V1（空仓）</b>：近10年收益几乎持平（181.66% vs 183.16%），但V4有手续费（累计16.72%）。说明国债在防守期不仅保值，还贡献了正收益，正好对冲了手续费成本。近5年V4(21.29%)甚至反超V1(21.19%)<br>
    • <b>V4 vs V3（红利）</b>：V4全面优于V3。近10年收益+7.41%，最大回撤从-44.42%改善到-32.70%。国债作为避险资产远优于红利（红利本质是股票指数，暴跌时跟跌）<br>
    • <b>最大回撤改善显著</b>：V4近10年最大回撤-32.70%，是四版策略中最低的，且低于上证50(-46.51%)和创业板50(-60.15%)单独持有<br>
    • <b>国债的避险价值</b>：国债本身夏普比率极高（近10年5.48，近5年5.39），在组合中起到了"稳定器"作用，是理想的空仓替代品<br>
    • <b>结论</b>：用国债替代空仓是本轮迭代的最优解——在不损失收益的前提下控制了回撤，策略鲁棒性更强
  </div>
</div>

<script>
const DATA = {data_json};

function colorClass(v) {{ return v >= 0 ? 'pos' : 'neg'; }}
function bestClass(val, arr) {{ return val === Math.max(...arr) ? 'best' : ''; }}

const tbody = document.getElementById('tableBody');
DATA.table_rows.forEach(row => {{
  const tots = [row._strat_total, row._bh1_total, row._bh2_total, row._bh3_total];
  const anns = [row._strat_ann, row._bh1_ann, row._bh2_ann, row._bh3_ann];
  tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="period">${{row.period}}</td>
    <td class="date-range">${{row.date_range}}</td>
    <td>${{row.n_days}}</td>
    <td class="${{colorClass(row._strat_total)}} ${{bestClass(row._strat_total, tots)}}">${{row.strat_total}}</td>
    <td class="${{colorClass(row._bh1_total)}} ${{bestClass(row._bh1_total, tots)}}">${{row.bh1_total}}</td>
    <td class="${{colorClass(row._bh2_total)}} ${{bestClass(row._bh2_total, tots)}}">${{row.bh2_total}}</td>
    <td class="${{colorClass(row._bh3_total)}} ${{bestClass(row._bh3_total, tots)}}">${{row.bh3_total}}</td>
    <td class="${{colorClass(row._strat_ann)}} ${{bestClass(row._strat_ann, anns)}}">${{row.strat_ann}}</td>
    <td class="${{colorClass(row._bh1_ann)}} ${{bestClass(row._bh1_ann, anns)}}">${{row.bh1_ann}}</td>
    <td class="${{colorClass(row._bh2_ann)}} ${{bestClass(row._bh2_ann, anns)}}">${{row.bh2_ann}}</td>
    <td class="${{colorClass(row._bh3_ann)}} ${{bestClass(row._bh3_ann, anns)}}">${{row.bh3_ann}}</td>
    <td class="neg">${{row.strat_mdd}}</td>
    <td class="neg">${{row.bh1_mdd}}</td>
    <td class="neg">${{row.bh2_mdd}}</td>
    <td class="neg">${{row.bh3_mdd}}</td>
    <td>${{row.strat_sharpe}}</td>
    <td>${{row.bh1_sharpe}}</td>
    <td>${{row.bh2_sharpe}}</td>
    <td>${{row.bh3_sharpe}}</td>
  `;
  tbody.appendChild(tr);
}});

const posBody = document.getElementById('posBody');
DATA.table_rows.forEach(row => {{
  const h1 = parseFloat(row.hold1_pct);
  const h2 = parseFloat(row.hold2_pct);
  const h3 = parseFloat(row.hold3_pct);
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="period">${{row.period}}</td>
    <td>${{row.switches}}</td>
    <td class="neg">${{row.total_fee}}</td>
    <td>${{row.hold1_pct}}</td>
    <td>${{row.hold2_pct}}</td>
    <td>${{row.hold3_pct}}</td>
    <td style="min-width:220px;">
      <div class="pos-bar">
        <div style="width:${{h1}}%;background:#1e88e5">${{h1>12?row.hold1_pct:''}}</div>
        <div style="width:${{h2}}%;background:#43a047">${{h2>12?row.hold2_pct:''}}</div>
        <div style="width:${{h3}}%;background:#8e24aa">${{h3>12?row.hold3_pct:''}}</div>
      </div>
    </td>
  `;
  posBody.appendChild(tr);
}});

Chart.defaults.font.family = "'PingFang SC', 'Microsoft YaHei', sans-serif";
Chart.defaults.font.size = 12;

function makeChart(canvasId, chartData, showLegend, showBh3) {{
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const datasets = [
    {{ label: '轮动策略V4', data: chartData.strat,
      borderColor: '#e53935', backgroundColor: 'rgba(229,57,53,0.08)',
      borderWidth: 2, pointRadius: 0, fill: true, tension: 0.1 }},
    {{ label: '上证50', data: chartData.bh1,
      borderColor: '#1e88e5', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1 }},
    {{ label: '创业板50', data: chartData.bh2,
      borderColor: '#43a047', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1 }},
  ];
  if (showBh3 !== false) {{
    datasets.push({{ label: '国债', data: chartData.bh3,
      borderColor: '#8e24aa', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1 }});
  }}
  return new Chart(ctx, {{
    type: 'line',
    data: {{ labels: chartData.dates, datasets: datasets }},
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
makeChart('chart3y', DATA.chart_periods['近3年'], false);
makeChart('chart1y', DATA.chart_periods['近1年'], false);
</script>

</body>
</html>
'''

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/MA20轮动策略V4回测报告.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("HTML报告已生成: MA20轮动策略V4回测报告.html")
