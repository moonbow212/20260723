# -*- coding: utf-8 -*-
"""
生成V14阈值敏感性分析的HTML报告
"""

import json
import html

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v14_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

results = data['results']
names = data['names']
bond_id = data['bond_id']

PERIODS = ['近10年', '近5年', '近3年', '近1年']

# ============ 工具函数 ============
def fmt_pct(x, digits=2):
    if x is None: return '-'
    return f"{x*100:.{digits}f}%"

# ============ 找出关键组合 ============
def find_combo(pname, trigger, release):
    for c in results[pname]['combos']:
        if c['trigger'] == trigger and c['release'] == release:
            return c
    return None

baseline = {p: find_combo(p, None, None) for p in PERIODS}
v13_default = {p: find_combo(p, 0.10, 0.05) for p in PERIODS}
best_return = {p: max(results[p]['combos'], key=lambda c: c['total']) for p in PERIODS}
best_sharpe = {p: max(results[p]['combos'], key=lambda c: c['sharpe']) for p in PERIODS}
best_calmar = {p: max(results[p]['combos'], key=lambda c: c['total']/abs(c['mdd']) if c['mdd']<0 else 0) for p in PERIODS}

# 4个时段综合排名（按总收益之和）
def score_combo(combo_label):
    s = 0
    for p in PERIODS:
        c = find_combo(p, combo_label[0], combo_label[1])
        if c: s += c['total']
    return s

# 找最稳定的赢家（每个时段前3都出现的阈值）
# 用所有常规组合找综合最佳
seen = set()
for p in PERIODS:
    for c in results[p]['combos']:
        key = (c['trigger'], c['release'])
        seen.add(key)
combo_score = []
for t, r in seen:
    if t is None: continue  # 跳过基线
    s = score_combo((t, r))
    combo_score.append(((t, r), s))
combo_score.sort(key=lambda x: -x[1])
top_combos_overall = combo_score[:10]  # 综合前10

