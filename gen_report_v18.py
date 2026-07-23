# -*- coding: utf-8 -*-
"""V18策略多时段对比报告生成器 — 14个行业/海外指数 vs V14(8宽基指数)"""
import json

with open('v18_periods_data.json','r',encoding='utf-8') as f:
    d18 = json.load(f)
with open('v14_periods_data.json','r',encoding='utf-8') as f:
    d14 = json.load(f)

periods = ['近20年','近10年','近5年','近3年','近1年']
colors = {'近20年':'#e74c3c','近10年':'#e67e22','近5年':'#2ecc71','近3年':'#3498db','近1年':'#9b59b6'}

# 构建对比数据
v18_data = []
v14_data = []
v8_18_data = []
v8_14_data = []
for p in periods:
    r18 = d18['results'][p]
    r14 = d14['results'][p]
    v18_data.append(r18['v18']['total']*100)
    v14_data.append(r14['v14']['total']*100)
    v8_18_data.append(r18['v8']['total']*100)
    v8_14_data.append(r14['v8']['total']*100)

# 持仓占比数据
holding_labels = ['国债','纳斯达克100','标普500','中证酒','中证环保','中证能源','中证消费',
                   '中证医药','中证金融','中证信息','中证体育','中证新能','中证军工','中证传媒','中证银行']
