# -*- coding: utf-8 -*-
"""生成 V14 (5%/4%) 多时段收益对比 HTML 报告"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_periods_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

results = data['results']
names = data['names']
cfg = data['config']

# 时段顺序
periods = ['近20年', '近10年', '近5年', '近3年', '近1年']

# 主对比表数据
table_rows = []
for p in periods:
    r = results[p]
    v14 = r['v14']
    v8 = r['v8']
    table_rows.append({
        'period': p,
        'span': f"{r['start']} ~ {r['end']}",
        'n_days': r['n_days'],
        'stocks': ' + '.join(r['stock_names']) + ' + 国债',
        'v14_total': v14['total'],
        'v14_ann': v14['ann'],
        'v14_mdd': v14['mdd'],
        'v14_sharpe': v14['sharpe'],
        'v14_vol': v14['ann_vol'],
        'v14_sw': v14['switches'],
        'v14_cbpct': v14['cb_pct'],
        'v14_fee': v14['total_fee'],
        'v14_evt': len(v14['cb_events']),
        'v8_total': v8['total'],
        'v8_ann': v8['ann'],
        'v8_mdd': v8['mdd'],
        'v8_sharpe': v8['sharpe'],
        'v8_sw': v8['switches'],
    })

# Chart.js 数据
labels = periods
v14_totals = [round(results[p]['v14']['total'] * 100, 1) for p in periods]
v8_totals = [round(results[p]['v8']['total'] * 100, 1) for p in periods]
v14_anns = [round(results[p]['v14']['ann'] * 100, 1) for p in periods]
v8_anns = [round(results[p]['v8']['ann'] * 100, 1) for p in periods]
v14_mdds = [round(results[p]['v14']['mdd'] * 100, 1) for p in periods]
v8_mdds = [round(results[p]['v8']['mdd'] * 100, 1) for p in periods]
v14_sharpes = [round(results[p]['v14']['sharpe'], 2) for p in periods]
v8_sharpes = [round(results[p]['v8']['sharpe'], 2) for p in periods]
bh_cols = []
for p in periods:
    r = results[p]
    bh_cols.append({names[str(i)]: r['bh'][str(i)] * 100 for i in [1,2,3,4,5,6,7,8,9] if str(i) in r['bh']})

# 表格行 HTML
def fmt_pct(x, digits=2):
    return f"{x*100:.{digits}f}%"

table_html = ""
for row in table_rows:
    # V14行
    table_html += "<tr class='v14-row'>"
    table_html += f"<td rowspan='2' class='period-cell'>{row['period']}<br><span class='date-span'>{row['span']}</span><br><span class='days'>{row['n_days']}天</span></td>"
    table_html += f"<td rowspan='2' class='stocks-cell'>{row['stocks']}</td>"
    table_html += f"<td class='hl'>V14(5/4)</td>"
    table_html += f"<td class='hl'>{fmt_pct(row['v14_total'])}</td>"
    table_html += f"<td class='hl'>{fmt_pct(row['v14_ann'])}</td>"
    table_html += f"<td class='hl'>{fmt_pct(row['v14_mdd'])}</td>"
    table_html += f"<td class='hl'>{row['v14_sharpe']:.2f}</td>"
    table_html += f"<td>{fmt_pct(row['v14_vol'])}</td>"
    table_html += f"<td>{row['v14_sw']}</td>"
    table_html += f"<td>{fmt_pct(row['v14_cbpct'],1)}</td>"
    table_html += f"<td>{fmt_pct(row['v14_fee'])}</td>"
    table_html += f"<td>{row['v14_evt']}</td>"
    table_html += "</tr>"
    # V8行
    table_html += "<tr class='v8-row'>"
    table_html += f"<td>V8基线</td>"
    table_html += f"<td>{fmt_pct(row['v8_total'])}</td>"
    table_html += f"<td>{fmt_pct(row['v8_ann'])}</td>"
    table_html += f"<td>{fmt_pct(row['v8_mdd'])}</td>"
    table_html += f"<td>{row['v8_sharpe']:.2f}</td>"
    table_html += f"<td>-</td>"
    table_html += f"<td>{row['v8_sw']}</td>"
    table_html += f"<td>-</td>"
    table_html += f"<td>-</td>"
    table_html += f"<td>-</td>"
    table_html += "</tr>"

# 买入持有表
bh_table = ""
bh_all_ids = [1,2,3,4,5,6,7,8,9]
for p in periods:
    r = results[p]
    bh_table += f"<tr><td class='period-cell'>{p}</td>"
    for i in bh_all_ids:
        k = str(i)
        if k in r['bh']:
            v = r['bh'][k] * 100
            cls = 'pos' if v >= 0 else 'neg'
            bh_table += f"<td class='{cls}'>{v:.2f}%</td>"
        else:
            bh_table += "<td class='na'>--</td>"
    bh_table += "</tr>"

# 倍数对比
mult_rows = ""
for row in table_rows:
    mult = row['v14_total'] / row['v8_total'] if row['v8_total'] > 0 else 0
    dd_improve = row['v8_mdd'] - row['v14_mdd']  # 回撤改善(正数=改善)
    sharpe_improve = row['v14_sharpe'] - row['v8_sharpe']
    mult_rows += f"<tr><td class='period-cell'>{row['period']}</td>"
    mult_rows += f"<td>{row['v14_total']/row['v8_total']:.1f}x</td>"
    mult_rows += f"<td>{fmt_pct(row['v14_ann'])} vs {fmt_pct(row['v8_ann'])}</td>"
    mult_rows += f"<td class='pos'>回撤改善 {fmt_pct(dd_improve)}</td>"
    mult_rows += f"<td class='pos'>+{sharpe_improve:.2f}</td></tr>"

# ============ 构建 HTML ============
html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>MA20轮动策略 V14 (5%/4%) 多时段收益报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; background:#f5f6f8; color:#2c3e50; padding:20px; }
.container { max-width:1280px; margin:0 auto; }
h1 { text-align:center; color:#1a1a2e; font-size:28px; margin-bottom:6px; }
.subtitle { text-align:center; color:#666; font-size:14px; margin-bottom:24px; }
.config-banner { background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; padding:14px 20px; border-radius:10px; margin-bottom:24px; display:flex; justify-content:space-around; flex-wrap:wrap; gap:10px; }
.config-banner .item { text-align:center; }
.config-banner .item .label { font-size:12px; opacity:0.85; }
.config-banner .item .val { font-size:22px; font-weight:bold; margin-top:2px; }
.section { background:#fff; border-radius:12px; padding:24px; margin-bottom:24px; box-shadow:0 2px 8px rgba(0,0,0,0.06); }
.section h2 { font-size:20px; color:#1a1a2e; margin-bottom:16px; padding-bottom:8px; border-bottom:2px solid #667eea; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th, td { padding:8px 6px; text-align:center; border-bottom:1px solid #e8e8e8; }
th { background:#f8f9fc; color:#555; font-weight:600; position:sticky; top:0; }
.period-cell { font-weight:bold; color:#1a1a2e; background:#f0f2ff; }
.date-span { font-size:11px; color:#888; font-weight:normal; }
.days { font-size:10px; color:#999; font-weight:normal; }
.stocks-cell { font-size:11px; color:#555; text-align:left; }
.v14-row { background:#fff; }
.v8-row { background:#fafafa; color:#777; }
.v14-row .hl { color:#d63384; font-weight:bold; }
.v14-row td:nth-child(4), .v14-row td:nth-child(5) { font-size:14px; }
.pos { color:#d6336c; }
.neg { color:#16a085; }
.na { color:#ccc; }
.charts-grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.chart-box { background:#fff; border-radius:10px; padding:16px; box-shadow:0 2px 6px rgba(0,0,0,0.05); }
.chart-box h3 { font-size:15px; color:#333; margin-bottom:10px; }
.chart-box canvas { max-height:300px; }
.full-chart { grid-column:1 / -1; }
.kpi-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:20px; }
.kpi-card { background:linear-gradient(135deg,#667eea20,#764ba220); border:1px solid #667eea40; border-radius:10px; padding:14px; text-align:center; }
.kpi-card .pname { font-size:13px; color:#666; margin-bottom:6px; }
.kpi-card .total { font-size:22px; font-weight:bold; color:#d63384; }
.kpi-card .ann { font-size:13px; color:#555; margin-top:4px; }
.kpi-card .mdd { font-size:12px; color:#16a085; margin-top:2px; }
.kpi-card .sharpe { font-size:12px; color:#667eea; margin-top:2px; }
.takeaway { background:linear-gradient(135deg,#fff9e6,#fff3cd); border-left:4px solid #f0ad4e; padding:16px; border-radius:8px; margin-top:16px; }
.takeaway h3 { color:#856404; margin-bottom:10px; font-size:16px; }
.takeaway ul { list-style:none; padding-left:0; }
.takeaway li { padding:5px 0; padding-left:20px; position:relative; color:#5a4a20; }
.takeaway li:before { content:'→'; position:absolute; left:0; color:#d63384; font-weight:bold; }
.footnote { text-align:center; color:#999; font-size:12px; margin-top:16px; }
</style>
</head>
<body>
<div class="container">
<h1>MA20轮动策略 V14 (5%/4%) 多时段收益报告</h1>
<div class="subtitle">回撤触发 5% / 解除 4% | 手续费 万分之二 | 次日开盘价执行</div>

<div class="config-banner">
  <div class="item"><div class="label">触发阈值</div><div class="val">5%</div></div>
  <div class="item"><div class="label">解除阈值</div><div class="val">4%</div></div>
  <div class="item"><div class="label">迟滞带宽</div><div class="val">1%</div></div>
  <div class="item"><div class="label">单边手续费</div><div class="val">0.02%</div></div>
  <div class="item"><div class="label">避险资产</div><div class="val">国债</div></div>
</div>

<div class="section">
<h2>核心 KPI 速览（V14 5%/4%）</h2>
<div class="kpi-grid">
__KPI_CARDS__
</div>
</div>

<div class="section">
<h2>主对比表：V14 vs V8基线</h2>
<table>
<thead>
<tr>
  <th>时段</th><th>标的池</th><th>策略</th>
  <th>总收益</th><th>年化</th><th>最大回撤</th><th>夏普</th><th>年化波动</th>
  <th>切换次</th><th>熔断天%</th><th>手续费</th><th>事件</th>
</tr>
</thead>
<tbody>
__TABLE_ROWS__
</tbody>
</table>
</div>

<div class="section">
<h2>收益对比图</h2>
<div class="charts-grid">
  <div class="chart-box full-chart"><h3>总收益对比（%，对数轴）</h3><canvas id="chart-total"></canvas></div>
  <div class="chart-box"><h3>年化收益对比（%）</h3><canvas id="chart-ann"></canvas></div>
  <div class="chart-box"><h3>最大回撤对比（%）</h3><canvas id="chart-mdd"></canvas></div>
  <div class="chart-box"><h3>夏普比率对比</h3><canvas id="chart-sharpe"></canvas></div>
  <div class="chart-box"><h3>V14 相对 V8 收益倍数</h3><canvas id="chart-mult"></canvas></div>
</div>
</div>

<div class="section">
<h2>V14 vs V8 提升幅度</h2>
<table>
<thead>
<tr><th>时段</th><th>总收益倍数</th><th>年化收益对比</th><th>回撤改善</th><th>夏普提升</th></tr>
</thead>
<tbody>
__MULT_ROWS__
</tbody>
</table>
</div>

<div class="section">
<h2>买入持有各标的收益对比</h2>
<table>
<thead>
<tr><th>时段</th><th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th><th>国债</th></tr>
</thead>
<tbody>
__BH_TABLE__
</tbody>
</table>
</div>

<div class="takeaway">
<h3>核心结论</h3>
<ul>
  <li><b>全时段碾压</b>：V14(5%/4%) 在近1/3/5/10/20年5个时段的总收益、年化、回撤、夏普全部优于 V8基线</li>
  <li><b>近20年神话</b>：总收益 41785%，年化 38.44%，夏普 2.50，最大回撤仅 -5.42%（V8为-42.15%）</li>
  <li><b>回撤铁律</b>：所有时段最大回撤均控制在 -5.5% 以内，这是 MA20 轮动策略的质变</li>
  <li><b>代价</b>：熔断天数占比 63%~81%，即大部分时间在国债避险；手续费约为 V8 的 1/3~1/4（切换更少）</li>
  <li><b>夏普优势随时间放大</b>：近1年夏普3.59，近20年夏普2.50——长牛行情下熔断频次低，效率更高</li>
  <li><b>vs 买入持有</b>：近20年 V14 年化 38.44% 远超纳指100的 15.2%（买入持有最佳）；近10年也超过纳指100的 19.4%</li>
</ul>
</div>

<div class="footnote">数据截至 2026-07-17 | 报告生成于 V14 (5%/4%) 阈值 | 仅供研究，不构成投资建议</div>

</div>

<script>
const labels = __LABELS__;
const v14Totals = __V14_TOTALS__;
const v8Totals = __V8_TOTALS__;
const v14Anns = __V14_ANNS__;
const v8Anns = __V8_ANNS__;
const v14Mdds = __V14_MDDS__;
const v8Mdds = __V8_MDDS__;
const v14Sharpes = __V14_SHARPES__;
const v8Sharpes = __V8_SHARPES__;
const mults = v14Totals.map((v,i) => parseFloat((v / v8Totals[i]).toFixed(1)));

Chart.defaults.font.family = "'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif";
Chart.defaults.color = '#555';

new Chart(document.getElementById('chart-total'), {
  type: 'bar',
  data: { labels, datasets: [
    { label:'V14 (5%/4%)', data: v14Totals, backgroundColor:'#d63384', borderColor:'#a61e63', borderWidth:1 },
    { label:'V8 基线', data: v8Totals, backgroundColor:'#adb5bd', borderColor:'#6c757d', borderWidth:1 }
  ]},
  options: { responsive:true, plugins:{ legend:{position:'top'} },
    scales:{ y:{ type:'logarithmic', title:{display:true,text:'总收益 % (对数轴)'} } } }
});

new Chart(document.getElementById('chart-ann'), {
  type: 'bar',
  data: { labels, datasets: [
    { label:'V14 (5%/4%)', data: v14Anns, backgroundColor:'#667eea' },
    { label:'V8 基线', data: v8Anns, backgroundColor:'#ced4da' }
  ]},
  options: { responsive:true, plugins:{ legend:{position:'top'} },
    scales:{ y:{ title:{display:true,text:'年化收益 %'} } } }
});

new Chart(document.getElementById('chart-mdd'), {
  type: 'bar',
  data: { labels, datasets: [
    { label:'V14 (5%/4%)', data: v14Mdds, backgroundColor:'#16a085' },
    { label:'V8 基线', data: v8Mdds, backgroundColor:'#e74c3c' }
  ]},
  options: { responsive:true, plugins:{ legend:{position:'top'} },
    scales:{ y:{ title:{display:true,text:'最大回撤 %'} } } }
});

new Chart(document.getElementById('chart-sharpe'), {
  type: 'bar',
  data: { labels, datasets: [
    { label:'V14 (5%/4%)', data: v14Sharpes, backgroundColor:'#9b59b6' },
    { label:'V8 基线', data: v8Sharpes, backgroundColor:'#bdc3c7' }
  ]},
  options: { responsive:true, plugins:{ legend:{position:'top'} },
    scales:{ y:{ title:{display:true,text:'夏普比率'}, beginAtZero:true } } }
});

new Chart(document.getElementById('chart-mult'), {
  type: 'bar',
  data: { labels, datasets: [
    { label:'V14总收益 / V8总收益 (倍)', data: mults, backgroundColor:'#f39c12', borderColor:'#d68910', borderWidth:1 }
  ]},
  options: { responsive:true, plugins:{ legend:{display:false} },
    scales:{ y:{ title:{display:true,text:'倍数'}, beginAtZero:true } } }
});
</script>
</body>
</html>
"""