# ============ HTML ============
HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>MA20轮动策略V14 - 熔断阈值敏感性分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
         background: #f5f7fa; color: #2c3e50; margin: 0; padding: 20px; }
  .container { max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
  h1 { color: #1a3a5c; border-bottom: 3px solid #3498db; padding-bottom: 12px; }
  h2 { color: #1a3a5c; margin-top: 30px; padding-left: 12px; border-left: 4px solid #3498db; }
  h3 { color: #34495e; margin-top: 20px; }
  .summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }
  .card { background: #f8f9fb; padding: 15px; border-radius: 6px; border: 1px solid #e1e4e8; }
  .card .label { font-size: 12px; color: #7f8c8d; margin-bottom: 6px; }
  .card .value { font-size: 22px; font-weight: 600; color: #1a3a5c; }
  .card .sub { font-size: 11px; color: #95a5a6; margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
  th { background: #34495e; color: white; padding: 8px 10px; text-align: center; font-weight: 500; }
  td { padding: 6px 10px; text-align: center; border-bottom: 1px solid #ecf0f1; }
  tr:hover { background: #f8f9fb; }
  .good { color: #c0392b; font-weight: 600; }  /* 涨红色 */
  .bad { color: #27ae60; font-weight: 600; }   /* 跌绿色 */
  .neutral { color: #7f8c8d; }
  .highlight { background: #fff3cd; font-weight: 600; }
  .winner { background: #d4edda; font-weight: 700; color: #155724; }
  .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }
  .chart-box { background: white; padding: 15px; border-radius: 6px; border: 1px solid #e1e4e8; }
  .chart-box h4 { margin: 0 0 10px 0; color: #34495e; }
  .narrative { background: #f0f7ff; border-left: 4px solid #3498db; padding: 12px 18px; margin: 16px 0; border-radius: 4px; }
  .narrative strong { color: #1a3a5c; }
  .insight { background: #fff8e1; border-left: 4px solid #f39c12; padding: 12px 18px; margin: 16px 0; border-radius: 4px; }
  .info-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #ecf0f1; }
  .info-row:last-child { border-bottom: none; }
</style>
</head>
<body>
<div class="container">

<h1>MA20轮动策略 V14 —— 熔断阈值敏感性分析</h1>
<p style="color: #7f8c8d;">在V8八指数轮动基础上，测试不同回撤熔断阈值（触发/解除）的策略效果 | 数据截至 """ + results['近10年']['nav_dates'][-1] + """</p>

<div class="narrative">
<strong>核心发现：V13原版 10%/5% 阈值过于保守。</strong>更紧的触发阈值（5%-6%）全面碾压V13：
<ul>
  <li><strong>近10年</strong>：收益从 498.98% → <strong>1717.42%</strong>（+3.4倍），回撤从 -10.55% → -5.01%，夏普从 1.07 → <strong>1.95</strong></li>
  <li><strong>近5年</strong>：收益从 107.23% → <strong>407.58%</strong>（+3.8倍），回撤从 -12.50% → -4.86%</li>
  <li><strong>近3年</strong>：收益从 101.83% → <strong>294.00%</strong>（+2.9倍），回撤从 -11.27% → -4.86%</li>
  <li><strong>近1年</strong>：收益从 13.48% → <strong>91.25%</strong>（+6.8倍），回撤从 -11.27% → -4.05%</li>
</ul>
<strong>建议新阈值：5%/4% 或 6%/5%</strong>。
</div>

<h2>一、关键阈值对比（各时段 Top 1 vs V13 vs V8基线）</h2>
<div class="charts-grid" style="grid-template-columns: 1fr 1fr;">
"""

# 关键阈值对比表
HTML += """
<table>
<tr>
  <th>时段</th>
  <th>阈值</th>
  <th>总收益</th>
  <th>年化</th>
  <th>最大回撤</th>
  <th>夏普</th>
  <th>卡玛</th>
  <th>熔断占比</th>
</tr>
"""
for p in PERIODS:
    n = results[p]['n_days']
    HTML += f'<tr><td rowspan="3"><strong>{p}</strong><br><span class="neutral">({n}天)</span></td>'
    for label, c in [('V8基线', baseline[p]), ('V13(10%/5%)', v13_default[p]), (f'最佳: {best_return[p]["label"]}', best_return[p])]:
        calmar = c['total']/abs(c['mdd']) if c['mdd']<0 else 0
        cls = 'winner' if label.startswith('最佳') else ''
        HTML += f'<td class="{cls}">{label}</td>'
        HTML += f'<td class="good">{fmt_pct(c["total"])}</td>'
        HTML += f'<td class="good">{fmt_pct(c["ann"])}</td>'
        HTML += f'<td class="bad">{fmt_pct(c["mdd"])}</td>'
        HTML += f'<td>{c["sharpe"]:.2f}</td>'
        HTML += f'<td>{calmar:.2f}</td>'
        HTML += f'<td>{fmt_pct(c["cb_pct"],1)}</td>'
        HTML += '</tr><tr>'
    HTML = HTML[:-8] + '</tr>'  # 去掉最后一个tr
HTML += "</table>"

HTML += """
</div>

<h2>二、综合 Top 10 阈值（四个时段累计总收益排名）</h2>
"""

HTML += """
<table>
<tr>
  <th>排名</th>
  <th>触发阈值</th>
  <th>解除阈值</th>
  <th>近10年收益</th>
  <th>近5年收益</th>
  <th>近3年收益</th>
  <th>近1年收益</th>
  <th>近10年回撤</th>
  <th>近10年夏普</th>
  <th>类型</th>
</tr>
"""
for i, ((t, r), s) in enumerate(top_combos_overall, 1):
    label_release = f"{r*100:.0f}%" if r is not None else "永不"
    ttype = "一次性" if r is None else "正常"
    c10 = find_combo('近10年', t, r)
    HTML += f'<tr>'
    HTML += f'<td>{i}</td>'
    HTML += f'<td>{t*100:.0f}%</td>'
    HTML += f'<td>{label_release}</td>'
    HTML += f'<td class="good">{fmt_pct(c10["total"])}</td>'
    HTML += f'<td class="good">{fmt_pct(find_combo("近5年", t, r)["total"])}</td>'
    HTML += f'<td class="good">{fmt_pct(find_combo("近3年", t, r)["total"])}</td>'
    HTML += f'<td class="good">{fmt_pct(find_combo("近1年", t, r)["total"])}</td>'
    HTML += f'<td class="bad">{fmt_pct(c10["mdd"])}</td>'
    HTML += f'<td>{c10["sharpe"]:.2f}</td>'
    HTML += f'<td>{ttype}</td>'
    HTML += f'</tr>'
HTML += "</table>"

# ============ 三、散点图：回撤 vs 收益 ============
HTML += """
<h2>三、阈值散点图（X=最大回撤, Y=总收益, 颜色=夏普）</h2>
<div class="charts-grid">
"""
for p in PERIODS:
    n = results[p]['n_days']
    box_id = f"scatter_{p}"
    HTML += f"""
<div class="chart-box">
  <h4>{p}（{n}天）</h4>
  <canvas id="{box_id}" height="280"></canvas>
</div>
"""
HTML += "</div>"

# 散点图JS数据
JS_SCATTER = ""
for p in PERIODS:
    points = []
    for c in results[p]['combos']:
        if c['trigger'] is None: continue
        is_v13 = c['trigger'] == 0.10 and c['release'] == 0.05
        is_best = (c['label'] == best_return[p]['label'])
        points.append({
            'x': round(c['mdd']*100, 2),
            'y': round(c['total']*100, 2),
            'label': c['label'],
            'sharpe': round(c['sharpe'], 2),
            'is_v13': is_v13,
            'is_best': is_best,
        })
    # V8基线单独点
    b = baseline[p]
    points.append({
        'x': round(b['mdd']*100, 2),
        'y': round(b['total']*100, 2),
        'label': 'V8基线',
        'sharpe': round(b['sharpe'], 2),
        'is_v13': False,
        'is_best': False,
        'is_baseline': True,
    })
    JS_SCATTER += f"""
const ctx_{p} = document.getElementById('scatter_{p}').getContext('2d');
new Chart(ctx_{p}, {{
  type: 'scatter',
  data: {{
    datasets: [{{
      label: '阈值组合',
      data: {json.dumps(points, ensure_ascii=False)},
      backgroundColor: function(ctx) {{
        const v = ctx.raw;
        if (v.is_best) return '#c0392b';
        if (v.is_v13) return '#f39c12';
        if (v.is_baseline) return '#34495e';
        const s = v.sharpe;
        if (s > 1.5) return 'rgba(231, 76, 60, 0.7)';
        if (s > 1.0) return 'rgba(241, 196, 15, 0.7)';
        if (s > 0.5) return 'rgba(52, 152, 219, 0.6)';
        return 'rgba(149, 165, 166, 0.5)';
      }},
      borderColor: function(ctx) {{
        const v = ctx.raw;
        if (v.is_best || v.is_v13 || v.is_baseline) return '#000';
        return 'rgba(0,0,0,0.3)';
      }},
      borderWidth: function(ctx) {{
        const v = ctx.raw;
        if (v.is_best || v.is_v13 || v.is_baseline) return 2;
        return 1;
      }},
      pointRadius: function(ctx) {{
        const v = ctx.raw;
        if (v.is_best) return 10;
        if (v.is_v13) return 8;
        if (v.is_baseline) return 8;
        return 5;
      }},
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          label: function(ctx) {{
            const v = ctx.raw;
            return v.label + ': 收益' + v.y + '%, 回撤' + v.x + '%, 夏普' + v.sharpe;
          }}
        }}
      }}
    }},
    scales: {{
      x: {{ title: {{ display: true, text: '最大回撤 (%)' }}, grid: {{ color: '#ecf0f1' }} }},
      y: {{ title: {{ display: true, text: '总收益 (%)' }}, grid: {{ color: '#ecf0f1' }} }}
    }}
  }}
}});
"""

# ============ 四、近10年净值曲线对比 ============
HTML += """
<h2>四、净值曲线对比（近10年）</h2>
<div class="chart-box">
  <h4>V8基线 vs V13(10%/5%) vs Top 3 阈值</h4>
  <canvas id="nav_chart" height="120"></canvas>
</div>
"""

# Top 3 阈值（含5%/4%最佳、6%/5%次优、8%/7%稳健）
top3_thresholds = [('5%/4%', 0.05, 0.04), ('6%/5%', 0.06, 0.05), ('8%/7%', 0.08, 0.07)]
nav_series = {'dates': results['近10年']['nav_dates']}
nav_series['V8基线'] = baseline['近10年']['nav']
nav_series['V13(10%/5%)'] = v13_default['近10年']['nav']
for label, t, r in top3_thresholds:
    c = find_combo('近10年', t, r)
    nav_series[label] = c['nav']

JS_NAV = f"""
const nav_data = {json.dumps(nav_series)};
const ctx_nav = document.getElementById('nav_chart').getContext('2d');
new Chart(ctx_nav, {{
  type: 'line',
  data: {{
    labels: nav_data.dates,
    datasets: [
      {{ label: 'V8基线(无熔断)', data: nav_data['V8基线'], borderColor: '#34495e', borderWidth: 1.5, pointRadius: 0, tension: 0 }},
      {{ label: 'V13原版(10%/5%)', data: nav_data['V13(10%/5%)'], borderColor: '#f39c12', borderWidth: 1.5, pointRadius: 0, tension: 0 }},
      {{ label: '5%/4%', data: nav_data['5%/4%'], borderColor: '#c0392b', borderWidth: 2.5, pointRadius: 0, tension: 0 }},
      {{ label: '6%/5%', data: nav_data['6%/5%'], borderColor: '#e74c3c', borderWidth: 2, pointRadius: 0, tension: 0, borderDash: [5,3] }},
      {{ label: '8%/7%', data: nav_data['8%/7%'], borderColor: '#9b59b6', borderWidth: 2, pointRadius: 0, tension: 0, borderDash: [2,2] }}
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ position: 'top' }},
      tooltip: {{ mode: 'index', intersect: false }}
    }},
    scales: {{
      x: {{ ticks: {{ maxTicksLimit: 8 }}, grid: {{ color: '#ecf0f1' }} }},
      y: {{ type: 'logarithmic', title: {{ display: true, text: '净值 (对数)' }}, grid: {{ color: '#ecf0f1' }} }}
    }}
  }}
}});
"""

# ============ 五、各时段详细排名表 ============
HTML += "<h2>五、各时段完整排名（按总收益排序）</h2>"

for p in PERIODS:
    n = results[p]['n_days']
    HTML += f"<h3>{p}（{n}天，{results[p]['nav_dates'][0]} ~ {results[p]['nav_dates'][-1]}）</h3>"
    HTML += """
<table>
<tr>
  <th>排名</th>
  <th>阈值</th>
  <th>总收益</th>
  <th>年化</th>
  <th>最大回撤</th>
  <th>夏普</th>
  <th>卡玛</th>
  <th>开关次</th>
  <th>熔断天%</th>
  <th>事件数</th>
  <th>手续费</th>
</tr>
"""
    sorted_combos = sorted(results[p]['combos'], key=lambda c: -c['total'])
    for i, c in enumerate(sorted_combos, 1):
        calmar = c['total']/abs(c['mdd']) if c['mdd']<0 else 0
        label_disp = c['label']
        if c['label'] == 'V8基线(无熔断)':
            label_disp = 'V8基线'
            cls = 'highlight'
        elif c['label'] == '10%/5%':
            label_disp = '10%/5%(V13)'
            cls = 'highlight'
        elif i == 1:
            cls = 'winner'
        else:
            cls = ''
        HTML += f'<tr class="{cls}">'
        HTML += f'<td>{i}</td>'
        HTML += f'<td>{label_disp}</td>'
        HTML += f'<td class="good">{fmt_pct(c["total"])}</td>'
        HTML += f'<td class="good">{fmt_pct(c["ann"])}</td>'
        HTML += f'<td class="bad">{fmt_pct(c["mdd"])}</td>'
        HTML += f'<td>{c["sharpe"]:.2f}</td>'
        HTML += f'<td>{calmar:.2f}</td>'
        HTML += f'<td>{c["switches"]}</td>'
        HTML += f'<td>{fmt_pct(c["cb_pct"],1)}</td>'
        HTML += f'<td>{len(c["cb_events"])}</td>'
        HTML += f'<td>{fmt_pct(c["total_fee"])}</td>'
        HTML += f'</tr>'
    HTML += "</table>"

# ============ 六、结论与建议 ============
HTML += """
<h2>六、结论与建议</h2>

<div class="insight">
<strong>🔥 重要发现 1：V13阈值（10%/5%）过于保守</strong><br>
V13的 10% 触发阈值在 10 年回测中只触发 <strong>21</strong> 次，且只有 46.6% 的时间在熔断状态。
原因是策略 V8 自身的回撤已经达到 -26.56%，而 cummax 的 10% 回撤需要策略再下跌 10%（即从当前高点下跌 10%），
但 V8 在大多数下跌行情中是从接近高点位置开始下跌，所以"10% 的回撤幅度"实际意味着已经跌了很多。
更紧的阈值（5%-6%）在回撤刚出现苗头时就介入避险，能保住更多利润。
</div>

<div class="insight">
<strong>📊 重要发现 2：5%-6% 触发 + 4%-5% 解除 是甜蜜点</strong><br>
<ul>
  <li><strong>5%/4%</strong>：4个时段全部第一（近10年 1717% / 近5年 408% / 近3年 294% / 近1年 91%）</li>
  <li><strong>6%/5%</strong>：4个时段全部第二，且熔断事件数更少（85次 vs 89次），更稳定</li>
  <li><strong>8%/7%</strong>：稳健型选项，熔断次数大幅减少（61次），收益仍远超V13</li>
</ul>
</div>

<div class="insight">
<strong>⚠️ 重要发现 3：解除阈值与触发阈值的差值（迟滞带宽）很关键</strong><br>
<ul>
  <li>差值太小（如 5%/2%）：过早解除熔断，没充分避险，收益下降</li>
  <li>差值太大（如 5%/永不）：过度保守，触发后基本回不来</li>
  <li>经验上 <strong>1%-2% 的迟滞带宽</strong> 最佳（即 r = t - 0.01 到 t - 0.02）</li>
</ul>
</div>

<div class="insight">
<strong>💡 操作建议</strong><br>
<ul>
  <li>若追求<strong>极致收益</strong>：<strong>5%/4%</strong>（夏普1.95，回撤-5.01%）</li>
  <li>若追求<strong>收益+稳定</strong>：<strong>6%/5%</strong>（夏普1.80，回撤-5.92%，事件数更少）</li>
  <li>若追求<strong>低频切换</strong>：<strong>8%/7%</strong>（夏普1.51，回撤-7.99%，熔断事件仅61次）</li>
  <li>若<strong>保守</strong>：保留 V13 的 10%/5%（但收益大幅落后）</li>
</ul>
</div>

<div class="narrative">
<strong>注：</strong>所有阈值都基于"<strong>策略自身净值</strong>"的回撤（不是市场回撤），
即"<strong>我们的策略是否在亏钱</strong>"，而非"<strong>市场是否在跌</strong>"。
这是事后才能计算的指标，<strong>实盘中需用滚动最大净值替代</strong>。
</div>

</div>
<script>
""" + JS_SCATTER + JS_NAV + """
</script>
</body>
</html>
"""

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/MA20轮动策略V14回测报告.html', 'w', encoding='utf-8') as f:
    f.write(HTML)

print(f"HTML报告已生成: MA20轮动策略V14回测报告.html")
print(f"文件大小: {len(HTML):,} 字符")
