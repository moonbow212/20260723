# -*- coding: utf-8 -*-
"""生成 V16 (V14+中证2000) vs V14 vs V8 多时段对比 HTML 报告"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v16_periods_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

results = data['results']
v14_results = data['v14']
names = {int(k): v for k, v in data['names'].items()}
cfg = data['config']

periods = ['近20年', '近10年', '近5年', '近3年', '近1年']

# 收集数据
v16_totals = [round(results[p]['v16']['total'] * 100, 1) for p in periods]
v14_totals = [round(v14_results[p]['v14']['total'] * 100, 1) for p in periods]
v8_totals = [round(results[p]['v8']['total'] * 100, 1) for p in periods]

v16_anns = [round(results[p]['v16']['ann'] * 100, 1) for p in periods]
v14_anns = [round(v14_results[p]['v14']['ann'] * 100, 1) for p in periods]
v8_anns = [round(results[p]['v8']['ann'] * 100, 1) for p in periods]

v16_mdds = [round(results[p]['v16']['mdd'] * 100, 1) for p in periods]
v14_mdds = [round(v14_results[p]['v14']['mdd'] * 100, 1) for p in periods]
v8_mdds = [round(results[p]['v8']['mdd'] * 100, 1) for p in periods]

v16_sharpes = [round(results[p]['v16']['sharpe'], 2) for p in periods]
v14_sharpes = [round(v14_results[p]['v14']['sharpe'], 2) for p in periods]

v16_cbpct = [round(results[p]['v16']['cb_pct'] * 100, 1) for p in periods]
v14_cbpct = [round(v14_results[p]['v14']['cb_pct'] * 100, 1) for p in periods]

v16_sw = [results[p]['v16']['switches'] for p in periods]
v14_sw = [v14_results[p]['v14']['switches'] for p in periods]

# 中证2000持仓占比
zz2000_pct = []
for p in periods:
    h = results[p]['v16']['holding']
    if '13' in h:
        zz2000_pct.append(round(h['13']['pct'], 2))
    else:
        zz2000_pct.append(0.0)

# 主对比表行
table_rows = []
for p in periods:
    r = results[p]
    v16, v8 = r['v16'], r['v8']
    v14 = v14_results[p]['v14']
    diff_total = (v16['total'] - v14['total']) * 100
    diff_mdd = (v16['mdd'] - v14['mdd']) * 100
    table_rows.append({
        'period': p,
        'span': f"{r['start']} ~ {r['end']}",
        'n_days': r['n_days'],
        'pool': f"{len(r['stock_ids'])}股+债",
        'v16_total': v16['total'], 'v16_ann': v16['ann'], 'v16_mdd': v16['mdd'],
        'v16_sharpe': v16['sharpe'], 'v16_sw': v16['switches'], 'v16_cbpct': v16['cb_pct'],
        'v16_fee': v16['total_fee'],
        'v14_total': v14['total'], 'v14_ann': v14['ann'], 'v14_mdd': v14['mdd'],
        'v14_sharpe': v14['sharpe'], 'v14_sw': v14['switches'], 'v14_cbpct': v14['cb_pct'],
        'v8_total': v8['total'], 'v8_mdd': v8['mdd'],
        'diff_total': diff_total, 'diff_mdd': diff_mdd,
        'zz2000_pct': zz2000_pct[len(table_rows)],
    })

def fmt_pct(x, digits=2):
    return f"{x*100:.{digits}f}%"

# V16各标的持仓占比表
holding_rows = []
for p in periods:
    r = results[p]
    h = r['v16']['holding']
    row = {'period': p, 'n_days': r['n_days']}
    all_stock_ids = r['stock_ids']
    for sid in all_stock_ids:
        sid_str = str(sid)
        if sid_str in h:
            row[names[sid]] = h[sid_str]['pct']
        else:
            row[names[sid]] = 0.0
    # 国债
    if '9' in h:
        row['国债'] = h['9']['pct']
    else:
        row['国债'] = 0.0
    holding_rows.append(row)

all_stock_names = [names[i] for i in results['近1年']['stock_ids']] + ['国债']

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>V16策略(V14+中证2000)多时段对比报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif; background:#f5f7fa; color:#333; padding:20px; }
h1 { text-align:center; font-size:24px; margin-bottom:6px; color:#1a1a2e; }
.subtitle { text-align:center; color:#666; font-size:13px; margin-bottom:24px; }
.summary-cards { display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-bottom:28px; }
.card { background:#fff; border-radius:10px; padding:16px; box-shadow:0 2px 8px rgba(0,0,0,0.06); text-align:center; }
.card h3 { font-size:14px; color:#888; margin-bottom:8px; font-weight:500; }
.card .val { font-size:22px; font-weight:700; color:#1a1a2e; }
.card .sub { font-size:11px; color:#999; margin-top:4px; }
.card.win .val { color:#e63946; }
.card.lose .val { color:#2a9d8f; }
.card.neutral .val { color:#457b9d; }
.section { background:#fff; border-radius:10px; padding:22px; margin-bottom:22px; box-shadow:0 2px 8px rgba(0,0,0,0.06); }
.section h2 { font-size:18px; margin-bottom:16px; color:#1a1a2e; border-left:4px solid #e63946; padding-left:10px; }
.chart-box { width:100%; height:380px; margin:10px 0; }
table { width:100%; border-collapse:collapse; font-size:12.5px; margin-top:10px; }
th { background:#1a1a2e; color:#fff; padding:9px 8px; text-align:center; font-weight:500; }
td { padding:8px; text-align:center; border-bottom:1px solid #eee; }
tr:hover td { background:#f8f9fa; }
.up { color:#e63946; font-weight:600; }
.down { color:#2a9d8f; font-weight:600; }
.flat { color:#666; }
.highlight { background:#fff3cd; }
.note { background:#e7f3ff; border-left:4px solid #2a9d8f; padding:14px 18px; border-radius:6px; margin-top:16px; font-size:13px; line-height:1.7; }
.warn { background:#fff3cd; border-left:4px solid #e63946; padding:14px 18px; border-radius:6px; margin-top:16px; font-size:13px; line-height:1.7; }
.tag { display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }
.tag-better { background:#fce4e4; color:#e63946; }
.tag-worse { background:#e0f2f1; color:#2a9d8f; }
.tag-same { background:#e8eaf6; color:#457b9d; }
</style>
</head>
<body>
<h1>V16 策略 (V14 5%/4% + 中证2000) 多时段对比报告</h1>
<p class="subtitle">5%/4%回撤熔断 | 手续费万分之二 | 中证2000从2014年起(近20年部分时段left join)</p>

<div class="summary-cards">'''

# 概览卡片
for i, p in enumerate(periods):
    diff = v16_totals[i] - v14_totals[i]
    cls = 'lose' if diff < -1 else ('win' if diff > 1 else 'neutral')
    tag = '<span class="tag tag-worse">收益下降</span>' if diff < -1 else ('<span class="tag tag-better">收益提升</span>' if diff > 1 else '<span class="tag tag-same">基本持平</span>')
    html += f'''
    <div class="card {cls}">
        <h3>{p}</h3>
        <div class="val">{v16_totals[i]:.0f}%</div>
        <div class="sub">V14: {v14_totals[i]:.0f}% ({diff:+.0f}pp)</div>
        <div style="margin-top:6px">{tag}</div>
    </div>'''

html += '''
</div>

<div class="section">
    <h2>核心指标对比：总收益</h2>
    <p style="font-size:13px;color:#666;margin-bottom:10px;">V16(含中证2000) vs V14(原8股) vs V8基线(含中证2000)</p>
    <div class="chart-box"><canvas id="chartTotal"></canvas></div>
</div>

<div class="section">
    <h2>核心指标对比：年化收益</h2>
    <div class="chart-box"><canvas id="chartAnn"></canvas></div>
</div>

<div class="section">
    <h2>最大回撤对比</h2>
    <div class="chart-box"><canvas id="chartMdd"></canvas></div>
</div>

<div class="section">
    <h2>详细对比表</h2>
    <table>
        <thead>
            <tr>
                <th rowspan="2">时段</th>
                <th rowspan="2">起止</th>
                <th rowspan="2">天数</th>
                <th rowspan="2">标的池</th>
                <th colspan="6">V16 (含中证2000)</th>
                <th colspan="4">V14 (对比)</th>
                <th rowspan="2">收益差<br>(V16-V14)</th>
                <th rowspan="2">中证2000<br>持仓占比</th>
            </tr>
            <tr>
                <th>总收益</th><th>年化</th><th>回撤</th><th>夏普</th><th>切换</th><th>熔断天%</th>
                <th>总收益</th><th>年化</th><th>回撤</th><th>夏普</th>
            </tr>
        </thead>
        <tbody>'''

for row in table_rows:
    diff_cls = 'down' if row['diff_total'] < -1 else ('up' if row['diff_total'] > 1 else 'flat')
    html += f'''
            <tr>
                <td><b>{row['period']}</b></td>
                <td style="font-size:11px">{row['span']}</td>
                <td>{row['n_days']}</td>
                <td>{row['pool']}</td>
                <td class="up">{fmt_pct(row['v16_total'])}</td>
                <td class="up">{fmt_pct(row['v16_ann'])}</td>
                <td class="down">{fmt_pct(row['v16_mdd'])}</td>
                <td>{row['v16_sharpe']:.2f}</td>
                <td>{row['v16_sw']}</td>
                <td>{row['v16_cbpct']*100:.1f}%</td>
                <td>{fmt_pct(row['v14_total'])}</td>
                <td>{fmt_pct(row['v14_ann'])}</td>
                <td>{fmt_pct(row['v14_mdd'])}</td>
                <td>{row['v14_sharpe']:.2f}</td>
                <td class="{diff_cls}">{row['diff_total']:+.0f}pp</td>
                <td>{row['zz2000_pct']:.2f}%</td>
            </tr>'''

html += f'''
        </tbody>
    </table>
</div>

<div class="section">
    <h2>中证2000在各时段的持仓占比</h2>
    <div class="chart-box" style="height:300px"><canvas id="chartZZ2000"></canvas></div>
    <table style="margin-top:16px">
        <thead><tr><th>时段</th><th>中证2000持仓天数</th><th>中证2000持仓占比</th><th>V16总切换次数</th><th>V14总切换次数</th></tr></thead>
        <tbody>'''

for i, p in enumerate(periods):
    r = results[p]
    h = r['v16']['holding']
    days = h.get('13', {}).get('days', 0)
    html += f'''
            <tr>
                <td><b>{p}</b></td>
                <td>{days}天</td>
                <td class="up">{zz2000_pct[i]:.2f}%</td>
                <td>{v16_sw[i]}</td>
                <td>{v14_sw[i]}</td>
            </tr>'''

html += '''
        </tbody>
    </table>
</div>

<div class="section">
    <h2>V16 各标的持仓占比明细</h2>
    <table>
        <thead><tr><th>时段</th>'''

for sn in all_stock_names:
    html += f'<th>{sn}</th>'
html += '</tr></thead><tbody>'

for row in holding_rows:
    html += f'<tr><td><b>{row["period"]}</b></td>'
    for sn in all_stock_names:
        v = row.get(sn, 0)
        if v > 0:
            cls = 'highlight' if sn == '中证2000' else ''
            html += f'<td class="{cls}">{v:.2f}%</td>'
        else:
            html += '<td style="color:#ccc">0%</td>'
    html += '</tr>'

html += '''
        </tbody>
    </table>
    <p style="font-size:12px;color:#888;margin-top:8px;">黄色高亮 = 中证2000列</p>
</div>

<div class="section">
    <h2>结论</h2>
    <div class="warn">
        <b>⚠️ 加入中证2000后，5个时段收益全部下降或持平</b><br><br>
        <b>1. 收益全面落后</b> — 近20年 -7819pp、近10年 -270pp、近5年 -119pp、近3年 -58pp、近1年 -1pp。<br>
        <b>2. 中证2000实际被选中天数极少</b> — 近20年仅3.38%、近10年5.03%、近5年3.57%、近3年2.05%、近1年0%。即便占比这么低，仍显著拉低整体收益。<br>
        <b>3. 根本原因：扰动熔断机制</b> — 中证2000的加入改变了V8基线净值的走势（原始信号选中标的不同），导致基线净值的高点和回撤路径与V14不同，熔断触发/解除时点随之改变，更多时间在避险。<br>
        <b>4. 回撤控制依然优秀</b> — V16回撤都在-4%~-6%以内，5%/4%熔断机制本身稳健，只是收益端受损。<br><br>
        <b>结论：不建议加入中证2000。</b> 这与V15加入海外指数的结论一致，再次证明"标的池越大越好"是错误直觉——新增标的会通过改变基线净值走势扰动熔断机制的工作节奏，需要谨慎测试。
    </div>
</div>

<script>
const periods = ''' + str(periods) + ''';
const v16Totals = ''' + str(v16_totals) + ''';
const v14Totals = ''' + str(v14_totals) + ''';
const v8Totals = ''' + str(v8_totals) + ''';
const v16Anns = ''' + str(v16_anns) + ''';
const v14Anns = ''' + str(v14_anns) + ''';
const v8Anns = ''' + str(v8_anns) + ''';
const v16Mdds = ''' + str(v16_mdds) + ''';
const v14Mdds = ''' + str(v14_mdds) + ''';
const v8Mdds = ''' + str(v8_mdds) + ''';
const zz2000Pct = ''' + str(zz2000_pct) + ''';

Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, Microsoft YaHei, sans-serif';
Chart.defaults.font.size = 12;

// 总收益
new Chart(document.getElementById('chartTotal'), {
    type: 'bar',
    data: {
        labels: periods,
        datasets: [
            {label:'V16 (含中证2000)', data: v16Totals, backgroundColor:'#e63946', borderColor:'#c1121f', borderWidth:1},
            {label:'V14 (原8股)', data: v14Totals, backgroundColor:'#457b9d', borderColor:'#1d3557', borderWidth:1},
            {label:'V8 基线', data: v8Totals, backgroundColor:'#a8dadc', borderColor:'#457b9d', borderWidth:1},
        ]
    },
    options: {
        responsive:true, maintainAspectRatio:false,
        plugins:{ title:{display:true,text:'总收益对比 (%)', font:{size:15}} },
        scales:{ y:{beginAtZero:true, ticks:{callback:v=>v+'%'}} }
    }
});

// 年化
new Chart(document.getElementById('chartAnn'), {
    type: 'bar',
    data: {
        labels: periods,
        datasets: [
            {label:'V16 (含中证2000)', data: v16Anns, backgroundColor:'#e63946'},
            {label:'V14 (原8股)', data: v14Anns, backgroundColor:'#457b9d'},
            {label:'V8 基线', data: v8Anns, backgroundColor:'#a8dadc'},
        ]
    },
    options: {
        responsive:true, maintainAspectRatio:false,
        plugins:{ title:{display:true,text:'年化收益对比 (%)', font:{size:15}} },
        scales:{ y:{beginAtZero:true, ticks:{callback:v=>v+'%'}} }
    }
});

// 回撤
new Chart(document.getElementById('chartMdd'), {
    type: 'bar',
    data: {
        labels: periods,
        datasets: [
            {label:'V16 (含中证2000)', data: v16Mdds, backgroundColor:'#2a9d8f'},
            {label:'V14 (原8股)', data: v14Mdds, backgroundColor:'#457b9d'},
            {label:'V8 基线', data: v8Mdds, backgroundColor:'#e76f51'},
        ]
    },
    options: {
        responsive:true, maintainAspectRatio:false,
        plugins:{ title:{display:true,text:'最大回撤对比 (%)', font:{size:15}} },
        scales:{ y:{ ticks:{callback:v=>v+'%'} } }
    }
});

// 中证2000占比
new Chart(document.getElementById('chartZZ2000'), {
    type: 'bar',
    data: {
        labels: periods,
        datasets: [{
            label:'中证2000持仓占比',
            data: zz2000Pct,
            backgroundColor:'#e9c46a',
            borderColor:'#e76f51',
            borderWidth:1
        }]
    },
    options: {
        responsive:true, maintainAspectRatio:false,
        plugins:{ title:{display:true,text:'中证2000在各时段的持仓占比 (%)', font:{size:15}} },
        scales:{ y:{beginAtZero:true, ticks:{callback:v=>v+'%'}} }
    }
});
</script>
</body>
</html>'''

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/V16策略多时段对比报告.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("报告已生成: V16策略多时段对比报告.html")
print(f"文件大小: {len(html)} 字符")
