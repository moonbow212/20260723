# -*- coding: utf-8 -*-
"""生成V5 HTML回测报告 - 三指数轮动(含纳斯达克)+国债避险"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v5_data.json', 'r', encoding='utf-8') as f:
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
        'bh4_total': fmt_pct(r['bh4_total']),
        'strat_ann': fmt_pct(r['strat_ann']),
        'bh1_ann': fmt_pct(r['bh1_ann']),
        'bh2_ann': fmt_pct(r['bh2_ann']),
        'bh3_ann': fmt_pct(r['bh3_ann']),
        'bh4_ann': fmt_pct(r['bh4_ann']),
        'strat_mdd': fmt_pct(r['strat_mdd']),
        'bh1_mdd': fmt_pct(r['bh1_mdd']),
        'bh2_mdd': fmt_pct(r['bh2_mdd']),
        'bh3_mdd': fmt_pct(r['bh3_mdd']),
        'bh4_mdd': fmt_pct(r['bh4_mdd']),
        'strat_sharpe': f"{r['strat_sharpe']:.2f}",
        'bh1_sharpe': f"{r['bh1_sharpe']:.2f}",
        'bh2_sharpe': f"{r['bh2_sharpe']:.2f}",
        'bh3_sharpe': f"{r['bh3_sharpe']:.2f}",
        'bh4_sharpe': f"{r['bh4_sharpe']:.2f}",
        'switches': r['switches'],
        'total_fee': fmt_pct(r['total_fee']),
        'hold1_pct': fmt_pct(r['hold1_pct']),
        'hold2_pct': fmt_pct(r['hold2_pct']),
        'hold3_pct': fmt_pct(r['hold3_pct']),
        'hold4_pct': fmt_pct(r['hold4_pct']),
        'cash_pct': fmt_pct(r['cash_pct']),
        '_strat_total': r['strat_total'],
        '_bh1_total': r['bh1_total'],
        '_bh2_total': r['bh2_total'],
        '_bh3_total': r['bh3_total'],
        '_bh4_total': r['bh4_total'],
        '_strat_ann': r['strat_ann'],
        '_bh1_ann': r['bh1_ann'],
        '_bh2_ann': r['bh2_ann'],
        '_bh3_ann': r['bh3_ann'],
        '_bh4_ann': r['bh4_ann'],
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
    'bh4': full['bh4'][::step],
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
        'bh4': pn['bh4'][::sp],
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
<title>MA20轮动策略V5回测报告 - 三指数轮动(含纳斯达克)</title>
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
  .warn {{
    background: #fff3e0; border: 1px solid #ff9800; border-radius: 8px;
    padding: 12px 16px; margin-top: 12px; font-size: 13px; color: #e65100;
  }}
  .info {{
    background: #e3f2fd; border: 1px solid #64b5f6; border-radius: 8px;
    padding: 12px 16px; margin-top: 12px; font-size: 13px; color: #1565c0;
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
  th {{ background: #f0f2f5; padding: 7px 5px; text-align: center;
    font-weight: 600; color: #555; white-space: nowrap; }}
  th.group {{ background: #e8eaf6; color: #333; }}
  td {{ padding: 7px 5px; text-align: center; border-bottom: 1px solid #eee;
    white-space: nowrap; }}
  td.period {{ font-weight: 700; color: #333; font-size: 12px; }}
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
    background: #fce4ec; padding: 12px; border-radius: 8px; border-left: 3px solid #e91e63;
  }}
  .compare-table td {{ font-size: 13px; padding: 10px 8px; }}
</style>
</head>
<body>

<h1>MA20轮动策略V5回测报告</h1>
<p class="subtitle">上证50 / 创业板50 / 纳斯达克 三指数轮动 + 国债避险 &nbsp;|&nbsp; 手续费万分之二/单边 &nbsp;|&nbsp; 2026-07-20</p>

<div class="strategy-box">
  <h2>策略说明（V5 — 三指数轮动 + 国债避险）</h2>
  <p><span class="formula">买入因子 = 当日收盘价 / 当日MA20 - 1</span></p>
  <p>1. 每日收盘后计算上证50、创业板50、纳斯达克三个指数的买入因子</p>
  <p>2. 三个指数中哪个买入因子最高 → 次日开盘价买入该指数</p>
  <p>3. 三个买入因子<strong>均小于0</strong>（均跌破MA20）→ 次日开盘价买入<strong>国债指数</strong></p>
  <p>4. 每次买入或卖出收取<strong>万分之二</strong>(0.02%)手续费，切换持仓总成本万分之四(0.04%)</p>
  <div class="warn">
    ⚠️ <b>重要发现</b>：加入纳斯达克后，策略在长周期出现<b>严重亏损</b>（近10年-42.70%，近5年-55.12%），
    最大回撤高达<b>-78.85%</b>。详见下方分析。
  </div>
</div>

<div class="card">
  <h2>各时段核心指标（五路对比）</h2>
  <table id="mainTable">
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th rowspan="2">日期范围</th>
        <th rowspan="2">交易日</th>
        <th colspan="5" class="group">总收益率</th>
        <th colspan="5" class="group">年化收益率</th>
        <th colspan="5" class="group">最大回撤</th>
        <th colspan="5" class="group">夏普比率</th>
      </tr>
      <tr>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>纳斯达克</th><th>国债</th>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>纳斯达克</th><th>国债</th>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>纳斯达克</th><th>国债</th>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>纳斯达克</th><th>国债</th>
      </tr>
    </thead>
    <tbody id="tableBody"></tbody>
  </table>
</div>

<div class="card">
  <h2>全周期净值曲线（2014年至今）</h2>
  <p style="font-size:13px;color:#666;">含手续费 | 五条净值线对比</p>
  <div class="chart-container"><canvas id="chartFull"></canvas></div>
  <div class="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#e53935"></div>轮动策略V5</div>
    <div class="legend-item"><div class="legend-dot" style="background:#1e88e5"></div>上证50</div>
    <div class="legend-item"><div class="legend-dot" style="background:#43a047"></div>创业板50</div>
    <div class="legend-item"><div class="legend-dot" style="background:#ff9800"></div>纳斯达克</div>
    <div class="legend-item"><div class="legend-dot" style="background:#8e24aa"></div>国债</div>
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
        <th>纳斯达克</th>
        <th>国债</th>
        <th>持仓分布</th>
      </tr>
    </thead>
    <tbody id="posBody"></tbody>
  </table>
</div>

<div class="card">
  <h2>V4 vs V5 对比（加入纳斯达克的影响）</h2>
  <table class="compare-table">
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th colspan="2">V4（上证50+创业板50+国债）</th>
        <th colspan="2">V5（+纳斯达克）</th>
        <th colspan="2">变化</th>
      </tr>
      <tr>
        <th>总收益</th><th>最大回撤</th>
        <th>总收益</th><th>最大回撤</th>
        <th>收益差</th><th>回撤差</th>
      </tr>
    </thead>
    <tbody>
      <tr><td class="period">近10年</td><td class="pos">181.66%</td><td class="neg">-32.70%</td><td class="neg">-42.70%</td><td class="neg">-78.85%</td><td class="neg">-224.36%</td><td class="neg">-46.15%</td></tr>
      <tr><td class="period">近5年</td><td class="pos">21.29%</td><td class="neg">-32.70%</td><td class="neg">-55.12%</td><td class="neg">-78.85%</td><td class="neg">-76.41%</td><td class="neg">-46.15%</td></tr>
      <tr><td class="period">近3年</td><td class="pos">42.32%</td><td class="neg">-21.44%</td><td class="pos">53.93%</td><td class="neg">-34.49%</td><td class="pos">+11.61%</td><td class="neg">-13.05%</td></tr>
      <tr><td class="period">近1年</td><td class="pos">21.04%</td><td class="neg">-21.05%</td><td class="pos">7.58%</td><td class="neg">-34.49%</td><td class="neg">-13.46%</td><td class="neg">-13.44%</td></tr>
    </tbody>
  </table>
  <div class="highlight">
    <b>关键发现：加入纳斯达克严重破坏了策略</b><br><br>
    • <b>长周期巨亏</b>：近10年从+181.66%暴跌到-42.70%，近5年从+21.29%变成-55.12%。策略净值被"腰斩再腰斩"<br>
    • <b>最大回撤爆炸</b>：从-32.70%恶化到-78.85%，远超任何单指数持有。策略几乎亏掉八成<br>
    • <b>根源：追高纳斯达克</b>。纳指ETF在高位时买入因子最高（close远超MA20），策略追入后遭遇暴跌（纳指本身近10年最大回撤-77.68%）。MA20择时在纳指这种"急涨急跌"资产上失效——涨得快时bf一直很高追在山顶，跌得快时跌破MA20才切换已晚<br>
    • <b>近3年是唯一例外</b>：纳指近3年涨81%，策略追入吃到部分涨幅，收益53.93%超过V4。但回撤仍恶化(-34% vs -21%)<br>
    • <b>切换更频繁</b>：492次切换(近10年) vs V4的417次，手续费19.72% vs 16.72%，三资产竞争加剧了切换<br>
    • <b>结论</b>：<b>不是资产越多越好</b>。MA20轮动适合"趋势同步、波动适中"的资产组合。纳斯达克与A股低相关且波动剧烈，用bf=close/MA20-1择时反而成了"追涨杀跌"的反向指标。V4（上证50+创业板50+国债）仍是最优配置
  </div>
</div>

<script>
const DATA = {data_json};

function colorClass(v) {{ return v >= 0 ? 'pos' : 'neg'; }}
function bestClass(val, arr) {{ return val === Math.max(...arr) ? 'best' : ''; }}

const tbody = document.getElementById('tableBody');
DATA.table_rows.forEach(row => {{
  const tots = [row._strat_total, row._bh1_total, row._bh2_total, row._bh3_total, row._bh4_total];
  const anns = [row._strat_ann, row._bh1_ann, row._bh2_ann, row._bh3_ann, row._bh4_ann];
  tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="period">${{row.period}}</td>
    <td class="date-range">${{row.date_range}}</td>
    <td>${{row.n_days}}</td>
    <td class="${{colorClass(row._strat_total)}} ${{bestClass(row._strat_total, tots)}}">${{row.strat_total}}</td>
    <td class="${{colorClass(row._bh1_total)}} ${{bestClass(row._bh1_total, tots)}}">${{row.bh1_total}}</td>
    <td class="${{colorClass(row._bh2_total)}} ${{bestClass(row._bh2_total, tots)}}">${{row.bh2_total}}</td>
    <td class="${{colorClass(row._bh3_total)}} ${{bestClass(row._bh3_total, tots)}}">${{row.bh3_total}}</td>
    <td class="${{colorClass(row._bh4_total)}} ${{bestClass(row._bh4_total, tots)}}">${{row.bh4_total}}</td>
    <td class="${{colorClass(row._strat_ann)}} ${{bestClass(row._strat_ann, anns)}}">${{row.strat_ann}}</td>
    <td class="${{colorClass(row._bh1_ann)}} ${{bestClass(row._bh1_ann, anns)}}">${{row.bh1_ann}}</td>
    <td class="${{colorClass(row._bh2_ann)}} ${{bestClass(row._bh2_ann, anns)}}">${{row.bh2_ann}}</td>
    <td class="${{colorClass(row._bh3_ann)}} ${{bestClass(row._bh3_ann, anns)}}">${{row.bh3_ann}}</td>
    <td class="${{colorClass(row._bh4_ann)}} ${{bestClass(row._bh4_ann, anns)}}">${{row.bh4_ann}}</td>
    <td class="neg">${{row.strat_mdd}}</td>
    <td class="neg">${{row.bh1_mdd}}</td>
    <td class="neg">${{row.bh2_mdd}}</td>
    <td class="neg">${{row.bh3_mdd}}</td>
    <td class="neg">${{row.bh4_mdd}}</td>
    <td>${{row.strat_sharpe}}</td>
    <td>${{row.bh1_sharpe}}</td>
    <td>${{row.bh2_sharpe}}</td>
    <td>${{row.bh3_sharpe}}</td>
    <td>${{row.bh4_sharpe}}</td>
  `;
  tbody.appendChild(tr);
}});

const posBody = document.getElementById('posBody');
DATA.table_rows.forEach(row => {{
  const h1 = parseFloat(row.hold1_pct);
  const h2 = parseFloat(row.hold2_pct);
  const h3 = parseFloat(row.hold3_pct);
  const h4 = parseFloat(row.hold4_pct);
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="period">${{row.period}}</td>
    <td>${{row.switches}}</td>
    <td class="neg">${{row.total_fee}}</td>
    <td>${{row.hold1_pct}}</td>
    <td>${{row.hold2_pct}}</td>
    <td>${{row.hold3_pct}}</td>
    <td>${{row.hold4_pct}}</td>
    <td style="min-width:240px;">
      <div class="pos-bar">
        <div style="width:${{h1}}%;background:#1e88e5">${{h1>10?row.hold1_pct:''}}</div>
        <div style="width:${{h2}}%;background:#43a047">${{h2>10?row.hold2_pct:''}}</div>
        <div style="width:${{h3}}%;background:#ff9800">${{h3>10?row.hold3_pct:''}}</div>
        <div style="width:${{h4}}%;background:#8e24aa">${{h4>10?row.hold4_pct:''}}</div>
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
  const datasets = [
    {{ label: '轮动策略V5', data: chartData.strat,
      borderColor: '#e53935', backgroundColor: 'rgba(229,57,53,0.08)',
      borderWidth: 2, pointRadius: 0, fill: true, tension: 0.1 }},
    {{ label: '上证50', data: chartData.bh1,
      borderColor: '#1e88e5', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1 }},
    {{ label: '创业板50', data: chartData.bh2,
      borderColor: '#43a047', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1 }},
    {{ label: '纳斯达克', data: chartData.bh3,
      borderColor: '#ff9800', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1 }},
    {{ label: '国债', data: chartData.bh4,
      borderColor: '#8e24aa', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1 }},
  ];
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

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/MA20轮动策略V5回测报告.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("HTML报告已生成: MA20轮动策略V5回测报告.html")
