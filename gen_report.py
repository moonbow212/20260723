# -*- coding: utf-8 -*-
"""生成HTML回测报告"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 构建结果表格数据
periods = ['近10年', '近5年', '近3年', '近1年']

def fmt_pct(v):
    return f"{v*100:.2f}%"

def fmt_pct_signed(v):
    s = fmt_pct(v)
    return s

table_rows = []
for p in periods:
    r = data['results'][p]
    table_rows.append({
        'period': p,
        'date_range': f"{r['start_date']} ~ {r['end_date']}",
        'n_days': r['n_days'],
        'strat_total': fmt_pct_signed(r['strat_total']),
        'bh1_total': fmt_pct_signed(r['bh1_total']),
        'bh2_total': fmt_pct_signed(r['bh2_total']),
        'strat_ann': fmt_pct_signed(r['strat_ann']),
        'bh1_ann': fmt_pct_signed(r['bh1_ann']),
        'bh2_ann': fmt_pct_signed(r['bh2_ann']),
        'strat_mdd': fmt_pct_signed(r['strat_mdd']),
        'bh1_mdd': fmt_pct_signed(r['bh1_mdd']),
        'bh2_mdd': fmt_pct_signed(r['bh2_mdd']),
        'strat_sharpe': f"{r['strat_sharpe']:.2f}",
        'bh1_sharpe': f"{r['bh1_sharpe']:.2f}",
        'bh2_sharpe': f"{r['bh2_sharpe']:.2f}",
        'switches': r['switches'],
        'hold1_pct': fmt_pct(r['hold1_pct']),
        'hold2_pct': fmt_pct(r['hold2_pct']),
        'cash_pct': fmt_pct(r['cash_pct']),
        # 原始数值用于着色
        '_strat_total': r['strat_total'],
        '_bh1_total': r['bh1_total'],
        '_bh2_total': r['bh2_total'],
        '_strat_ann': r['strat_ann'],
        '_bh1_ann': r['bh1_ann'],
        '_bh2_ann': r['bh2_ann'],
    })

# 准备图表数据（降采样full_nav以提升性能）
full = data['full_nav']
n = len(full['dates'])
step = max(1, n // 800)
chart_full = {
    'dates': full['dates'][::step],
    'strat': full['strat'][::step],
    'bh1': full['bh1'][::step],
    'bh2': full['bh2'][::step],
}

# 各时段图表数据也降采样
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
}

data_json = json.dumps(all_data, ensure_ascii=False)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MA20轮动策略回测报告</title>
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
  .neutral {{ color: #666; }}
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
  .legend {{ display: flex; gap: 20px; margin-top: 12px; font-size: 13px; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  .legend-dot {{ width: 12px; height: 12px; border-radius: 3px; }}
  .note {{ font-size: 12px; color: #999; margin-top: 8px; }}
  .highlight {{ font-size: 13px; color: #555; margin-top: 12px;
    background: #f9f9f9; padding: 12px; border-radius: 8px; border-left: 3px solid #ffc107; }}
</style>
</head>
<body>

<h1>MA20轮动策略回测报告</h1>
<p class="subtitle">上证50 vs 创业板50 指数轮动 &nbsp;|&nbsp; 数据区间: 2014-06-18 ~ 2026-07-20 &nbsp;|&nbsp; 生成日期: 2026-07-20</p>

<div class="strategy-box">
  <h2>策略说明</h2>
  <p>
    <span class="formula">买入因子 = 当日收盘价 / 当日MA20 - 1</span>
  </p>
  <p>1. 每日收盘后，分别计算上证50和创业板50的买入因子</p>
  <p>2. 哪个指数买入因子更高 → 次日开盘价买入（切换至该指数）</p>
  <p>3. 如果两个指数均跌破MA20（close/MA20 &lt; 1，即买入因子 &lt; 0）→ 清仓持现金</p>
  <p style="margin-top:10px; font-size:12px; opacity:0.8;">
    注：用户原文"买入因子都低于1就清仓"。买入因子=close/MA20-1，字面"低于1"即close/MA20&lt;2，
    几乎永远满足（不合理）。合理解释为close/MA20比值低于1（跌破均线）时清仓，等价于买入因子&lt;0。
    本报告采用此解释。收益计算采用开盘价执行、open-to-open收益，现金无利息。
  </p>
</div>

<div class="card">
  <h2>各时段收益率对比</h2>
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
  <p style="font-size:13px;color:#666;">以首个交易日净值为1，三策略起点统一</p>
  <div class="chart-container"><canvas id="chartFull"></canvas></div>
  <div class="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#e53935"></div>轮动策略</div>
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
  <h2>近1年净值曲线</h2>
  <div class="chart-container-small"><canvas id="chart1y"></canvas></div>
</div>

<div class="card">
  <h2>持仓分布与交易统计</h2>
  <table>
    <thead>
      <tr>
        <th>时段</th>
        <th>交易切换次数</th>
        <th>持有上证50占比</th>
        <th>持有创业板50占比</th>
        <th>空仓占比</th>
        <th>持仓分布</th>
      </tr>
    </thead>
    <tbody id="posBody"></tbody>
  </table>
  <div class="highlight">
    <b>关键发现：</b><br>
    • 策略在<strong>近10年</strong>表现优异，总收益183.16%远超上证50(34.01%)和创业板50(71.04%)，年化11.41%，且最大回撤-33.64%显著低于两个指数单独持有<br>
    • <strong>近5年</strong>市场低迷期（2021-2026），策略仍获正收益21.19%，而上证50亏损-13.42%，体现了空仓规避风险的价值<br>
    • <strong>近3年/近1年</strong>创业板50强势上涨，单纯持有创业板50收益更高（75.52%/59.61%），轮动策略未能完全跟上，但回撤更可控<br>
    • 策略约33-40%时间空仓，有效降低了系统性回撤，适合震荡和下行市场；单边牛市中择时会跑输满仓
  </div>
</div>

<script>
const DATA = {data_json};

function colorClass(v) {{
  return v >= 0 ? 'pos' : 'neg';
}}

function bestClass(val, arr) {{
  const max = Math.max(...arr);
  return val === max ? 'best' : '';
}}

// 填充表格
const tbody = document.getElementById('tableBody');
DATA.table_rows.forEach(row => {{
  const tr = document.createElement('tr');
  const tots = [row._strat_total, row._bh1_total, row._bh2_total];
  const anns = [row._strat_ann, row._bh1_ann, row._bh2_ann];
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

// 持仓分布表
const posBody = document.getElementById('posBody');
DATA.table_rows.forEach(row => {{
  const h1 = parseFloat(row.hold1_pct);
  const h2 = parseFloat(row.hold2_pct);
  const cash = parseFloat(row.cash_pct);
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="period">${{row.period}}</td>
    <td>${{row.switches}}</td>
    <td>${{row.hold1_pct}}</td>
    <td>${{row.hold2_pct}}</td>
    <td>${{row.cash_pct}}</td>
    <td style="min-width:200px;">
      <div class="pos-bar">
        <div style="width:${{h1}}%;background:#1e88e5">${{h1>15?row.hold1_pct:''}}</div>
        <div style="width:${{h2}}%;background:#43a047">${{h2>15?row.hold2_pct:''}}</div>
        <div style="width:${{cash}}%;background:#999">${{cash>15?row.cash_pct:''}}</div>
      </div>
    </td>
  `;
  posBody.appendChild(tr);
}});

// Chart.js 配置
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
        {{
          label: '轮动策略',
          data: chartData.strat,
          borderColor: '#e53935',
          backgroundColor: 'rgba(229,57,53,0.08)',
          borderWidth: 2,
          pointRadius: 0,
          fill: true,
          tension: 0.1
        }},
        {{
          label: '上证50 买入持有',
          data: chartData.bh1,
          borderColor: '#1e88e5',
          backgroundColor: 'transparent',
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
          tension: 0.1
        }},
        {{
          label: '创业板50 买入持有',
          data: chartData.bh2,
          borderColor: '#43a047',
          backgroundColor: 'transparent',
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
          tension: 0.1
        }}
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: showLegend, position: 'top' }},
        tooltip: {{
          callbacks: {{
            label: function(ctx) {{
              return ctx.dataset.label + ': ' + (ctx.parsed.y).toFixed(4);
            }}
          }}
        }}
      }},
      scales: {{
        x: {{
          ticks: {{ maxTicksLimit: 8, maxRotation: 0 }},
          grid: {{ display: false }}
        }},
        y: {{
          ticks: {{ callback: v => v.toFixed(2) }},
          grid: {{ color: '#f0f0f0' }}
        }}
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

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/MA20轮动策略回测报告.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("HTML报告已生成: MA20轮动策略回测报告.html")
