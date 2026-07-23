# -*- coding: utf-8 -*-
"""生成V7 HTML回测报告 - 六指数轮动+国债避险"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v7_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

periods = ['近10年', '近5年', '近3年', '近1年']
# 1=上证50 2=创业板50 3=纳斯达克100 4=沪深300 5=中证500 6=中证1000 7=国债
STOCK = [1,2,3,4,5,6]
ALL = [1,2,3,4,5,6,7]

def fmt_pct(v):
    return f"{v*100:.2f}%"

table_rows = []
for p in periods:
    r = data['results'][p]
    row = {
        'period': p,
        'date_range': f"{r['start_date']} ~ {r['end_date']}",
        'n_days': r['n_days'],
        'strat_total': fmt_pct(r['strat_total']),
        'strat_ann': fmt_pct(r['strat_ann']),
        'strat_mdd': fmt_pct(r['strat_mdd']),
        'strat_sharpe': f"{r['strat_sharpe']:.2f}",
        'switches': r['switches'],
        'total_fee': fmt_pct(r['total_fee']),
        '_strat_total': r['strat_total'],
        '_strat_ann': r['strat_ann'],
    }
    for i in ALL:
        row[f'bh{i}_total'] = fmt_pct(r[f'bh{i}_total'])
        row[f'bh{i}_ann'] = fmt_pct(r[f'bh{i}_ann'])
        row[f'bh{i}_mdd'] = fmt_pct(r[f'bh{i}_mdd'])
        row[f'bh{i}_sharpe'] = f"{r[f'bh{i}_sharpe']:.2f}"
        row[f'hold{i}_pct'] = fmt_pct(r[f'hold{i}_pct'])
        row[f'_bh{i}_total'] = r[f'bh{i}_total']
        row[f'_bh{i}_ann'] = r[f'bh{i}_ann']
    row['cash_pct'] = fmt_pct(r['cash_pct'])
    table_rows.append(row)

# 降采样
full = data['full_nav']
n = len(full['dates'])
step = max(1, n // 800)
chart_full = {
    'dates': full['dates'][::step],
    'strat': full['strat'][::step],
}
for i in ALL:
    chart_full[f'bh{i}'] = full[f'bh{i}'][::step]

chart_periods = {}
for p in periods:
    pn = data['period_navs'][p]
    np_ = len(pn['dates'])
    sp = max(1, np_ // 600)
    chart_periods[p] = {'dates': pn['dates'][::sp], 'strat': pn['strat'][::sp]}
    for i in ALL:
        chart_periods[p][f'bh{i}'] = pn[f'bh{i}'][::sp]

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
<title>MA20轮动策略V7回测报告 - 六指数轮动</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #f5f7fa; color: #1a1a2e; line-height: 1.6;
    padding: 20px; max-width: 1300px; margin: 0 auto;
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
    background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
    color: #fff; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px;
  }}
  .strategy-box h2 {{ color: #fff; border-left-color: rgba(255,255,255,0.5); }}
  .strategy-box p {{ font-size: 14px; opacity: 0.95; margin-top: 8px; }}
  .strategy-box .formula {{
    display: inline-block; background: rgba(255,255,255,0.2);
    padding: 4px 12px; border-radius: 6px; font-family: monospace;
    font-size: 14px; margin: 4px 4px 4px 0;
  }}
  .good {{
    background: #e8f5e9; border: 1px solid #66bb6a; border-radius: 8px;
    padding: 12px 16px; margin-top: 12px; font-size: 13px; color: #2e7d32;
  }}
  .info {{
    background: #e3f2fd; border: 1px solid #64b5f6; border-radius: 8px;
    padding: 12px 16px; margin-top: 12px; font-size: 13px; color: #1565c0;
  }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; font-size: 10px; min-width: 100%; }}
  th {{ background: #f0f2f5; padding: 6px 4px; text-align: center;
    font-weight: 600; color: #555; white-space: nowrap; }}
  th.group {{ background: #e8eaf6; color: #333; }}
  td {{ padding: 6px 4px; text-align: center; border-bottom: 1px solid #eee;
    white-space: nowrap; }}
  td.period {{ font-weight: 700; color: #333; font-size: 12px; }}
  td.date-range {{ font-size: 9px; color: #999; }}
  .pos {{ color: #d32f2f; font-weight: 600; }}
  .neg {{ color: #2e7d32; font-weight: 600; }}
  .best {{ background: #fff3e0; border-radius: 4px; }}
  .chart-container {{ position: relative; height: 420px; margin-top: 12px; }}
  .chart-container-small {{ position: relative; height: 320px; margin-top: 12px; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .pos-bar {{
    display: flex; height: 24px; border-radius: 6px; overflow: hidden;
    margin-top: 8px; font-size: 10px; min-width: 280px;
  }}
  .pos-bar div {{ display: flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 600; }}
  .legend {{ display: flex; gap: 14px; margin-top: 12px; font-size: 12px; flex-wrap: wrap; }}
  .legend-item {{ display: flex; align-items: center; gap: 5px; }}
  .legend-dot {{ width: 12px; height: 12px; border-radius: 3px; }}
  .highlight {{
    font-size: 13px; color: #555; margin-top: 12px;
    background: #f3e5f5; padding: 14px; border-radius: 8px; border-left: 3px solid #8e24aa;
  }}
  .compare-table td {{ font-size: 13px; padding: 10px 8px; }}
</style>
</head>
<body>

<h1>MA20轮动策略V7回测报告</h1>
<p class="subtitle">上证50 / 创业板50 / 纳斯达克100 / 沪深300 / 中证500 / 中证1000 六指数轮动 + 国债避险 &nbsp;|&nbsp; 手续费万分之二/单边 &nbsp;|&nbsp; 2026-07-20</p>

<div class="strategy-box">
  <h2>策略说明（V7 — 六指数轮动版）</h2>
  <p><span class="formula">买入因子 = 当日收盘价 / 当日MA20 - 1</span></p>
  <p>1. 每日收盘后计算六个股票指数的买入因子：上证50、创业板50、纳斯达克100、沪深300、中证500、中证1000</p>
  <p>2. 六个指数中哪个买入因子最高 → 次日开盘价买入该指数</p>
  <p>3. 六个买入因子<strong>均小于0</strong>（均跌破MA20）→ 次日开盘价买入<strong>国债指数</strong></p>
  <p>4. 每次买入或卖出收取<strong>万分之二</strong>(0.02%)手续费，切换持仓总成本万分之四(0.04%)</p>
  <div class="good">
    ✅ <b>历史最优</b>：六指数轮动近10年收益达<b>428.63%</b>（年化19.59%），夏普0.84，
    最大回撤仅-27.58%——收益超越V6(401.25%)且回撤更低(-31.44%→-27.58%)，近1年从V6的6.11%跃升至25.42%。
  </div>
  <div class="info">
    ℹ️ <b>与V6的区别</b>：V6仅用上证50/创业板50/纳斯达克100三指数轮动，V7在此基础上新增沪深300、中证500、中证1000三个A股宽基指数。
    更多资产意味着更强的选优能力——每日可在6个指数中挑选趋势最强者，捕捉到中证500/中证1000等中小盘行情。
    注意：因中证500数据始于2007年、创业板50始于2014年，内连接后回测起点为2014年6月。
  </div>
</div>

<div class="card">
  <h2>各时段核心指标（八路对比）</h2>
  <div class="table-wrap">
  <table id="mainTable">
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th rowspan="2">日期范围</th>
        <th rowspan="2">交易日</th>
        <th colspan="8" class="group">总收益率</th>
        <th colspan="8" class="group">年化收益率</th>
        <th colspan="8" class="group">最大回撤</th>
        <th colspan="8" class="group">夏普比率</th>
      </tr>
      <tr>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>国债</th>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>国债</th>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>国债</th>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>国债</th>
      </tr>
    </thead>
    <tbody id="tableBody"></tbody>
  </table>
  </div>
</div>

<div class="card">
  <h2>全周期净值曲线（2014年至今）</h2>
  <p style="font-size:13px;color:#666;">含手续费 | 八条净值线对比</p>
  <div class="chart-container"><canvas id="chartFull"></canvas></div>
  <div class="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#e53935"></div>轮动策略V7</div>
    <div class="legend-item"><div class="legend-dot" style="background:#1e88e5"></div>上证50</div>
    <div class="legend-item"><div class="legend-dot" style="background:#43a047"></div>创业板50</div>
    <div class="legend-item"><div class="legend-dot" style="background:#ff9800"></div>纳斯达克100</div>
    <div class="legend-item"><div class="legend-dot" style="background:#00acc1"></div>沪深300</div>
    <div class="legend-item"><div class="legend-dot" style="background:#8e24aa"></div>中证500</div>
    <div class="legend-item"><div class="legend-dot" style="background:#ec407a"></div>中证1000</div>
    <div class="legend-item"><div class="legend-dot" style="background:#757575"></div>国债</div>
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
  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>时段</th>
        <th>切换次数</th>
        <th>累计手续费</th>
        <th>上证50</th>
        <th>创业板50</th>
        <th>纳指100</th>
        <th>沪深300</th>
        <th>中证500</th>
        <th>中证1000</th>
        <th>国债</th>
        <th>持仓分布</th>
      </tr>
    </thead>
    <tbody id="posBody"></tbody>
  </table>
  </div>
</div>

<div class="card">
  <h2>三版策略横向对比（V4双指数 / V6三指数 / V7六指数）</h2>
  <div class="table-wrap">
  <table class="compare-table">
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th colspan="2">V4（上证50+创业板50+国债）</th>
        <th colspan="2">V6（+纳斯达克100）</th>
        <th colspan="2">V7（+沪深300+中证500+中证1000）</th>
      </tr>
      <tr>
        <th>总收益</th><th>最大回撤</th>
        <th>总收益</th><th>最大回撤</th>
        <th>总收益</th><th>最大回撤</th>
      </tr>
    </thead>
    <tbody>
      <tr><td class="period">近10年</td><td class="pos">181.66%</td><td class="neg">-32.70%</td><td class="pos">401.25%</td><td class="neg">-31.44%</td><td class="pos best">428.63%</td><td class="neg">-27.58%</td></tr>
      <tr><td class="period">近5年</td><td class="pos">21.29%</td><td class="neg">-32.70%</td><td class="pos">95.34%</td><td class="neg">-29.43%</td><td class="pos best">139.20%</td><td class="neg">-23.27%</td></tr>
      <tr><td class="period">近3年</td><td class="pos">42.32%</td><td class="neg">-21.44%</td><td class="pos">88.71%</td><td class="neg">-29.43%</td><td class="pos best">99.79%</td><td class="neg">-23.27%</td></tr>
      <tr><td class="period">近1年</td><td class="pos">21.04%</td><td class="neg">-21.05%</td><td class="pos">6.11%</td><td class="neg">-29.43%</td><td class="pos best">25.42%</td><td class="neg">-18.37%</td></tr>
    </tbody>
  </table>
  </div>
  <div class="highlight">
    <b>关键发现：资产多样性提升策略鲁棒性</b><br><br>
    • <b>V7全面超越V6</b>：四个时段收益全部提升，近10年428.63% &gt; V6的401.25%；近5年139.20% &gt; 95.34%；近3年99.79% &gt; 88.71%；近1年25.42% &gt; 6.11%（提升4倍）<br>
    • <b>回撤同步改善</b>：近10年最大回撤从V6的-31.44%降至-27.58%，近5年从-29.43%降至-23.27%。更多资产提供更多避风港<br>
    • <b>近1年飞跃的原因</b>：V6近1年仅6.11%因在纳指100和创业板间频繁切换；V7新增中证500（近1年涨24.94%）后，策略捕捉到中小盘行情，且创业板50持仓占比升至43.2%吃到完整涨幅<br>
    • <b>持仓更分散</b>：纳指100仍占33.8%（美股长牛），创业板50占23.4%，中证1000占10.3%，上证50占11.6%——新增的沪深300仅占1.8%（与上证50高度相关被替代），中证500占4.5%<br>
    • <b>代价：手续费上升</b>：近10年累计手续费22.28%（V6为19.48%），切换557次（V6约500次）。更多资产带来更多切换，但收益提升远超成本<br>
    • <b>结论</b>：在保证数据质量（用原生指数而非ETF）的前提下，增加相关性较低的优质资产能持续提升轮动策略表现。V7是迄今最优版本
  </div>
</div>

<script>
const DATA = {data_json};

function colorClass(v) {{ return v >= 0 ? 'pos' : 'neg'; }}
function bestClass(val, arr) {{ return val === Math.max(...arr) ? 'best' : ''; }}

const tbody = document.getElementById('tableBody');
DATA.table_rows.forEach(row => {{
  const tots = [row._strat_total, row._bh1_total, row._bh2_total, row._bh3_total, row._bh4_total, row._bh5_total, row._bh6_total, row._bh7_total];
  const anns = [row._strat_ann, row._bh1_ann, row._bh2_ann, row._bh3_ann, row._bh4_ann, row._bh5_ann, row._bh6_ann, row._bh7_ann];
  const tr = document.createElement('tr');
  let html = `<td class="period">${{row.period}}</td><td class="date-range">${{row.date_range}}</td><td>${{row.n_days}}</td>`;
  // 总收益率
  html += `<td class="${{colorClass(row._strat_total)}} ${{bestClass(row._strat_total, tots)}}">${{row.strat_total}}</td>`;
  for (let i=1;i<=7;i++) html += `<td class="${{colorClass(row['_bh'+i+'_total'])}} ${{bestClass(row['_bh'+i+'_total'], tots)}}">${{row['bh'+i+'_total']}}</td>`;
  // 年化
  html += `<td class="${{colorClass(row._strat_ann)}} ${{bestClass(row._strat_ann, anns)}}">${{row.strat_ann}}</td>`;
  for (let i=1;i<=7;i++) html += `<td class="${{colorClass(row['_bh'+i+'_ann'])}} ${{bestClass(row['_bh'+i+'_ann'], anns)}}">${{row['bh'+i+'_ann']}}</td>`;
  // 最大回撤
  html += `<td class="neg">${{row.strat_mdd}}</td>`;
  for (let i=1;i<=7;i++) html += `<td class="neg">${{row['bh'+i+'_mdd']}}</td>`;
  // 夏普
  html += `<td>${{row.strat_sharpe}}</td>`;
  for (let i=1;i<=7;i++) html += `<td>${{row['bh'+i+'_sharpe']}}</td>`;
  tr.innerHTML = html;
  tbody.appendChild(tr);
}});

const COLORS = {{strat:'#e53935', bh1:'#1e88e5', bh2:'#43a047', bh3:'#ff9800', bh4:'#00acc1', bh5:'#8e24aa', bh6:'#ec407a', bh7:'#757575'}};
const LABELS = {{strat:'轮动策略V7', bh1:'上证50', bh2:'创业板50', bh3:'纳斯达克100', bh4:'沪深300', bh5:'中证500', bh6:'中证1000', bh7:'国债'}};
const POS_COLORS = {{bh1:'#1e88e5', bh2:'#43a047', bh3:'#ff9800', bh4:'#00acc1', bh5:'#8e24aa', bh6:'#ec407a', bh7:'#757575'}};

const posBody = document.getElementById('posBody');
DATA.table_rows.forEach(row => {{
  const tr = document.createElement('tr');
  let html = `<td class="period">${{row.period}}</td><td>${{row.switches}}</td><td class="neg">${{row.total_fee}}</td>`;
  for (let i=1;i<=7;i++) html += `<td>${{row['hold'+i+'_pct']}}</td>`;
  // 持仓条
  let barHtml = '<div class="pos-bar">';
  for (let i=1;i<=7;i++) {{
    const pct = parseFloat(row['hold'+i+'_pct']);
    barHtml += `<div style="width:${{pct}}%;background:${{POS_COLORS['bh'+i]}}">${{pct>8?row['hold'+i+'_pct']:''}}</div>`;
  }}
  barHtml += '</div>';
  html += `<td style="min-width:280px;">${{barHtml}}</td>`;
  tr.innerHTML = html;
  posBody.appendChild(tr);
}});

Chart.defaults.font.family = "'PingFang SC', 'Microsoft YaHei', sans-serif";
Chart.defaults.font.size = 11;

function makeChart(canvasId, chartData, showLegend) {{
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const datasets = [
    {{ label: LABELS.strat, data: chartData.strat,
      borderColor: COLORS.strat, backgroundColor: 'rgba(229,57,53,0.08)',
      borderWidth: 2.5, pointRadius: 0, fill: true, tension: 0.1 }}
  ];
  for (let i=1;i<=7;i++) {{
    datasets.push({{
      label: LABELS['bh'+i], data: chartData['bh'+i],
      borderColor: COLORS['bh'+i], borderWidth: 1.2, pointRadius: 0, fill: false, tension: 0.1
    }});
  }}
  return new Chart(ctx, {{
    type: 'line',
    data: {{ labels: chartData.dates, datasets: datasets }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: showLegend, position: 'top', labels: {{ boxWidth: 12, font: {{size:11}} }} }},
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

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/MA20轮动策略V7回测报告.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("HTML报告已生成: MA20轮动策略V7回测报告.html")
