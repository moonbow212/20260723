# -*- coding: utf-8 -*-
"""生成 V15 (加入3海外指数) vs V14 vs V8 多时段对比 HTML 报告"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v15_periods_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

results = data['results']
names = {int(k): v for k, v in data['names'].items()}
cfg = data['config']
overseas = data['overseas_names']

periods = ['近20年', '近10年', '近5年', '近3年', '近1年']

# 收集各策略数据
v15_totals = [round(results[p]['v15']['total'] * 100, 1) for p in periods]
v14_totals = [round(results[p]['v14']['total'] * 100, 1) for p in periods]
v8_totals = [round(results[p]['v8']['total'] * 100, 1) for p in periods]
v15_anns = [round(results[p]['v15']['ann'] * 100, 1) for p in periods]
v14_anns = [round(results[p]['v14']['ann'] * 100, 1) for p in periods]
v8_anns = [round(results[p]['v8']['ann'] * 100, 1) for p in periods]
v15_mdds = [round(results[p]['v15']['mdd'] * 100, 1) for p in periods]
v14_mdds = [round(results[p]['v14']['mdd'] * 100, 1) for p in periods]
v8_mdds = [round(results[p]['v8']['mdd'] * 100, 1) for p in periods]
v15_sharpes = [round(results[p]['v15']['sharpe'], 2) for p in periods]
v14_sharpes = [round(results[p]['v14']['sharpe'], 2) for p in periods]
v8_sharpes = [round(results[p]['v8']['sharpe'], 2) for p in periods]
v15_cbpct = [round(results[p]['v15']['cb_pct'] * 100, 1) for p in periods]
v14_cbpct = [round(results[p]['v14']['cb_pct'] * 100, 1) for p in periods]
v15_sw = [results[p]['v15']['switches'] for p in periods]
v14_sw = [results[p]['v14']['switches'] for p in periods]

# 持仓占比数据 (V15)
holding_data = {}
for p in periods:
    holding_data[p] = results[p]['hold_v15']

# 主对比表行
table_rows = []
for p in periods:
    r = results[p]
    v15, v14, v8 = r['v15'], r['v14'], r['v8']
    table_rows.append({
        'period': p,
        'span': f"{r['start']} ~ {r['end']}",
        'n_days': r['n_days'],
        'pool_v15': f"{len(r['stock_ids_v15'])}股+债",
        'pool_v14': f"{len(r['stock_ids_v14'])}股+债",
        'v15_total': v15['total'], 'v15_ann': v15['ann'], 'v15_mdd': v15['mdd'],
        'v15_sharpe': v15['sharpe'], 'v15_sw': v15['switches'], 'v15_cbpct': v15['cb_pct'],
        'v15_fee': v15['total_fee'], 'v15_cb_evt': r['cb_v15_count'],
        'v14_total': v14['total'], 'v14_ann': v14['ann'], 'v14_mdd': v14['mdd'],
        'v14_sharpe': v14['sharpe'], 'v14_sw': v14['switches'], 'v14_cbpct': v14['cb_pct'],
        'v14_fee': v14['total_fee'], 'v14_cb_evt': r['cb_v14_count'],
        'v8_total': v8['total'], 'v8_ann': v8['ann'], 'v8_mdd': v8['mdd'],
        'v8_sharpe': v8['sharpe'], 'v8_sw': v8['switches'],
    })

def fmt_pct(x, digits=2):
    return f"{x*100:.{digits}f}%"

# 海外指数持仓占比
overseas_hold = {}
for p in periods:
    overseas_hold[p] = {}
    for name in overseas:
        if name in holding_data[p]:
            overseas_hold[p][name] = holding_data[p][name]['pct']
        else:
            overseas_hold[p][name] = 0.0

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>V15策略多时段对比报告 - 加入3海外指数</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
       background: #f5f6f8; color: #1a1a1a; line-height: 1.6; padding: 20px; }
.container { max-width: 1200px; margin: 0 auto; }
h1 { text-align: center; font-size: 26px; margin: 20px 0 8px; color: #1a1a1a; }
.subtitle { text-align: center; color: #666; font-size: 14px; margin-bottom: 24px; }
.card { background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.card h2 { font-size: 18px; margin-bottom: 16px; color: #1a1a1a; border-left: 4px solid #d6336c; padding-left: 12px; }
.finding { background: #fff5f5; border-left: 4px solid #d6336c; padding: 16px 20px; border-radius: 8px; margin-bottom: 16px; }
.finding.good { background: #f0f9ff; border-left-color: #1971c2; }
.finding.warn { background: #fff9db; border-left-color: #e67700; }
.finding strong { color: #d6336c; }
.finding.good strong { color: #1971c2; }
.finding.warn strong { color: #e67700; }
.overview-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }
.overview-card { background: #fff; border-radius: 8px; padding: 16px 12px; text-align: center;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.06); border-top: 3px solid #d6336c; }
.overview-card .period { font-size: 13px; color: #666; margin-bottom: 8px; }
.overview-card .v15-ret { font-size: 22px; font-weight: 700; color: #d6336c; }
.overview-card .v14-ret { font-size: 14px; color: #888; margin-top: 4px; }
.overview-card .diff { font-size: 12px; margin-top: 4px; }
.diff.pos { color: #d6336c; }
.diff.neg { color: #1971c2; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 6px; text-align: center; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: 600; color: #495057; position: sticky; top: 0; }
td.period { font-weight: 600; text-align: left; }
.pos { color: #d6336c; font-weight: 600; }
.neg { color: #2b8a3e; font-weight: 600; }
.chart-box { height: 380px; margin: 16px 0; }
.note { background: #f8f9fa; border-radius: 8px; padding: 16px 20px; font-size: 13px; color: #555; margin-top: 12px; line-height: 1.8; }
.note b { color: #1a1a1a; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge.new { background: #fff0f6; color: #d6336c; border: 1px solid #ffdeeb; }
.badge.win { background: #e6fcf5; color: #0ca678; }
.badge.lose { background: #fff5f5; color: #c92a2a; }
</style>
</head>
<body>
<div class="container">
<h1>V15 策略多时段对比报告</h1>
<p class="subtitle">加入日经225 / 越南胡志明 / 英国富时100 三个海外指数后的收益对比 · 5%/4%阈值</p>

<div class="card">
  <h2>核心发现：加入海外指数反而降低收益 <span class="badge lose">反直觉</span></h2>
  <div class="finding">
    <strong>5个时段中4个收益下降，仅近1年略升。</strong>V15(11股+债) 相比 V14(8股+债)：
    <ul style="margin: 8px 0 0 20px;">
      <li><strong>近20年</strong>：43166% → 9115%，<span class="neg">下降34051pp</span> ❌</li>
      <li><strong>近10年</strong>：1697% → 653%，<span class="neg">下降1043pp</span> ❌</li>
      <li><strong>近5年</strong>：407% → 200%，<span class="neg">下降206pp</span> ❌</li>
      <li><strong>近3年</strong>：294% → 231%，<span class="neg">下降63pp</span> ❌</li>
      <li><strong>近1年</strong>：95.7% → 111.1%，<span class="pos">上升15pp</span> ✅</li>
    </ul>
  </div>
  <div class="finding warn">
    <strong>根本原因：海外指数改变了V8基线净值走势，导致熔断触发/解除时点改变。</strong>
    加入海外指数后，原始信号选中的标的不同，V15基线净值的高点和回撤路径与V14不同。
    熔断天数占比普遍升高（近20年 90.5% vs 75.1%，近5年 89.7% vs 72.1%），
    意味着V15更多时间在避险，错过更多行情。而海外指数实际被选中的天数很少（占比多<5%），属于"赔了夫人又折兵"。
  </div>
</div>

<div class="overview-grid">
'''

# 概览卡片
for i, p in enumerate(periods):
    diff = v15_totals[i] - v14_totals[i]
    diff_class = "pos" if diff > 0 else "neg"
    arrow = "↑" if diff > 0 else "↓"
    html += f'''  <div class="overview-card">
    <div class="period">{p}</div>
    <div class="v15-ret">{v15_totals[i]:.1f}%</div>
    <div class="v14-ret">V14: {v14_totals[i]:.1f}%</div>
    <div class="diff {diff_class}">{arrow} {abs(diff):.1f}pp</div>
  </div>
'''

html += '''</div>

<div class="card">
  <h2>V15 vs V14 vs V8 完整对比表</h2>
  <table>
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th rowspan="2">标的池</th>
        <th colspan="4">V15 (含3海外指数)</th>
        <th colspan="4">V14 (原8股+债)</th>
        <th colspan="2">V8基线</th>
      </tr>
      <tr>
        <th>总收益</th><th>年化</th><th>夏普</th><th>熔断天%</th>
        <th>总收益</th><th>年化</th><th>夏普</th><th>熔断天%</th>
        <th>总收益</th><th>回撤</th>
      </tr>
    </thead>
    <tbody>
'''

for r in table_rows:
    html += f'''      <tr>
        <td class="period">{r['period']}</td>
        <td>V15:{r['pool_v15']}<br>V14:{r['pool_v14']}</td>
        <td class="pos">{fmt_pct(r['v15_total'])}</td>
        <td>{fmt_pct(r['v15_ann'])}</td>
        <td>{r['v15_sharpe']:.2f}</td>
        <td>{r['v15_cbpct']*100:.1f}%</td>
        <td class="pos">{fmt_pct(r['v14_total'])}</td>
        <td>{fmt_pct(r['v14_ann'])}</td>
        <td>{r['v14_sharpe']:.2f}</td>
        <td>{r['v14_cbpct']*100:.1f}%</td>
        <td>{fmt_pct(r['v8_total'])}</td>
        <td class="neg">{fmt_pct(r['v8_mdd'])}</td>
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
  <h2>最大回撤对比</h2>
  <div class="chart-box"><canvas id="chartMdd"></canvas></div>
</div>

<div class="card">
  <h2>熔断天数占比对比 <span class="badge new">关键</span></h2>
  <div class="chart-box"><canvas id="chartCb"></canvas></div>
  <div class="finding warn">
    <strong>V15熔断天数普遍高于V14</strong>，说明加入海外指数后基线净值回撤更频繁/更深，导致更多时间在避险。
    这是V15收益下降的直接原因——不是海外指数本身亏钱，而是它们的存在扰动了熔断机制的工作节奏。
  </div>
</div>

<div class="card">
  <h2>切换次数对比</h2>
  <div class="chart-box"><canvas id="chartSw"></canvas></div>
</div>

<div class="card">
  <h2>海外指数实际持仓占比 <span class="badge new">新增</span></h2>
  <table>
    <thead>
      <tr><th>时段</th><th>日经225</th><th>越南胡志明</th><th>英国富时100</th><th>三者合计</th></tr>
    </thead>
    <tbody>
'''

for p in periods:
    nk = overseas_hold[p].get('日经225', 0)
    vn = overseas_hold[p].get('越南胡志明', 0)
    ft = overseas_hold[p].get('英国富时100', 0)
    total = nk + vn + ft
    html += f'''      <tr>
        <td class="period">{p}</td>
        <td>{nk:.1f}%</td>
        <td>{vn:.1f}%</td>
        <td>{ft:.1f}%</td>
        <td class="pos">{total:.1f}%</td>
      </tr>
'''

html += '''    </tbody>
  </table>
  <div class="finding">
    <strong>海外指数被选中的天数极少。</strong>近20年三者合计仅3.1%，近5年合计2.2%，近1年几乎为0。
    但即便占比这么低，它们的存在仍通过改变选股逻辑和熔断节奏，显著拉低了整体收益。这说明"标的池越大越好"是错误的直觉。
  </div>
</div>

<div class="card">
  <h2>V15 各标的完整持仓占比</h2>
'''

for p in periods:
    hold = holding_data[p]
    html += f'  <h3 style="margin: 16px 0 8px; font-size: 15px; color: #495057;">{p}</h3>\n  <table>\n    <thead><tr><th>标的</th><th>天数</th><th>占比</th></tr></thead>\n    <tbody>\n'
    for name, d in sorted(hold.items(), key=lambda x: -x[1]['pct']):
        is_overseas = name in overseas
        badge = ' <span class="badge new">海外</span>' if is_overseas else ''
        html += f'      <tr><td>{name}{badge}</td><td>{d["days"]}</td><td>{d["pct"]:.1f}%</td></tr>\n'
    html += '    </tbody>\n  </table>\n'

html += '''</div>

<div class="card">
  <h2>V15 vs V14 提升幅度明细</h2>
  <table>
    <thead>
      <tr><th>时段</th><th>V15总收益</th><th>V14总收益</th><th>收益差</th><th>V15年化</th><th>V14年化</th><th>年化差</th><th>V15夏普</th><th>V14夏普</th><th>结论</th></tr>
    </thead>
    <tbody>
'''

for i, p in enumerate(periods):
    r = table_rows[i]
    diff_total = (r['v15_total'] - r['v14_total']) * 100
    diff_ann = (r['v15_ann'] - r['v14_ann']) * 100
    verdict = '<span class="badge win">V15胜</span>' if diff_total > 0 else '<span class="badge lose">V14胜</span>'
    html += f'''      <tr>
        <td class="period">{p}</td>
        <td class="pos">{r['v15_total']*100:.2f}%</td>
        <td class="pos">{r['v14_total']*100:.2f}%</td>
        <td class="{'pos' if diff_total>0 else 'neg'}">{diff_total:+.2f}pp</td>
        <td>{r['v15_ann']*100:.2f}%</td>
        <td>{r['v14_ann']*100:.2f}%</td>
        <td class="{'pos' if diff_ann>0 else 'neg'}">{diff_ann:+.2f}pp</td>
        <td>{r['v15_sharpe']:.2f}</td>
        <td>{r['v14_sharpe']:.2f}</td>
        <td>{verdict}</td>
      </tr>
'''

html += '''    </tbody>
  </table>
</div>

<div class="card">
  <h2>结论与建议</h2>
  <div class="finding warn">
    <strong>不建议加入这3个海外指数。</strong>原因：
    <ol style="margin: 8px 0 0 20px;">
      <li><strong>收益全面下降</strong>：5个时段中4个明显下降，近20年降幅达34051pp</li>
      <li><strong>海外指数很少被选中</strong>：持仓占比多<5%，贡献极小</li>
      <li><strong>扰动熔断机制</strong>：熔断天数升高，错过更多行情</li>
      <li><strong>交易日历不一致</strong>：海外指数在A股非交易日缺失，数据对齐存在偏差</li>
    </ol>
  </div>
  <div class="finding good">
    <strong>唯一亮点：近1年V15略优</strong>（111% vs 96%，+15pp），因为近1年越南胡志明在少数时段被选中且表现尚可。
    但样本太小，不足以推翻整体结论。
  </div>
  <div class="note">
    <b>方法论说明</b>：<br>
    ① <b>V15标的池</b>：原8股(上证50/创业板50/纳指100/沪深300/中证500/中证1000/标普500/科创50) + 日经225/越南胡志明/英国富时100 + 国债 = 11股+债<br>
    ② <b>V14标的池</b>：原8股 + 国债 = 8股+债（对照组）<br>
    ③ <b>海外指数处理</b>：各按自己交易日历算MA20/bf，left join到主日历(原8股inner join)，缺失日bf=NaN不参与选股<br>
    ④ <b>近20年/10年</b>因部分原标的无全程数据，标的池较小：近20年V15=7股+债、V14=4股+债；近10年V15=10股+债、V14=7股+债<br>
    ⑤ <b>富时100</b>只到2026-04-17，之后自动排除<br>
    ⑥ 5%/4%熔断阈值、万分之二手续费、T日收盘信号T+1日开盘执行（同V14）
  </div>
</div>

</div>

<script>
const periods = ''' + json.dumps(periods, ensure_ascii=False) + ''';
const v15Totals = ''' + json.dumps(v15_totals) + ''';
const v14Totals = ''' + json.dumps(v14_totals) + ''';
const v8Totals = ''' + json.dumps(v8_totals) + ''';
const v15Anns = ''' + json.dumps(v15_anns) + ''';
const v14Anns = ''' + json.dumps(v14_anns) + ''';
const v8Anns = ''' + json.dumps(v8_anns) + ''';
const v15Mdds = ''' + json.dumps(v15_mdds) + ''';
const v14Mdds = ''' + json.dumps(v14_mdds) + ''';
const v8Mdds = ''' + json.dumps(v8_mdds) + ''';
const v15Sharpes = ''' + json.dumps(v15_sharpes) + ''';
const v14Sharpes = ''' + json.dumps(v14_sharpes) + ''';
const v8Sharpes = ''' + json.dumps(v8_sharpes) + ''';
const v15Cb = ''' + json.dumps(v15_cbpct) + ''';
const v14Cb = ''' + json.dumps(v14_cbpct) + ''';
const v15Sw = ''' + json.dumps(v15_sw) + ''';
const v14Sw = ''' + json.dumps(v14_sw) + ''';

Chart.defaults.font.family = '-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif';
Chart.defaults.font.size = 12;

const colors = {
  v15: '#d6336c', v14: '#1971c2', v8: '#868e96'
};

function mkBar(id, title, v15, v14, v8, fmt) {
  new Chart(document.getElementById(id), {
    type: 'bar',
    data: {
      labels: periods,
      datasets: [
        {label:'V15(含海外)', data:v15, backgroundColor:colors.v15, borderColor:colors.v15, borderWidth:1},
        {label:'V14(原8股)', data:v14, backgroundColor:colors.v14, borderColor:colors.v14, borderWidth:1},
        {label:'V8基线', data:v8, backgroundColor:colors.v8, borderColor:colors.v8, borderWidth:1},
      ]
    },
    options: {
      responsive:true, maintainAspectRatio:false,
      plugins:{title:{display:true,text:title,font:{size:14}},legend:{position:'top'}},
      scales:{y:{beginAtZero:false,callbacks:fmt}}
    }
  });
}

mkBar('chartTotal', '总收益对比 (%)', v15Totals, v14Totals, v8Totals,
  {label:(c)=>c.value.toFixed(1)+'%'});
mkBar('chartAnn', '年化收益对比 (%)', v15Anns, v14Anns, v8Anns,
  {label:(c)=>c.value.toFixed(1)+'%'});

new Chart(document.getElementById('chartMdd'), {
  type:'bar',
  data:{labels:periods, datasets:[
    {label:'V15(含海外)', data:v15Mdds, backgroundColor:colors.v15},
    {label:'V14(原8股)', data:v14Mdds, backgroundColor:colors.v14},
    {label:'V8基线', data:v8Mdds, backgroundColor:colors.v8},
  ]},
  options:{responsive:true,maintainAspectRatio:false,
    plugins:{title:{display:true,text:'最大回撤对比 (%)',font:{size:14}},legend:{position:'top'}},
    scales:{y:{beginAtZero:false}}}
});

new Chart(document.getElementById('chartCb'), {
  type:'bar',
  data:{labels:periods, datasets:[
    {label:'V15(含海外)', data:v15Cb, backgroundColor:colors.v15},
    {label:'V14(原8股)', data:v14Cb, backgroundColor:colors.v14},
  ]},
  options:{responsive:true,maintainAspectRatio:false,
    plugins:{title:{display:true,text:'熔断天数占比 (%)',font:{size:14}},legend:{position:'top'}},
    scales:{y:{beginAtZero:true,max:100}}}
});

new Chart(document.getElementById('chartSw'), {
  type:'bar',
  data:{labels:periods, datasets:[
    {label:'V15(含海外)', data:v15Sw, backgroundColor:colors.v15},
    {label:'V14(原8股)', data:v14Sw, backgroundColor:colors.v14},
  ]},
  options:{responsive:true,maintainAspectRatio:false,
    plugins:{title:{display:true,text:'切换次数对比',font:{size:14}},legend:{position:'top'}},
    scales:{y:{beginAtZero:true}}}
});
</script>
</body>
</html>'''

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/V15策略多时段对比报告.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("报告已生成: V15策略多时段对比报告.html")
