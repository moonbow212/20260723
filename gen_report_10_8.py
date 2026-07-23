# -*- coding: utf-8 -*-
"""生成 10%/8% vs 5%/4% 阈值对比 HTML 报告"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/threshold_10_8_vs_5_4.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

results = data['results']
names = {int(k): v for k, v in data['names'].items()}

periods = ['近20年', '近10年', '近5年', '近3年', '近1年']

# 收集数据
m108_totals = [round(results[p]['10_8']['total'] * 100, 1) for p in periods]
m54_totals = [round(results[p]['5_4']['total'] * 100, 1) for p in periods]
v8_totals = [round(results[p]['v8']['total'] * 100, 1) for p in periods]
m108_anns = [round(results[p]['10_8']['ann'] * 100, 1) for p in periods]
m54_anns = [round(results[p]['5_4']['ann'] * 100, 1) for p in periods]
m108_mdds = [round(results[p]['10_8']['mdd'] * 100, 1) for p in periods]
m54_mdds = [round(results[p]['5_4']['mdd'] * 100, 1) for p in periods]
v8_mdds = [round(results[p]['v8']['mdd'] * 100, 1) for p in periods]
m108_sharpes = [round(results[p]['10_8']['sharpe'], 2) for p in periods]
m54_sharpes = [round(results[p]['5_4']['sharpe'], 2) for p in periods]
m108_cbpct = [round(results[p]['10_8']['cb_pct'] * 100, 1) for p in periods]
m54_cbpct = [round(results[p]['5_4']['cb_pct'] * 100, 1) for p in periods]
m108_sw = [results[p]['10_8']['switches'] for p in periods]
m54_sw = [results[p]['5_4']['switches'] for p in periods]

def fmt_pct(x, digits=2):
    return f"{x*100:.{digits}f}%"

# 表格行
table_rows = []
for p in periods:
    r = results[p]
    m108, m54, v8 = r['10_8'], r['5_4'], r['v8']
    table_rows.append({
        'period': p, 'span': f"{r['start']} ~ {r['end']}", 'n_days': r['n_days'],
        'stocks': ' + '.join(r['stock_names']) + ' + 国债',
        'm108_total': m108['total'], 'm108_ann': m108['ann'], 'm108_mdd': m108['mdd'],
        'm108_sharpe': m108['sharpe'], 'm108_sw': m108['switches'], 'm108_cbpct': m108['cb_pct'],
        'm108_fee': m108['total_fee'], 'm108_evt': r['cb_count_10_8'],
        'm54_total': m54['total'], 'm54_ann': m54['ann'], 'm54_mdd': m54['mdd'],
        'm54_sharpe': m54['sharpe'], 'm54_sw': m54['switches'], 'm54_cbpct': m54['cb_pct'],
        'm54_fee': m54['total_fee'], 'm54_evt': r['cb_count_5_4'],
        'v8_total': v8['total'], 'v8_mdd': v8['mdd'],
    })

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>10%/8% vs 5%/4% 阈值对比报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
       background: #f5f6f8; color: #1a1a1a; line-height: 1.6; padding: 20px; }
.container { max-width: 1200px; margin: 0 auto; }
h1 { text-align: center; font-size: 26px; margin: 20px 0 8px; }
.subtitle { text-align: center; color: #666; font-size: 14px; margin-bottom: 24px; }
.card { background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.card h2 { font-size: 18px; margin-bottom: 16px; border-left: 4px solid #d6336c; padding-left: 12px; }
.finding { background: #fff5f5; border-left: 4px solid #d6336c; padding: 16px 20px; border-radius: 8px; margin-bottom: 16px; }
.finding.good { background: #f0f9ff; border-left-color: #1971c2; }
.finding.warn { background: #fff9db; border-left-color: #e67700; }
.overview-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }
.overview-card { background: #fff; border-radius: 8px; padding: 16px 12px; text-align: center;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.06); border-top: 3px solid #e8590c; }
.overview-card .period { font-size: 13px; color: #666; margin-bottom: 8px; }
.overview-card .m108-ret { font-size: 20px; font-weight: 700; color: #e8590c; }
.overview-card .m54-ret { font-size: 14px; color: #888; margin-top: 4px; }
.overview-card .diff { font-size: 12px; margin-top: 4px; color: #c92a2a; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 6px; text-align: center; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: 600; color: #495057; }
td.period { font-weight: 600; text-align: left; }
.pos { color: #d6336c; font-weight: 600; }
.neg { color: #2b8a3e; font-weight: 600; }
.worse { color: #c92a2a; }
.better { color: #0ca678; }
.chart-box { height: 380px; margin: 16px 0; }
.note { background: #f8f9fa; border-radius: 8px; padding: 16px 20px; font-size: 13px; color: #555; margin-top: 12px; line-height: 1.8; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge.lose { background: #fff5f5; color: #c92a2a; }
.badge.win { background: #e6fcf5; color: #0ca678; }
</style>
</head>
<body>
<div class="container">
<h1>10%/8% vs 5%/4% 阈值对比报告</h1>
<p class="subtitle">V14策略(8股+国债)基础上，熔断阈值从5%/4%改为10%/8%的效果 · 多时段回测</p>

<div class="card">
  <h2>核心结论：10%/8% 全面落后于 5%/4% <span class="badge lose">全面劣势</span></h2>
  <div class="finding">
    <strong>5个时段的收益和回撤全部更差。</strong>10%/8% 相比 5%/4%：
    <ul style="margin: 8px 0 0 20px;">
      <li><strong>近20年</strong>：13762% vs 43166%，收益少29403pp；回撤 -10.11% vs -5.42%</li>
      <li><strong>近10年</strong>：716% vs 1697%，收益少981pp；回撤 -10.73% vs -5.01%</li>
      <li><strong>近5年</strong>：170% vs 407%，收益少236pp；回撤 -10.88% vs -4.86%</li>
      <li><strong>近3年</strong>：147% vs 294%，收益少147pp；回撤 -10.88% vs -4.86%</li>
      <li><strong>近1年</strong>：25% vs 95%，收益少70pp；回撤 -10.88% vs -4.05%</li>
    </ul>
  </div>
  <div class="finding warn">
    <strong>根本原因：触发阈值直接决定最大回撤上限。</strong>
    10%/8%的回撤全部被钉在-10%~-11%（因为要跌10%才触发），而5%/4%的回撤都在-4%~-5.5%（跌5%就触发）。
    虽然10%/8%熔断天数更少（54-61% vs 63-80%），看似"更少干预"，但每次干预前已经亏了更多，且解除阈值8%太高导致恢复信号更晚，错过反弹初段。
  </div>
</div>

<div class="overview-grid">
'''

for i, p in enumerate(periods):
    diff = m108_totals[i] - m54_totals[i]
    html += f'''  <div class="overview-card">
    <div class="period">{p}</div>
    <div class="m108-ret">{m108_totals[i]:.1f}%</div>
    <div class="m54-ret">5%/4%: {m54_totals[i]:.1f}%</div>
    <div class="diff">↓ {abs(diff):.1f}pp</div>
  </div>
'''

html += '''</div>

<div class="card">
  <h2>完整对比表</h2>
  <table>
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th colspan="5">10%/8% (新)</th>
        <th colspan="5">5%/4% (V14最佳)</th>
        <th colspan="2">V8基线</th>
      </tr>
      <tr>
        <th>总收益</th><th>年化</th><th>夏普</th><th>回撤</th><th>熔断天%</th>
        <th>总收益</th><th>年化</th><th>夏普</th><th>回撤</th><th>熔断天%</th>
        <th>总收益</th><th>回撤</th>
      </tr>
    </thead>
    <tbody>
'''

for r in table_rows:
    html += f'''      <tr>
        <td class="period">{r['period']}</td>
        <td class="pos">{fmt_pct(r['m108_total'])}</td>
        <td>{fmt_pct(r['m108_ann'])}</td>
        <td>{r['m108_sharpe']:.2f}</td>
        <td class="worse">{fmt_pct(r['m108_mdd'])}</td>
        <td>{r['m108_cbpct']*100:.1f}%</td>
        <td class="pos">{fmt_pct(r['m54_total'])}</td>
        <td>{fmt_pct(r['m54_ann'])}</td>
        <td>{r['m54_sharpe']:.2f}</td>
        <td class="better">{fmt_pct(r['m54_mdd'])}</td>
        <td>{r['m54_cbpct']*100:.1f}%</td>
        <td>{fmt_pct(r['v8_total'])}</td>
        <td class="worse">{fmt_pct(r['v8_mdd'])}</td>
      </tr>
'''

html += '''    </tbody>
  </table>
</div>

<div class="card">
  <h2>总收益对比 (对数刻度)</h2>
  <div class="chart-box"><canvas id="chartTotal"></canvas></div>
</div>

<div class="card">
  <h2>年化收益对比</h2>
  <div class="chart-box"><canvas id="chartAnn"></canvas></div>
</div>

<div class="card">
  <h2>最大回撤对比 <span class="badge lose">关键差异</span></h2>
  <div class="chart-box"><canvas id="chartMdd"></canvas></div>
  <div class="finding">
    <strong>10%/8%的回撤全部在-10%~-11%，5%/4%全部在-4%~-5.5%。</strong>
    这不是巧合——触发阈值就是回撤的"天花板"。10%阈值意味着允许跌10%才动手，5%阈值意味着跌5%就动手。
    回撤控制是熔断机制的核心价值，10%/8%在这个维度上完败。
  </div>
</div>

<div class="card">
  <h2>夏普比率对比</h2>
  <div class="chart-box"><canvas id="chartSharpe"></canvas></div>
</div>

<div class="card">
  <h2>熔断天数占比对比</h2>
  <div class="chart-box"><canvas id="chartCb"></canvas></div>
  <div class="finding warn">
    <strong>10%/8%熔断天数更少（54-61%），但收益反而更低。</strong>
    这说明"少干预"不等于"好结果"。10%/8%虽然更多时间在持仓股票，但每次熔断前已经亏了10%（vs 5%/4%的5%），
    且解除阈值8%太高，回撤修复到-8%才恢复信号，错过了-8%~-5%这段反弹。
  </div>
</div>

<div class="card">
  <h2>切换次数对比</h2>
  <div class="chart-box"><canvas id="chartSw"></canvas></div>
  <div class="finding warn">
    <strong>10%/8%切换次数普遍更多</strong>（近20年405次 vs 247次，近1年28次 vs 20次）。
    虽然迟滞带宽更大（2% vs 1%），但熔断天数少意味着更多时间在持仓股票，而持仓期间每天都要选bf最高的标的，导致轮动切换更频繁。
  </div>
</div>

<div class="card">
  <h2>10%/8% vs 5%/4% 提升幅度明细</h2>
  <table>
    <thead>
      <tr><th>时段</th><th>10/8总收益</th><th>5/4总收益</th><th>收益差</th><th>10/8年化</th><th>5/4年化</th><th>年化差</th><th>10/8回撤</th><th>5/4回撤</th><th>10/8夏普</th><th>5/4夏普</th><th>结论</th></tr>
    </thead>
    <tbody>
'''

for i, p in enumerate(periods):
    r = table_rows[i]
    diff_total = (r['m108_total'] - r['m54_total']) * 100
    diff_ann = (r['m108_ann'] - r['m54_ann']) * 100
    html += f'''      <tr>
        <td class="period">{p}</td>
        <td class="pos">{r['m108_total']*100:.2f}%</td>
        <td class="pos">{r['m54_total']*100:.2f}%</td>
        <td class="worse">{diff_total:+.2f}pp</td>
        <td>{r['m108_ann']*100:.2f}%</td>
        <td>{r['m54_ann']*100:.2f}%</td>
        <td class="worse">{diff_ann:+.2f}pp</td>
        <td class="worse">{r['m108_mdd']*100:.2f}%</td>
        <td class="better">{r['m54_mdd']*100:.2f}%</td>
        <td>{r['m108_sharpe']:.2f}</td>
        <td>{r['m54_sharpe']:.2f}</td>
        <td><span class="badge lose">5/4胜</span></td>
      </tr>
'''

html += '''    </tbody>
  </table>
</div>

<div class="card">
  <h2>10%/8% 持仓占比</h2>
'''

for p in periods:
    hold = results[p]['hold_10_8']
    html += f'  <h3 style="margin: 16px 0 8px; font-size: 15px; color: #495057;">{p}</h3>\n  <table>\n    <thead><tr><th>标的</th><th>天数</th><th>占比</th></tr></thead>\n    <tbody>\n'
    for name, d in sorted(hold.items(), key=lambda x: -x[1]['pct']):
        html += f'      <tr><td>{name}</td><td>{d["days"]}</td><td>{d["pct"]:.1f}%</td></tr>\n'
    html += '    </tbody>\n  </table>\n'

html += '''</div>

<div class="card">
  <h2>结论</h2>
  <div class="finding">
    <strong>10%/8% 不如 5%/4%，不建议采用。</strong>
    <ol style="margin: 8px 0 0 20px;">
      <li><strong>收益全面落后</strong>：5个时段总收益全部更低，近20年少29403pp</li>
      <li><strong>回撤全面更大</strong>：5个时段回撤全部在-10%~-11%，远差于5%/4%的-4%~-5.5%</li>
      <li><strong>夏普全面更低</strong>：风险调整后收益也更差</li>
      <li><strong>切换次数更多</strong>：手续费成本更高（近20年16.18% vs 9.86%）</li>
    </ol>
  </div>
  <div class="finding good">
    <strong>但仍优于V8基线。</strong>10%/8%近20年13762% vs V8的5914%，近1年25% vs 23%。
    说明任何熔断机制都比没有好，只是5%/4%比10%/8%好得多。
  </div>
  <div class="note">
    <b>阈值选择的核心规律</b>：<br>
    ① <b>触发阈值 = 回撤天花板</b>：5%触发→回撤上限约-5%，10%触发→回撤上限约-10%<br>
    ② <b>解除阈值 = 反弹捕获</b>：4%解除→回撤修复到-4%就恢复信号，8%解除→要修复到-8%才恢复，错过-8%~-4%的反弹<br>
    ③ <b>5%/4%是甜蜜点</b>：紧触发+紧解除，回撤小且能及时捕捉反弹，虽有1%迟滞带宽防whipsaw但不过度保守<br>
    ④ <b>10%/8%太松</b>：允许跌10%才动手已经太晚，且8%解除门槛让恢复信号过迟<br>
    ⑤ <b>方法论</b>：V8原始信号→算raw_nav→cummax→raw_dd→熔断判断，同V14；仅阈值参数不同
  </div>
</div>

</div>

<script>
const periods = ''' + json.dumps(periods, ensure_ascii=False) + ''';
const m108Totals = ''' + json.dumps(m108_totals) + ''';
const m54Totals = ''' + json.dumps(m54_totals) + ''';
const v8Totals = ''' + json.dumps(v8_totals) + ''';
const m108Anns = ''' + json.dumps(m108_anns) + ''';
const m54Anns = ''' + json.dumps(m54_anns) + ''';
const m108Mdds = ''' + json.dumps(m108_mdds) + ''';
const m54Mdds = ''' + json.dumps(m54_mdds) + ''';
const v8Mdds = ''' + json.dumps(v8_mdds) + ''';
const m108Sharpes = ''' + json.dumps(m108_sharpes) + ''';
const m54Sharpes = ''' + json.dumps(m54_sharpes) + ''';
const m108Cb = ''' + json.dumps(m108_cbpct) + ''';
const m54Cb = ''' + json.dumps(m54_cbpct) + ''';
const m108Sw = ''' + json.dumps(m108_sw) + ''';
const m54Sw = ''' + json.dumps(m54_sw) + ''';

Chart.defaults.font.family = '-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif';
Chart.defaults.font.size = 12;

const c108 = '#e8590c', c54 = '#1971c2', cv8 = '#868e96';

new Chart(document.getElementById('chartTotal'), {
  type:'bar',
  data:{labels:periods, datasets:[
    {label:'10%/8%', data:m108Totals, backgroundColor:c108},
    {label:'5%/4%', data:m54Totals, backgroundColor:c54},
    {label:'V8基线', data:v8Totals, backgroundColor:cv8},
  ]},
  options:{responsive:true,maintainAspectRatio:false,
    plugins:{title:{display:true,text:'总收益对比 (%)',font:{size:14}},legend:{position:'top'}},
    scales:{y:{type:'logarithmic'}}}
});

new Chart(document.getElementById('chartAnn'), {
  type:'bar',
  data:{labels:periods, datasets:[
    {label:'10%/8%', data:m108Anns, backgroundColor:c108},
    {label:'5%/4%', data:m54Anns, backgroundColor:c54},
  ]},
  options:{responsive:true,maintainAspectRatio:false,
    plugins:{title:{display:true,text:'年化收益对比 (%)',font:{size:14}},legend:{position:'top'}},
    scales:{y:{beginAtZero:true}}}
});

new Chart(document.getElementById('chartMdd'), {
  type:'bar',
  data:{labels:periods, datasets:[
    {label:'10%/8%', data:m108Mdds, backgroundColor:c108},
    {label:'5%/4%', data:m54Mdds, backgroundColor:c54},
    {label:'V8基线', data:v8Mdds, backgroundColor:cv8},
  ]},
  options:{responsive:true,maintainAspectRatio:false,
    plugins:{title:{display:true,text:'最大回撤对比 (%)',font:{size:14}},legend:{position:'top'}},
    scales:{y:{beginAtZero:false}}}
});

new Chart(document.getElementById('chartSharpe'), {
  type:'bar',
  data:{labels:periods, datasets:[
    {label:'10%/8%', data:m108Sharpes, backgroundColor:c108},
    {label:'5%/4%', data:m54Sharpes, backgroundColor:c54},
  ]},
  options:{responsive:true,maintainAspectRatio:false,
    plugins:{title:{display:true,text:'夏普比率对比',font:{size:14}},legend:{position:'top'}},
    scales:{y:{beginAtZero:true}}}
});

new Chart(document.getElementById('chartCb'), {
  type:'bar',
  data:{labels:periods, datasets:[
    {label:'10%/8%', data:m108Cb, backgroundColor:c108},
    {label:'5%/4%', data:m54Cb, backgroundColor:c54},
  ]},
  options:{responsive:true,maintainAspectRatio:false,
    plugins:{title:{display:true,text:'熔断天数占比 (%)',font:{size:14}},legend:{position:'top'}},
    scales:{y:{beginAtZero:true,max:100}}}
});

new Chart(document.getElementById('chartSw'), {
  type:'bar',
  data:{labels:periods, datasets:[
    {label:'10%/8%', data:m108Sw, backgroundColor:c108},
    {label:'5%/4%', data:m54Sw, backgroundColor:c54},
  ]},
  options:{responsive:true,maintainAspectRatio:false,
    plugins:{title:{display:true,text:'切换次数对比',font:{size:14}},legend:{position:'top'}},
    scales:{y:{beginAtZero:true}}}
});
</script>
</body>
</html>'''

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/10_8_vs_5_4阈值对比报告.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("报告已生成: 10_8_vs_5_4阈值对比报告.html")