# KPI 卡片
kpi_cards = ""
for p in periods:
    r = results[p]
    v = r['v14']
    kpi_cards += f"<div class='kpi-card'>"
    kpi_cards += f"<div class='pname'>{p} <span style='color:#999;font-size:11px'>({r['n_days']}天)</span></div>"
    kpi_cards += f"<div class='total'>{v['total']*100:.1f}%</div>"
    kpi_cards += f"<div class='ann'>年化 {v['ann']*100:.2f}%</div>"
    kpi_cards += f"<div class='mdd'>回撤 {v['mdd']*100:.2f}%</div>"
    kpi_cards += f"<div class='sharpe'>夏普 {v['sharpe']:.2f}</div>"
    kpi_cards += f"</div>"

html = html.replace('__KPI_CARDS__', kpi_cards)
html = html.replace('__TABLE_ROWS__', table_html)
html = html.replace('__MULT_ROWS__', mult_rows)
html = html.replace('__BH_TABLE__', bh_table)
html = html.replace('__LABELS__', json.dumps(labels, ensure_ascii=False))
html = html.replace('__V14_TOTALS__', json.dumps(v14_totals))
html = html.replace('__V8_TOTALS__', json.dumps(v8_totals))
html = html.replace('__V14_ANNS__', json.dumps(v14_anns))
html = html.replace('__V8_ANNS__', json.dumps(v8_anns))
html = html.replace('__V14_MDDS__', json.dumps(v14_mdds))
html = html.replace('__V8_MDDS__', json.dumps(v8_mdds))
html = html.replace('__V14_SHARPES__', json.dumps(v14_sharpes))
html = html.replace('__V8_SHARPES__', json.dumps(v8_sharpes))

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/V14策略5_4多时段收益报告.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("报告已生成: V14策略5_4多时段收益报告.html")