holding_data = {}
for p in periods:
    r18 = d18['results'][p]
    h = r18['v18'].get('holding', {})
    holding_data[p] = [h.get(nm, {'pct':0})['pct'] for nm in holding_labels]

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V18策略多时段对比报告 — 14行业指数 vs V14宽基指数</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI','Microsoft YaHei',sans-serif; background:#f5f5f5; color:#333; padding:20px; }
h1 { text-align:center; font-size:24px; margin-bottom:5px; color:#2c3e50; }
.subtitle { text-align:center; font-size:13px; color:#888; margin-bottom:20px; }
.section { background:#fff; border-radius:10px; padding:20px; margin-bottom:20px; box-shadow:0 2px 8px rgba(0,0,0,0.08); }
.section h2 { font-size:18px; color:#2c3e50; margin-bottom:15px; border-left:4px solid #3498db; padding-left:10px; }
.chart-container { position:relative; height:400px; margin-bottom:15px; }
.chart-container.tall { height:450px; }
table { width:100%; border-collapse:collapse; font-size:13px; margin-top:10px; }
th { background:#34495e; color:#fff; padding:8px 6px; text-align:center; font-weight:600; }
td { padding:7px 6px; text-align:center; border-bottom:1px solid #eee; }
tr:hover { background:#f8f9fa; }
.pos { color:#e74c3c; font-weight:600; }
.neg { color:#27ae60; font-weight:600; }
.win { background:#fdffcc; }
.lose { background:#ffe8e8; }
.note { background:#eaf6ff; border-left:4px solid #3498db; padding:12px 15px; margin:15px 0; font-size:13px; line-height:1.8; border-radius:0 6px 6px 0; }
.summary-cards { display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin-bottom:15px; }
.card { background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; border-radius:8px; padding:15px; text-align:center; }
.card .period { font-size:13px; opacity:0.9; }
.card .value { font-size:22px; font-weight:bold; margin:5px 0; }
.card .sub { font-size:11px; opacity:0.8; }
.card.win { background:linear-gradient(135deg,#11998e,#38ef7d); }
.card.lose { background:linear-gradient(135deg,#eb3349,#f45c43); }
.badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:bold; }
.badge-win { background:#d4edda; color:#155724; }
.badge-lose { background:#f8d7da; color:#721c24; }
.badge-tie { background:#fff3cd; color:#856404; }
</style>
</head>
<body>
<h1>V18策略多时段对比报告</h1>
<div class="subtitle">14个行业/海外指数+国债 (5%/4%阈值) vs V14 8宽基指数+国债 (5%/4%阈值)</div>

<div class="section">
<h2>核心结论</h2>
<div class="note">
<b>14个行业指数候选池仅在近1年优于V14宽基指数池，其余4个时段全面落后。</b><br>
• 近1年V18 +136.39% > V14 +91.25% ✅（中证信息+中证新能贡献）<br>
• 近3/5/10/20年V18收益仅为V14的15%~40% ❌<br>
• 根本原因：行业指数波动大、趋势性弱，V8基线（无熔断）近10/5/3年居然<b>负收益</b>（-17%/-20%/-9%），熔断虽能扭亏为盈但大部分时间在避险<br>
• V14宽基指数（创业板50/纳指100等）趋势性强，V8基线本身就是正收益，熔断锦上添花
</div>
</div>

<div class="section">
<h2>总览对比卡片</h2>
<div class="summary-cards">
'''

for p in periods:
    r18 = d18['results'][p]['v18']
    r14 = d14['results'][p]['v14']
    diff = r18['total'] - r14['total']
    cls = 'win' if diff > 0.05 else 'lose' if diff < -0.05 else ''
    badge = '<span class="badge badge-win">V18胜</span>' if diff > 0.05 else '<span class="badge badge-lose">V14胜</span>' if diff < -0.05 else '<span class="badge badge-tie">持平</span>'
    html += f'''<div class="card {cls}">
<div class="period">{p}</div>
<div class="value">{r18["total"]*100:.1f}%</div>
<div class="sub">V14: {r14["total"]*100:.1f}%</div>
<div style="margin-top:5px;">{badge}</div>
</div>
'''

html += '''</div>
</div>

<div class="section">
<h2>V18 vs V14 总收益对比</h2>
<div class="chart-container">
<canvas id="chartTotal"></canvas>
</div>
<table>
<tr><th>时段</th><th>V18(14行业)总收益</th><th>V14(8宽基)总收益</th><th>收益差</th><th>V18年化</th><th>V14年化</th><th>V18回撤</th><th>V14回撤</th><th>V18夏普</th><th>V14夏普</th><th>胜负</th></tr>
'''

for p in periods:
    r18 = d18['results'][p]['v18']
    r14 = d14['results'][p]['v14']
    diff = (r18['total'] - r14['total']) * 100
    cls = 'win' if diff > 5 else 'lose' if diff < -5 else ''
    badge = '<span class="badge badge-win">V18胜</span>' if diff > 5 else '<span class="badge badge-lose">V14胜</span>' if diff < -5 else '<span class="badge badge-tie">持平</span>'
    html += f'''<tr class="{cls}">
<td><b>{p}</b></td>
<td class="pos">{r18["total"]*100:.2f}%</td>
<td class="pos">{r14["total"]*100:.2f}%</td>
<td>{diff:+.2f}pp</td>
<td>{r18["ann"]*100:.2f}%</td>
<td>{r14["ann"]*100:.2f}%</td>
<td class="neg">{r18["mdd"]*100:.2f}%</td>
<td class="neg">{r14["mdd"]*100:.2f}%</td>
<td>{r18["sharpe"]:.2f}</td>
<td>{r14["sharpe"]:.2f}</td>
<td>{badge}</td>
</tr>'''

html += '''</table>
</div>

<div class="section">
<h2>V8基线对比（无熔断）— 行业指数 vs 宽基指数的原始差异</h2>
<div class="chart-container">
<canvas id="chartV8"></canvas>
</div>
<div class="note">
<b>这是V18不如V14的根源：</b>V8基线（无熔断的MA20轮动）在行业指数池上表现极差——近10/5/3年居然是<b>负收益</b>（-17%/-20%/-9%），
而宽基指数池的V8基线同期是正收益（427%/130%/112%）。行业指数波动大、轮动频繁、趋势性弱，
MA20信号频繁切换导致手续费侵蚀严重（V8近10年手续费30.58%），且每次切换经常踏错节奏。
</div>
<table>
<tr><th>时段</th><th>V18-V8基线总收益</th><th>V14-V8基线总收益</th><th>V18-V8回撤</th><th>V14-V8回撤</th><th>V18-V8切换次</th><th>V14-V8切换次</th><th>V18-V8手续费</th><th>V14-V8手续费</th></tr>
'''

for p in periods:
    r18v8 = d18['results'][p]['v8']
    r14v8 = d14['results'][p]['v8']
    html += f'''<tr>
<td><b>{p}</b></td>
<td class="{'neg' if r18v8['total']<0 else 'pos'}">{r18v8["total"]*100:.2f}%</td>
<td class="pos">{r14v8["total"]*100:.2f}%</td>
<td class="neg">{r18v8["mdd"]*100:.2f}%</td>
<td class="neg">{r14v8["mdd"]*100:.2f}%</td>
<td>{r18v8["switches"]}</td>
<td>{r14v8["switches"]}</td>
<td>{r18v8["total_fee"]*100:.2f}%</td>
<td>{r14v8["total_fee"]*100:.2f}%</td>
</tr>'''

html += '''</table>
</div>

<div class="section">
<h2>V18 持仓占比（各时段）</h2>
<div class="chart-container tall">
<canvas id="chartHolding"></canvas>
</div>
<div class="note">
<b>行业指数池的熔断时间远超宽基指数池：</b>V18近10/5/3年熔断天数占比高达89%~98%（V14为63%~75%），
说明行业指数的V8基线几乎一直在回撤>5%的状态，熔断机制几乎全程启动，策略变成了"大部分时间持国债+偶尔短暂入场"。<br>
• 近10年V18持仓最分散：12个行业指数都有短暂持仓，但合计仅6.4%（国债93.6%）<br>
• 近5年V18几乎全持国债（97.6%），仅中证能源(1.7%)偶尔入场<br>
• 近1年V18最活跃：中证信息(17.1%)+中证新能(9.7%)+中证军工(5.1%)贡献了主要收益
</div>
<table>
<tr><th>标的</th>'''

for p in periods:
    html += f'<th>{p}</th>'
html += '</tr>'

for idx, nm in enumerate(holding_labels):
    html += f'<tr><td style="text-align:left;font-weight:600;">{nm}</td>'
    for p in periods:
        val = holding_data[p][idx]
        cls = 'pos' if val > 5 else ''
        html += f'<td class="{cls}">{val:.1f}%</td>' if val > 0 else '<td style="color:#ccc;">—</td>'
    html += '</tr>'
html += '</table></div>'

# 熔断对比
html += '''
<div class="section">
<h2>熔断机制对比</h2>
<table>
<tr><th>时段</th><th>V18熔断天%</th><th>V14熔断天%</th><th>V18切换次</th><th>V14切换次</th><th>V18手续费</th><th>V14手续费</th><th>V18事件数</th><th>V14事件数</th></tr>
'''
for p in periods:
    r18 = d18['results'][p]['v18']
    r14 = d14['results'][p]['v14']
    html += f'''<tr>
<td><b>{p}</b></td>
<td>{r18["cb_pct"]*100:.1f}%</td>
<td>{r14["cb_pct"]*100:.1f}%</td>
<td>{r18["switches"]}</td>
<td>{r14["switches"]}</td>
<td>{r18["total_fee"]*100:.2f}%</td>
<td>{r14["total_fee"]*100:.2f}%</td>
<td>{len(r18["cb_events"])}</td>
<td>{len(r14["cb_events"])}</td>
</tr>'''
html += '''</table>
<div class="note">
<b>熔断天数的差异揭示了问题本质：</b>V18近10年熔断93.6%、近5年97.6%——行业指数的V8基线几乎全程处于回撤>5%状态，
熔断机制虽然成功把负收益扭转为正收益（V8 -17% → V18 +150%），但代价是93.6%的时间在持国债，收益主要来自国债利息而非股票轮动。<br>
相比之下，V14近10年熔断63%，有37%的时间在持有股票，能吃到更多行情，因此收益远超V18。
</div>
</div>
'''

# 买入持有对比
html += '''
<div class="section">
<h2>买入持有收益对比（行业指数 vs 宽基指数）</h2>
<div class="note">
行业指数的买入持有收益普遍远低于宽基指数。近5年12个行业指数中有8个<b>亏损</b>（中证酒-58%、中证消费-46%、中证医药-47%等），
而宽基指数（纳指100 +89%、创业板50等）多数正收益。这说明行业指数整体走势偏弱，不是MA20轮动能弥补的。
</div>
<table>
<tr><th>标的</th>'''

for p in periods:
    html += f'<th>{p}</th>'
html += '</tr>'

bh_labels = holding_labels
for idx, nm in enumerate(bh_labels):
    if nm == '国债':
        continue
    sid = None
    for k, v in d18['names'].items():
        if v == nm:
            sid = k
            break
    if sid is None:
        continue
    html += f'<tr><td style="text-align:left;font-weight:600;">{nm}</td>'
    for p in periods:
        bh = d18['results'][p].get('bh', {})
        val = bh.get(sid, None)
        if val is not None:
            cls = 'pos' if val > 0 else 'neg'
            html += f'<td class="{cls}">{val*100:.2f}%</td>'
        else:
            html += '<td style="color:#ccc;">—</td>'
    html += '</tr>'

# 宽基买入持有对比
html += '<tr style="background:#e8f4fd;"><td style="text-align:left;font-weight:600;color:#2980b9;">— V14宽基指数对比 —</td>'
for p in periods:
    html += f'<td style="color:#2980b9;font-weight:600;">{p}</td>'
html += '</tr>'

broad_names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}
for sid, nm in broad_names.items():
    html += f'<tr><td style="text-align:left;font-weight:600;">{nm}</td>'
    for p in periods:
        bh = d14['results'][p].get('bh', {})
        val = bh.get(sid, bh.get(str(sid), None))
        if val is not None:
            cls = 'pos' if val > 0 else 'neg'
            html += f'<td class="{cls}">{val*100:.2f}%</td>'
        else:
            html += '<td style="color:#ccc;">—</td>'
    html += '</tr>'

html += '''</table>
</div>

<div class="section">
<h2>详细数据表</h2>
<table>
<tr><th>时段</th><th>策略</th><th>总收益</th><th>年化</th><th>最大回撤</th><th>夏普</th><th>年化波动</th><th>切换次</th><th>熔断天%</th><th>手续费</th><th>事件数</th><th>标的池</th></tr>
'''

for p in periods:
    r18 = d18['results'][p]
    r14 = d14['results'][p]
    for label, m, pool in [('V18(行业)', r18['v18'], f'{len(r18["stock_ids"])}股+债'), ('V18-V8基线', r18['v8'], f'{len(r18["stock_ids"])}股+债'), ('V14(宽基)', r14['v14'], f'{len(r14["stock_ids"])}股+债'), ('V14-V8基线', r14['v8'], f'{len(r14["stock_ids"])}股+债')]:
        html += f'''<tr>
<td><b>{p}</b></td>
<td>{label}</td>
<td class="{'pos' if m['total']>0 else 'neg'}">{m["total"]*100:.2f}%</td>
<td>{m["ann"]*100:.2f}%</td>
<td class="neg">{m["mdd"]*100:.2f}%</td>
<td>{m["sharpe"]:.2f}</td>
<td>{m["ann_vol"]*100:.2f}%</td>
<td>{m["switches"]}</td>
<td>{m["cb_pct"]*100:.1f}%</td>
<td>{m["total_fee"]*100:.2f}%</td>
<td>{len(m.get("cb_events",[]))}</td>
<td>{pool}</td>
</tr>'''
    html += '<tr style="border-top:2px solid #34495e;"></tr>'

html += '''</table>
</div>

<div class="section">
<h2>结论与分析</h2>
<div class="note">
<b>1. 行业指数池不如宽基指数池——4/5时段收益更低</b><br>
V18仅在近1年(+136%)优于V14(+91%)，其余4个时段V18收益仅为V14的15%~40%。<br><br>

<b>2. 根本原因：行业指数趋势性弱、波动大</b><br>
• V8基线（无熔断）在行业指数池上近10/5/3年是<b>负收益</b>（-17%/-20%/-9%），宽基指数池同期是正收益（427%/130%/112%）<br>
• 行业指数轮动频繁，V8近10年切换765次（V14仅412次），手续费侵蚀30.58%（V14仅7.02%）<br>
• 行业指数买入持有普遍亏损（近5年12个中有8个亏损），说明行业指数整体走势偏弱<br><br>

<b>3. 熔断机制虽能扭亏为盈，但代价过大</b><br>
• V18近10年熔断93.6%、近5年97.6%——几乎全程在避险，收益主要来自国债利息<br>
• V14近10年熔断63%、近5年72%——有足够时间持有股票吃行情<br>
• 熔断天数差异直接导致收益差距：V18大部分时间"睡着"了<br><br>

<b>4. 近1年V18胜出的原因</b><br>
• 中证信息(+57.64%买入持有)和中证新能(+12.18%)在近1年表现突出，成为bf最高的标的<br>
• V18近1年熔断仅62.7%（远低于近10/5年），有37%时间在持仓，能吃到行情<br>
• 但这是短期现象，不足以推翻长期结论<br><br>

<b>5. MA20轮动策略的本质要求</b><br>
MA20轮动需要标的具有<b>强趋势性</b>——价格持续偏离均线（bf持续为正）才能吃到主升浪。
宽基指数（创业板50/纳指100/科创50）代表整个市场或大型板块，趋势性强、持续性好；
行业指数受政策/周期影响大，频繁切换涨跌主角，趋势持续性差，导致MA20信号频繁失效。
</div>
</div>

<script>
// Chart数据
const periods = ''' + json.dumps(periods, ensure_ascii=False) + ''';
const colors = ''' + json.dumps(colors, ensure_ascii=False) + ''';

// 总收益对比图
new Chart(document.getElementById('chartTotal'), {
    type: 'bar',
    data: {
        labels: periods,
        datasets: [
            {label: 'V18 (14行业指数)', data: ''' + json.dumps([round(v,2) for v in v18_data]) + ''', backgroundColor: 'rgba(231,76,60,0.7)', borderColor: '#e74c3c', borderWidth: 1},
            {label: 'V14 (8宽基指数)', data: ''' + json.dumps([round(v,2) for v in v14_data]) + ''', backgroundColor: 'rgba(52,152,219,0.7)', borderColor: '#3498db', borderWidth: 1},
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {title: {display: true, text: 'V18 vs V14 总收益对比 (5%/4%阈值)', font: {size: 16}}},
        scales: {y: {type: 'logarithmic', title: {display: true, text: '总收益% (对数轴)'}}}
    }
});

// V8基线对比图
new Chart(document.getElementById('chartV8'), {
    type: 'bar',
    data: {
        labels: periods,
        datasets: [
            {label: 'V18-V8基线 (行业)', data: ''' + json.dumps([round(v,2) for v in v8_18_data]) + ''', backgroundColor: 'rgba(231,76,60,0.5)', borderColor: '#e74c3c', borderWidth: 1},
            {label: 'V14-V8基线 (宽基)', data: ''' + json.dumps([round(v,2) for v in v8_14_data]) + ''', backgroundColor: 'rgba(52,152,219,0.5)', borderColor: '#3498db', borderWidth: 1},
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {title: {display: true, text: 'V8基线对比 — 无熔断的原始MA20轮动', font: {size: 16}}},
        scales: {y: {title: {display: true, text: '总收益%'}}}
    }
});

// 持仓占比堆叠柱状图
new Chart(document.getElementById('chartHolding'), {
    type: 'bar',
    data: {
        labels: periods,
        datasets: [
            ''' + ','.join([
                f'{{label: "{nm}", data: {[holding_data[p][i] for p in periods]}, backgroundColor: "{["#95a5a6","#3498db","#1abc9c","#e74c3c","#2ecc71","#f39c12","#9b59b6","#34495e","#e67e22","#1abc9c","#fd79a8","#6c5ce7","#a29bfe","#ffeaa7","#fab1a0"][i]}", stack: "hold"}}'
                for i, nm in enumerate(holding_labels)
            ]) + '''
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {title: {display: true, text: 'V18各时段持仓占比 (%)', font: {size: 16}}, legend: {position: 'right', labels: {boxWidth: 12, font: {size: 11}}},
            tooltip: {callbacks: {label: function(ctx) { return ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(1) + '%'; }}}},
        scales: {x: {stacked: true}, y: {stacked: true, title: {display: true, text: '占比%'}, max: 100}}
    }
});
</script>
</body>
</html>'''

html = html.replace('TRUE', 'true').replace('FALSE', 'false')

with open('V18策略多时段对比报告.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('报告已生成: V18策略多时段对比报告.html')
