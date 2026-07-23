# -*- coding: utf-8 -*-
"""生成V17阈值搜索HTML报告"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v17_threshold_search.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

names = data['names']
thresholds = data['thresholds']
search = data['search_results']
v14_ref = data.get('v14_ref', {})
rank_sum = data.get('rank_sum', {})
extra_names = data.get('extra_names', [])

periods = ['近20年', '近10年', '近5年', '近3年', '近1年']
keys = list(search.keys())

# 找各时段最优
best_per_period = {}
for p in periods:
    best_key = max(keys, key=lambda k: search[k][p]['total'])
    best_per_period[p] = best_key

# 综合排名前5
sorted_keys = sorted(rank_sum.keys(), key=lambda x: rank_sum[x])

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V17阈值搜索报告 - 12股+债</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#f5f7fa; color:#333; line-height:1.6; }
.container { max-width:1200px; margin:0 auto; padding:20px; }
h1 { text-align:center; color:#1a1a2e; margin:20px 0 5px; font-size:26px; }
.subtitle { text-align:center; color:#888; margin-bottom:25px; font-size:14px; }
.card { background:#fff; border-radius:12px; padding:20px; margin-bottom:20px; box-shadow:0 2px 8px rgba(0,0,0,0.06); }
.card h2 { font-size:18px; color:#1a1a2e; margin-bottom:15px; border-left:4px solid #667eea; padding-left:10px; }
.summary-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin-bottom:15px; }
.stat-card { background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:#fff; border-radius:10px; padding:15px; text-align:center; }
.stat-card .label { font-size:12px; opacity:0.9; }
.stat-card .value { font-size:22px; font-weight:bold; margin-top:5px; }
.stat-card .sub { font-size:11px; opacity:0.8; margin-top:3px; }
.stat-card.green { background:linear-gradient(135deg,#11998e 0%,#38ef7d 100%); }
.stat-card.red { background:linear-gradient(135deg,#eb3349 0%,#f45c43 100%); }
.stat-card.orange { background:linear-gradient(135deg,#f12711 0%,#f5af19 100%); }
table { width:100%; border-collapse:collapse; font-size:13px; }
th, td { padding:8px 10px; text-align:center; border-bottom:1px solid #eee; }
th { background:#f8f9fa; font-weight:600; color:#555; position:sticky; top:0; }
tr:hover { background:#f8f9fa; }
.best { background:#fff3cd !important; font-weight:bold; }
.win { color:#28a745; font-weight:bold; }
.lose { color:#dc3545; font-weight:bold; }
.heat-cell { font-size:12px; }
.note { background:#e7f3ff; border-left:4px solid #2196F3; padding:12px 15px; border-radius:8px; margin:15px 0; font-size:13px; }
.warning { background:#fff3cd; border-left:4px solid #ffc107; padding:12px 15px; border-radius:8px; margin:15px 0; font-size:13px; }
.chart-box { position:relative; height:400px; margin:15px 0; }
.compare-table th { background:#667eea; color:#fff; }
.compare-table .v17-col { background:#f0f7ff; }
.compare-table .v14-col { background:#fff8f0; }
</style>
</head>
<body>
<div class="container">
<h1>V17 阈值搜索报告</h1>
<p class="subtitle">12股+债（原8股+中证2000+日经225+越南胡志明+英国富时100+国债）| 15个阈值组合 × 5个时段</p>

<div class="card">
<h2>核心结论</h2>
<div class="summary-grid">
<div class="stat-card red">
<div class="label">V17最优阈值</div>
<div class="value">3%/3%</div>
<div class="sub">零迟滞带宽</div>
</div>
<div class="stat-card red">
<div class="label">vs V14(5%/4%)</div>
<div class="value">4负1胜</div>
<div class="sub">仅近1年略优</div>
</div>
<div class="stat-card green">
<div class="label">V17回撤更优</div>
<div class="value">-2.7%~-3.3%</div>
<div class="sub">vs V14的-4.1%~-5.4%</div>
</div>
<div class="stat-card orange">
<div class="label">V17熔断天数</div>
<div class="value">71%-92%</div>
<div class="sub">过度保守</div>
</div>
</div>
<div class="warning">
<b>结论：加入中证2000+3海外后，无论怎么调阈值都无法超过V14(8股,5%/4%)的收益。</b><br>
3%/3%虽让回撤更小(-2.7%~-3.3%)，但熔断天数高达71%-92%，过度保守导致收益受损。根本原因：新增标的扰动了V8基线净值走势，改变了熔断触发/解除节奏。
</div>
</div>
'''

# 阈值热力图表
html += '''
<div class="card">
<h2>阈值网格搜索 - 总收益热力图</h2>
<p style="font-size:13px;color:#888;margin-bottom:10px;">15个阈值组合在5个时段的总收益(%)。黄色高亮=该时段最优。</p>
<table>
<thead>
<tr><th>触发/解除</th>
'''
for p in periods:
    html += f'<th>{p}</th>'
html += '<th>平均排名</th></tr></thead><tbody>'

for k in sorted_keys:
    avg_rank = rank_sum[k] / 5
    html += f'<tr><td><b>{k}</b></td>'
    for p in periods:
        v = search[k][p]['total'] * 100
        is_best = (best_per_period[p] == k)
        cls = 'best' if is_best else ''
        # 颜色梯度
        if v > 20000:
            color = '#28a745'
        elif v > 10000:
            color = '#5cb85c'
        elif v > 5000:
            color = '#8fd17a'
        elif v > 2000:
            color = '#ffc107'
        elif v > 1000:
            color = '#fd7e14'
        else:
            color = '#dc3545'
        html += f'<td class="heat-cell {cls}" style="color:{color};">{v:.1f}%</td>'
    rank_color = '#28a745' if avg_rank <= 2 else '#ffc107' if avg_rank <= 5 else '#dc3545'
    html += f'<td style="color:{rank_color};font-weight:bold;">{avg_rank:.1f}</td></tr>'

html += '</tbody></table>'
html += '<p style="font-size:12px;color:#888;margin-top:8px;">平均排名：各时段按收益排名(1=最好)，取5个时段平均值。越小越好。</p>'
html += '</div>'

# V17最优 vs V14对比表
html += '''
<div class="card">
<h2>V17最优阈值 vs V14(8股,5%/4%) 全面对比</h2>
<table class="compare-table">
<thead>
<tr>
<th rowspan="2">时段</th>
<th colspan="4" style="background:#4a90d9;">V17最优阈值</th>
<th colspan="4" style="background:#e8871e;">V14 (5%/4%)</th>
<th rowspan="2">收益差</th>
<th rowspan="2">胜负</th>
</tr>
<tr>
<th class="v17-col">阈值</th>
<th class="v17-col">总收益</th>
<th class="v17-col">回撤</th>
<th class="v17-col">夏普</th>
<th class="v14-col">总收益</th>
<th class="v14-col">回撤</th>
<th class="v14-col">夏普</th>
<th class="v14-col">熔断天%</th>
</tr>
</thead>
<tbody>
'''

for p in periods:
    bk = best_per_period[p]
    v17 = search[bk][p]
    v14 = v14_ref.get(p, {})
    if not v14:
        continue
    diff = (v17['total'] - v14['total']) * 100
    win = 'win' if diff > 0 else 'lose'
    win_text = 'V17胜' if diff > 0 else 'V14胜'
    html += f'''<tr>
<td><b>{p}</b></td>
<td class="v17-col"><b>{bk}</b></td>
<td class="v17-col">{v17['total']*100:.1f}%</td>
<td class="v17-col">{v17['mdd']*100:.2f}%</td>
<td class="v17-col">{v17['sharpe']:.2f}</td>
<td class="v14-col">{v14['total']*100:.1f}%</td>
<td class="v14-col">{v14['mdd']*100:.2f}%</td>
<td class="v14-col">{v14['sharpe']:.2f}</td>
<td class="v14-col">{v14['cb_pct']*100:.1f}%</td>
<td>{diff:+.1f}pp</td>
<td class="{win}">{win_text}</td>
</tr>'''

html += '</tbody></table>'
html += '<div class="note">V17最优阈值各时段不同：近20/5/3/1年为<b>3%/3%</b>，近10年为<b>5%/5%</b>。但即使各自取最优，仍4负1胜。</div>'
html += '</div>'

# 3/3详细指标
html += '<div class="card"><h2>3%/3%阈值（综合排名第1）详细指标</h2>'
html += '<table><thead><tr><th>时段</th><th>总收益</th><th>年化</th><th>最大回撤</th><th>夏普</th><th>切换次数</th><th>熔断天%</th><th>熔断事件</th></tr></thead><tbody>'
k33 = '3/3'
for p in periods:
    m = search[k33][p]
    html += f'''<tr>
<td><b>{p}</b></td>
<td>{m['total']*100:.1f}%</td>
<td>{m['ann']*100:.2f}%</td>
<td style="color:#dc3545;">{m['mdd']*100:.2f}%</td>
<td>{m['sharpe']:.2f}</td>
<td>{m['switches']}</td>
<td>{m['cb_pct']*100:.1f}%</td>
<td>{m.get('cb_events',0)}</td>
</tr>'''
html += '</tbody></table>'
html += '<div class="warning"><b>3%/3%的问题</b>：零迟滞带宽（触发=解除）导致频繁触发-解除，熔断天数高达71%-92%。虽然回撤极小(-2.7%~-3.3%)，但过度保守严重侵蚀收益。近20年26335%看似不错，但V14(5%/4%)是41785%，差距巨大。</div>'
html += '</div>'

# 综合排名前5
html += '<div class="card"><h2>综合排名前8</h2>'
html += '<table><thead><tr><th>排名</th><th>阈值</th><th>平均排名</th>'
for p in periods:
    html += f'<th>{p}</th>'
html += '<th>规律</th></tr></thead><tbody>'

patterns = {
    '3/3': '零带宽，最紧触发',
    '5/5': '零带宽，中等触发',
    '4/4': '零带宽，偏紧触发',
    '6/6': '零带宽，偏松触发',
    '7/7': '零带宽，松触发',
    '4/3': '1%带宽，紧触发',
    '3/2': '1%带宽，最紧触发',
    '6/5': '1%带宽，中等触发',
    '5/4': '1%带宽，V14最优(8股)',
    '7/6': '1%带宽，偏松触发',
    '5/3': '2%带宽，紧触发',
    '6/4': '2%带宽，中等触发',
    '8/7': '1%带宽，松触发',
    '7/5': '2%带宽，偏松触发',
    '8/6': '2%带宽，松触发',
}

for rank, k in enumerate(sorted_keys[:8], 1):
    avg_rank = rank_sum[k] / 5
    pattern = patterns.get(k, '')
    html += f'<tr><td><b>#{rank}</b></td><td><b>{k}</b></td><td>{avg_rank:.1f}</td>'
    for p in periods:
        v = search[k][p]['total'] * 100
        html += f'<td>{v:.1f}%</td>'
    html += f'<td style="font-size:12px;color:#888;">{pattern}</td></tr>'

html += '''</tbody></table>
<div class="note">
<b>关键规律</b>：在12股+债的标的池下，<b>零迟滞带宽（触发=解除）全面优于有带宽</b>。这与V14(8股)的结论（5%/4%即1%带宽最优）完全相反！<br>
原因：12股+债的V8基线净值更震荡（标的更多，切换更频繁），有带宽会导致解除后立刻又触发（whipsaw），零带宽反而更干净利落。
</div>
</div>'''

# 收益对比柱状图
labels_js = json.dumps(periods, ensure_ascii=False)
v17_best_data = [search[best_per_period[p]][p]['total'] * 100 for p in periods]
v14_data = [v14_ref.get(p, {}).get('total', 0) * 100 for p in periods]
v17_33_data = [search['3/3'][p]['total'] * 100 for p in periods]
v17_54_data = [search['5/4'][p]['total'] * 100 for p in periods]

html += f'''
<div class="card">
<h2>收益对比柱状图</h2>
<div class="chart-box">
<canvas id="chart1"></canvas>
</div>
<p style="font-size:13px;color:#888;">V14(8股,5%/4%)在4个时段领先，V17(12股+债,3%/3%)仅近1年领先。注意纵轴已截断（近20年数值过大）。</p>
</div>

<div class="card">
<h2>同阈值(5%/4%)下：12股+债 vs 8股+债</h2>
<div class="chart-box">
<canvas id="chart2"></canvas>
</div>
<p style="font-size:13px;color:#888;">同样用5%/4%阈值，12股+债(V17)在所有5个时段都不如8股+债(V14)。证明新增标的本身就是负贡献。</p>
</div>
'''

# 结论
html += '''
<div class="card">
<h2>结论与建议</h2>
<div class="warning">
<b>最终结论：不建议加入中证2000和3个海外指数。</b>
</div>
<table>
<thead><tr><th>发现</th><th>详情</th></tr></thead>
<tbody>
<tr><td><b>1. 无论怎么调阈值都无法翻盘</b></td><td>12股+债在15个阈值组合中，最优解3%/3%仍4负1负于V14(8股,5%/4%)</td></tr>
<tr><td><b>2. 最优阈值从5%/4%变为3%/3%</b></td><td>标的池扩大后基线更震荡，零带宽反而更优，但仍不及V14</td></tr>
<tr><td><b>3. 回撤更小但代价过大</b></td><td>3%/3%回撤-2.7%~-3.3%优于V14的-4.1%~-5.4%，但熔断天数71-92%严重侵蚀收益</td></tr>
<tr><td><b>4. 新增标的实际被选中极少</b></td><td>中证2000+3海外合计持仓占比仅0.5%-8.8%，但通过扰动基线净值显著拉低收益</td></tr>
<tr><td><b>5. 近1年是唯一亮点</b></td><td>V17(3/3)近1年145.5% vs V14的91.2%，但样本太小不足以推翻整体结论</td></tr>
</tbody>
</table>
<div class="note">
<b>三次验证一致结论</b>：<br>
- V15(加3海外, 5%/4%) → 4负1胜<br>
- V16(加中证2000, 5%/4%) → 5负0胜<br>
- V17(加全部4个, 阈值搜索) → 最优3%/3%仍4负1胜<br><br>
<b>"标的池越大越好"是错误直觉</b>。新增标的会通过改变V8基线净值走势扰动熔断机制的工作节奏，即使调整阈值也无法弥补。V14(8股+国债, 5%/4%)仍是最优配置。
</div>
</div>

<div class="card">
<h2>标的池说明</h2>
<table>
<thead><tr><th>时段</th><th>标的数</th><th>标的池</th></tr></thead>
<tbody>
<tr><td>近20年</td><td>8股+债</td><td>上证50/纳指100/沪深300/中证1000 + 中证2000(2013起left join) + 日经225/越南胡志明/英国富时100(left join) + 国债</td></tr>
<tr><td>近10年</td><td>11股+债</td><td>上述4股 + 创业板50/中证500/标普500 + 中证2000 + 3海外 + 国债</td></tr>
<tr><td>近5/3/1年</td><td>12股+债</td><td>上述7股 + 科创50 + 中证2000 + 3海外 + 国债</td></tr>
</tbody>
</table>
<div class="note">
<b>数据处理</b>：海外指数交易日历与A股不同，按各自日历算MA20/bf后left join到主表，缺失日bf=NaN不参与选股。中证2000从2013年起，近20年前7年缺失同样left join处理。英国富时100只到2026-04-17，之后自动排除。last_date固定2026-07-17保证与V14严格可比。
</div>
</div>
</div>

<script>
const labels = ''' + labels_js + ''';

new Chart(document.getElementById('chart1'), {
    type: 'bar',
    data: {
        labels: labels,
        datasets: [
            {label: 'V14 (8股, 5%/4%)', data: ''' + json.dumps(v14_data) + ''', backgroundColor: 'rgba(102,126,234,0.8)', borderColor: 'rgba(102,126,234,1)', borderWidth: 1},
            {label: 'V17最优 (各时段最优阈值)', data: ''' + json.dumps(v17_best_data) + ''', backgroundColor: 'rgba(255,193,7,0.8)', borderColor: 'rgba(255,193,7,1)', borderWidth: 1},
            {label: 'V17 (3%/3%)', data: ''' + json.dumps(v17_33_data) + ''', backgroundColor: 'rgba(220,53,69,0.7)', borderColor: 'rgba(220,53,69,1)', borderWidth: 1},
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { title: { display: true, text: '总收益对比 (%)' }, legend: { position: 'top' } },
        scales: { y: { beginAtZero: true, title: { display: true, text: '总收益 (%)' } } }
    }
});

new Chart(document.getElementById('chart2'), {
    type: 'bar',
    data: {
        labels: labels,
        datasets: [
            {label: 'V14 (8股+债, 5%/4%)', data: ''' + json.dumps(v14_data) + ''', backgroundColor: 'rgba(102,126,234,0.8)', borderColor: 'rgba(102,126,234,1)', borderWidth: 1},
            {label: 'V17 (12股+债, 5%/4%)', data: ''' + json.dumps(v17_54_data) + ''', backgroundColor: 'rgba(255,99,132,0.7)', borderColor: 'rgba(255,99,132,1)', borderWidth: 1},
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { title: { display: true, text: '同阈值5%/4%下: 8股 vs 12股 总收益对比 (%)' }, legend: { position: 'top' } },
        scales: { y: { beginAtZero: true, title: { display: true, text: '总收益 (%)' } } }
    }
});
</script>
</body>
</html>
'''

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/V17阈值搜索报告.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("报告已生成: V17阈值搜索报告.html")
