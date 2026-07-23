# -*- coding: utf-8 -*-
"""生成V14(5%/4%)近1年操作明细HTML报告"""
import json
from collections import Counter

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_detail_1y.json','r',encoding='utf-8') as f:
    data = json.load(f)

switches = data['switches']
daily = data['daily_records']

COLORS = {'上证50':'#1e88e5','创业板50':'#43a047','纳斯达克100':'#ff9800','沪深300':'#00acc1','中证500':'#8e24aa','中证1000':'#ec407a','标普500':'#f57c00','科创50':'#00897b','国债':'#757575','空仓':'#bdbdbd'}

# 切换明细表
switch_rows = ''
for idx, s in enumerate(switches):
    bf_cells = ''
    for name in ['上证50','创业板50','纳斯达克100','沪深300','中证500','中证1000','标普500','科创50']:
        v = s['bf_values'].get(name, '—')
        is_top = (name == s['to'])
        cls = 'bf-top' if is_top else ''
        bf_cells += f'<td class="{cls}">{v:+.4f}</td>' if isinstance(v, float) else f'<td>{v}</td>'

    from_color = COLORS.get(s['from'], '#999')
    to_color = COLORS.get(s['to'], '#999')

    # 行样式：按切换类型
    st = s['switch_type']
    if st == '熔断触发':
        row_class = 'switch-cb-trigger'
        type_badge = '<span class="badge badge-trigger">熔断触发</span>'
    elif st == '熔断解除':
        row_class = 'switch-cb-release'
        type_badge = '<span class="badge badge-release">熔断解除</span>'
    elif st == '建仓':
        row_class = 'switch-init'
        type_badge = '<span class="badge badge-init">建仓</span>'
    elif st == '避险':
        row_class = 'switch-bond'
        type_badge = '<span class="badge badge-bond">避险</span>'
    else:
        row_class = ''
        type_badge = '<span class="badge badge-rot">轮动</span>'

    period_ret = s.get('period_ret')
    if period_ret is None:
        period_cell = '<td class="muted">—</td>'
    else:
        period_cell = f'<td class="{"pos" if period_ret>=0 else "neg"}">{period_ret:+.2%}</td>'

    dd = s['raw_dd']
    dd_cls = 'neg' if dd < -0.05 else ('warn' if dd < -0.04 else 'normal')

    switch_rows += f'''<tr class="{row_class}">
        <td class="idx">{idx+1}</td>
        <td class="date">{s['date']}</td>
        <td>{type_badge}</td>
        <td><span class="tag" style="background:{from_color}">{s['from']}</span></td>
        <td>→</td>
        <td><span class="tag" style="background:{to_color}">{s['to']}</span></td>
        <td class="{dd_cls}">{dd*100:+.2f}%</td>
        {bf_cells}
        <td class="cost">{s['cost']*10000:.0f}‱</td>
        <td class="nav">{s['nav_after']:.4f}</td>
        <td class="{'pos' if s['ret']>=0 else 'neg'}">{s['ret']:+.2%}</td>
        {period_cell}
        <td class="reason">{s['reason']}</td>
    </tr>'''

# 最后一段：持有至今
last_nav = daily[-1]['nav']
last_ret = data['last_period_ret']
last_asset = switches[-1]['to']
last_color = COLORS.get(last_asset, '#999')
switch_rows += f'''<tr class="switch-hold">
    <td class="idx">—</td>
    <td class="date">{switches[-1]['date']}→{data['end_date']}</td>
    <td><span class="badge badge-hold">持有至今</span></td>
    <td><span class="tag" style="background:{last_color}">{last_asset}</span></td>
    <td>持有</td>
    <td>至今</td>
    <td colspan="11" style="color:#999;font-size:11px;">持有 {last_asset} 至今（未调仓）</td>
    <td class="nav">{last_nav:.4f}</td>
    <td>—</td>
    <td class="{'pos' if last_ret>=0 else 'neg'}">{last_ret:+.2%}</td>
    <td>—</td>
</tr>'''

# 每日持仓记录（关键节点）
daily_filtered = []
for i, d in enumerate(daily):
    is_switch = d['is_switch']
    is_month_start = (i == 0) or (i > 0 and daily[i-1]['date'][5:7] != d['date'][5:7])
    is_last = (i == len(daily) - 1)
    if is_switch or is_month_start or is_last:
        daily_filtered.append(d)

daily_rows = ''
for d in daily_filtered:
    pos_color = COLORS.get(d['position'], '#999')
    switch_badge = '<span class="switch-badge">切换</span>' if d['is_switch'] else ''
    bf_cells = ''
    for name in ['上证50','创业板50','纳斯达克100','沪深300','中证500','中证1000','标普500','科创50']:
        v = d['bf'].get(name, 0)
        is_pos = (name == d['position'])
        cls = 'bf-top' if is_pos else ''
        bf_cells += f'<td class="{cls}">{v:+.4f}</td>'
    # 熔断状态badge
    cb = d.get('cb_status', 'NORMAL')
    if cb == 'TRIGGERED':
        cb_badge = '<span class="cb-tag cb-trig">⚡触发</span>'
    elif cb == 'IN_CB':
        cb_badge = '<span class="cb-tag cb-in">⏸熔断中</span>'
    elif cb == 'RELEASED':
        cb_badge = '<span class="cb-tag cb-rel">✓解除</span>'
    else:
        cb_badge = '<span class="cb-tag cb-normal">正常</span>'

    dd_val = d.get('raw_dd', 0)
    dd_cls = 'neg' if dd_val < -0.05 else ('warn' if dd_val < -0.04 else 'normal')

    daily_rows += f'''<tr>
        <td class="date">{d['date']}</td>
        <td><span class="tag-sm" style="background:{pos_color}">{d['position']}</span> {switch_badge}</td>
        <td>{cb_badge}</td>
        <td style="color:#999;font-size:11px;">→ {d['signal']}</td>
        <td class="{dd_cls}">{dd_val*100:+.2f}%</td>
        {bf_cells}
        <td class="{'pos' if d['ret']>=0 else 'neg'}">{d['ret']:+.2%}</td>
        <td class="cost">{d['cost']*10000:.0f}‱</td>
        <td class="nav">{d['nav']:.4f}</td>
    </tr>'''

# 持仓分布
hold_pct = data['hold_pct']
hold_bars = ''
for name in ['国债','创业板50','科创50','中证500','纳斯达克100','标普500','中证1000','上证50','沪深300','空仓']:
    p = hold_pct.get(name, 0)
    if p > 0:
        hold_bars += f'<div style="width:{p*100}%;background:{COLORS.get(name,"#999")};">{name} {p:.0%}</div>'

# 切换类型统计
type_counts = data['type_counts']
type_html = ''
for t in ['建仓','轮动','避险','熔断触发','熔断解除']:
    cnt = type_counts.get(t, 0)
    if cnt > 0:
        if t == '熔断触发':
            badge = '<span class="badge badge-trigger">熔断触发</span>'
        elif t == '熔断解除':
            badge = '<span class="badge badge-release">熔断解除</span>'
        elif t == '建仓':
            badge = '<span class="badge badge-init">建仓</span>'
        elif t == '避险':
            badge = '<span class="badge badge-bond">避险</span>'
        else:
            badge = '<span class="badge badge-rot">轮动</span>'
        type_html += f'<tr><td>{badge}</td><td class="pos">{cnt}</td><td>{cnt/data["total_switches"]*100:.0f}%</td></tr>'

# 熔断事件时间线
cb_events = data['cb_events']
cb_timeline = ''
for ev in cb_events:
    cls = 'ev-trigger' if ev['event'] == 'TRIGGER' else 'ev-release'
    icon = '⚡' if ev['event'] == 'TRIGGER' else '✓'
    label = '触发熔断' if ev['event'] == 'TRIGGER' else '解除熔断'
    cb_timeline += f'''<div class="cb-event {cls}">
        <span class="ev-date">{ev['date']}</span>
        <span class="ev-icon">{icon}</span>
        <span class="ev-label">{label}</span>
        <span class="ev-detail">回撤 {ev['dd']*100:.2f}% · {ev['from']} → {ev['to']}</span>
    </div>'''

data_json = json.dumps({
    'dates': [d['date'] for d in daily],
    'strat_nav': [d['nav'] for d in daily],
    'raw_nav': [d['raw_nav'] for d in daily],
    'positions': [d['pos_id'] for d in daily],
    'raw_dd': [d['raw_dd'] for d in daily],
    'cb_status': [d.get('cb_status', 'NORMAL') for d in daily],
}, ensure_ascii=False)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14策略(5%/4%阈值)近1年操作明细</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
    background:#f5f7fa; color:#1a1a2e; line-height:1.6; padding:20px; max-width:1500px; margin:0 auto; }}
  h1 {{ font-size:24px; margin-bottom:4px; }}
  .subtitle {{ color:#666; font-size:13px; margin-bottom:20px; }}
  .card {{ background:#fff; border-radius:12px; padding:20px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }}
  .card h2 {{ font-size:17px; margin-bottom:14px; border-left:4px solid #e74c3c; padding-left:10px; }}
  .stats-grid {{ display:grid; grid-template-columns:repeat(6,1fr); gap:12px; margin-bottom:8px; }}
  .stat {{ background:#f8f9fb; border-radius:8px; padding:12px; text-align:center; }}
  .stat .label {{ font-size:11px; color:#888; margin-bottom:4px; }}
  .stat .value {{ font-size:18px; font-weight:700; }}
  .stat .value.pos {{ color:#d32f2f; }}
  .stat .value.neg {{ color:#2e7d32; }}
  .stat .value.warn {{ color:#f57c00; }}
  .pos-bar {{ display:flex; height:28px; border-radius:6px; overflow:hidden; margin-top:8px; font-size:10px; }}
  .pos-bar div {{ display:flex; align-items:center; justify-content:center; color:#fff; font-weight:600; padding:0 4px; }}
  .table-wrap {{ overflow-x:auto; }}
  table {{ border-collapse:collapse; font-size:11px; width:100%; }}
  th {{ background:#f0f2f5; padding:8px 6px; text-align:center; font-weight:600; color:#555; white-space:nowrap; position:sticky; top:0; }}
  th.bf-group {{ background:#e8eaf6; }}
  td {{ padding:7px 6px; text-align:center; border-bottom:1px solid #eee; white-space:nowrap; }}
  td.idx {{ color:#999; font-size:10px; }}
  td.date {{ font-weight:600; color:#333; }}
  td.bf-top {{ background:#fff8e1; font-weight:700; color:#e65100; }}
  td.cost {{ color:#888; font-size:10px; }}
  td.nav {{ font-family:monospace; color:#555; }}
  td.pos {{ color:#d32f2f; font-weight:600; }}
  td.neg {{ color:#2e7d32; font-weight:600; }}
  td.warn {{ color:#f57c00; font-weight:600; }}
  td.normal {{ color:#666; }}
  td.reason {{ font-size:10px; color:#888; text-align:left; max-width:200px; white-space:normal; }}
  tr.switch-cb-trigger {{ background:#ffebee; }}
  tr.switch-cb-trigger td:nth-child(6) .tag {{ box-shadow:0 0 0 2px #c62828; }}
  tr.switch-cb-release {{ background:#e8f5e9; }}
  tr.switch-cb-release td:nth-child(6) .tag {{ box-shadow:0 0 0 2px #2e7d32; }}
  tr.switch-bond {{ background:#fafafa; }}
  tr.switch-init {{ background:#e3f2fd; }}
  tr.switch-hold {{ background:#f3e5f5; font-style:italic; }}
  td.muted {{ color:#ccc; }}
  .tag {{ display:inline-block; padding:2px 8px; border-radius:4px; color:#fff; font-size:10px; font-weight:600; }}
  .tag-sm {{ display:inline-block; padding:1px 6px; border-radius:3px; color:#fff; font-size:10px; font-weight:600; }}
  .switch-badge {{ display:inline-block; background:#e53935; color:#fff; font-size:9px; padding:1px 5px; border-radius:3px; margin-left:4px; }}
  .badge {{ display:inline-block; padding:2px 6px; border-radius:3px; color:#fff; font-size:10px; font-weight:600; }}
  .badge-trigger {{ background:#c62828; }}
  .badge-release {{ background:#2e7d32; }}
  .badge-init {{ background:#1976d2; }}
  .badge-bond {{ background:#757575; }}
  .badge-rot {{ background:#7b1fa2; }}
  .badge-hold {{ background:#6a1b9a; }}
  .cb-tag {{ display:inline-block; padding:1px 5px; border-radius:3px; font-size:9px; font-weight:600; }}
  .cb-trig {{ background:#c62828; color:#fff; }}
  .cb-in {{ background:#ef9a9a; color:#fff; }}
  .cb-rel {{ background:#2e7d32; color:#fff; }}
  .cb-normal {{ background:#e0e0e0; color:#666; }}
  .legend {{ font-size:11px; color:#888; margin-top:8px; }}
  .grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  .chart-container {{ position:relative; height:320px; margin-top:8px; }}
  .note {{ background:#fff4e5; border:1px solid #ff9800; border-radius:8px; padding:12px; font-size:12px; color:#e65100; margin-top:12px; }}
  .cb-timeline {{ display:flex; flex-direction:column; gap:6px; max-height:280px; overflow-y:auto; padding-right:6px; }}
  .cb-event {{ display:flex; align-items:center; gap:10px; padding:6px 10px; border-radius:6px; font-size:12px; }}
  .ev-trigger {{ background:#ffebee; border-left:3px solid #c62828; }}
  .ev-release {{ background:#e8f5e9; border-left:3px solid #2e7d32; }}
  .ev-date {{ font-weight:600; color:#333; min-width:90px; }}
  .ev-icon {{ font-size:14px; }}
  .ev-label {{ font-weight:600; min-width:60px; }}
  .ev-detail {{ color:#666; font-size:11px; }}
</style>
</head>
<body>

<h1>V14策略（5%/4%阈值）近1年操作明细</h1>
<p class="subtitle">{data['start_date']} ~ {data['end_date']} | {data['n_days']}个交易日 | 八指数轮动+国债避险+5%/4%回撤熔断 | 手续费万分之二/单边</p>

<div class="card">
  <h2>核心数据概览</h2>
  <div class="stats-grid">
    <div class="stat"><div class="label">总收益率</div><div class="value pos">{data['strat_total']*100:.2f}%</div></div>
    <div class="stat"><div class="label">年化收益</div><div class="value pos">{data['strat_ann']*100:.2f}%</div></div>
    <div class="stat"><div class="label">夏普比率</div><div class="value pos">{data['strat_sharpe']:.2f}</div></div>
    <div class="stat"><div class="label">最大回撤</div><div class="value neg">{data['strat_mdd']*100:.2f}%</div></div>
    <div class="stat"><div class="label">切换次数</div><div class="value">{data['total_switches']}</div></div>
    <div class="stat"><div class="label">累计手续费</div><div class="value neg">{data['total_fee']*100:.2f}%</div></div>
  </div>
  <div class="stats-grid" style="grid-template-columns:repeat(4,1fr); margin-top:8px;">
    <div class="stat"><div class="label">熔断触发次数</div><div class="value warn">{data['cb_trigger_count']}</div></div>
    <div class="stat"><div class="label">熔断解除次数</div><div class="value warn">{data['cb_release_count']}</div></div>
    <div class="stat"><div class="label">熔断天数</div><div class="value warn">{data['cb_days']}</div></div>
    <div class="stat"><div class="label">熔断占比</div><div class="value warn">{data['cb_pct']*100:.1f}%</div></div>
  </div>
  <p style="font-size:12px;color:#666;margin-top:12px;margin-bottom:4px;">持仓分布：</p>
  <div class="pos-bar">{hold_bars}</div>
</div>

<div class="card">
  <h2>策略净值 vs V8基线净值 + 回撤 + 熔断状态</h2>
  <div class="chart-container"><canvas id="navChart"></canvas></div>
  <p class="legend">红线 = V14(5%/4%)策略净值 | 灰线 = V8基线净值 | 橙线 = 策略回撤 | 红色背景 = 熔断状态</p>
</div>

<div class="grid-2">
  <div class="card">
    <h2>切换类型统计</h2>
    <table>
      <thead><tr><th>类型</th><th>次数</th><th>占比</th></tr></thead>
      <tbody>{type_html}</tbody>
    </table>
  </div>
  <div class="card">
    <h2>熔断事件时间线（{len(cb_events)}次）</h2>
    <div class="cb-timeline">{cb_timeline}</div>
  </div>
</div>

<div class="card">
  <h2>全部切换操作明细（{data['total_switches']}次）</h2>
  <p style="font-size:12px;color:#888;margin-bottom:10px;">
    黄色高亮 = 当次买入资产 | <b>决策依据bf</b> = <b>前一日收盘后</b>计算的各指数买入因子（close/MA20-1），即真正决定本次切换的依据（T日持仓由T-1日信号决定，次日开盘执行）<br>
    <b>回撤</b> = V8基线策略当时距历史高点的回撤 | <b>区间收益</b> = 上次调仓→本次调仓持有资产的累计收益（含手续费）<br>
    红底 = 熔断触发 | 绿底 = 熔断解除 | 蓝底 = 初始建仓 | 灰底 = 避险转国债 | 紫底 = 持有至今
  </p>
  <div class="table-wrap" style="max-height:700px;overflow-y:auto;">
  <table>
    <thead>
      <tr>
        <th>#</th><th>日期</th><th>类型</th><th>从</th><th></th><th>买入</th><th>回撤</th>
        <th class="bf-group" colspan="8">决策依据bf（前日收盘 close/MA20-1）</th>
        <th>手续费</th><th>切换后净值</th><th>当日收益</th><th>区间收益</th><th>原因</th>
      </tr>
      <tr>
        <th colspan="7"></th>
        <th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th>
        <th colspan="5"></th>
      </tr>
    </thead>
    <tbody>{switch_rows}</tbody>
  </table>
  </div>
</div>

<div class="card">
  <h2>每日持仓记录（切换日 + 月初 + 末日）</h2>
  <p style="font-size:12px;color:#888;margin-bottom:10px;">仅展示关键节点。回撤列展示V8基线当时距高点的回撤；熔断状态列展示当日熔断机状态</p>
  <div class="table-wrap" style="max-height:600px;overflow-y:auto;">
  <table>
    <thead>
      <tr>
        <th>日期</th><th>实际持仓</th><th>熔断状态</th><th>V8信号</th><th>回撤</th>
        <th class="bf-group" colspan="8">各指数买入因子</th>
        <th>当日收益</th><th>手续费</th><th>净值</th>
      </tr>
      <tr>
        <th colspan="5"></th>
        <th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th>
        <th colspan="3"></th>
      </tr>
    </thead>
    <tbody>{daily_rows}</tbody>
  </table>
  </div>
</div>

<div class="note">
  ℹ️ <b>策略说明</b>：在V8八指数轮动基础上，加入5%/4%回撤熔断机制。<br>
  ① <b>原始信号</b>：每日收盘后计算8个股票指数的买入因子（close/MA20-1），持有因子最高的；若全部跌破MA20则买国债。<br>
  ② <b>熔断机制</b>：跟踪V8基线策略净值距历史高点的回撤，<b>回撤>5%强制转国债</b>（即使有更优信号）；<b>回撤<4%时解除熔断</b>恢复V8信号。<br>
  ③ <b>决策时序（重要）</b>：T日收盘后计算bf→确定信号；<b>T+1日开盘价执行</b>买卖（扣万分之二手续费/单边）。因此切换明细表的"决策依据bf"列展示的是<b>前一日收盘</b>的bf值，而非切换当日的bf。<br>
  ④ 上表"回撤"列指V8基线净值当时距历史高点的回撤幅度，是熔断判断的依据。<br>
  ⑤ <b>区间收益</b>列：从上次调仓到本次调仓这段时间内，持有原资产的累计收益率（含手续费影响）。
</div>

<script>
const D = {data_json};
Chart.defaults.font.family="'PingFang SC','Microsoft YaHei',sans-serif";
Chart.defaults.font.size=11;

const COLORS = {{1:'#1e88e5',2:'#43a047',3:'#ff9800',4:'#00acc1',5:'#8e24aa',6:'#ec407a',7:'#f57c00',8:'#00897b',9:'#757575',0:'#bdbdbd'}};

// 净值曲线 + 回撤 + 熔断背景
const ctx = document.getElementById('navChart').getContext('2d');

// 准备熔断背景区域
const cbBands = [];
let inBand = false;
let bandStart = null;
for (let i = 0; i < D.dates.length; i++) {{
    const isCB = D.cb_status[i] === 'TRIGGERED' || D.cb_status[i] === 'IN_CB';
    if (isCB && !inBand) {{
        inBand = true; bandStart = i;
    }} else if (!isCB && inBand) {{
        cbBands.push([bandStart, i-1]);
        inBand = false;
    }}
}}
if (inBand) cbBands.push([bandStart, D.dates.length-1]);

// 用 annotation plugin 简单实现：自定义plugin画背景
const cbBgPlugin = {{
    id: 'cbBackground',
    beforeDatasetsDraw(chart) {{
        const ctx = chart.ctx;
        const xScale = chart.scales.x;
        const yScale = chart.scales.y;
        cbBands.forEach(([s, e]) => {{
            const x1 = xScale.getPixelForValue(s);
            const x2 = xScale.getPixelForValue(e);
            ctx.save();
            ctx.fillStyle = 'rgba(198, 40, 40, 0.10)';
            ctx.fillRect(x1, yScale.top, x2-x1, yScale.bottom-yScale.top);
            ctx.restore();
        }});
    }}
}};

new Chart(ctx, {{
    type: 'line',
    data: {{
        labels: D.dates,
        datasets: [
            {{
                label: 'V14策略净值 (5%/4%)',
                data: D.strat_nav,
                borderColor: '#c62828',
                backgroundColor: 'rgba(198,40,40,0.1)',
                borderWidth: 2.5,
                pointRadius: 0,
                tension: 0,
                yAxisID: 'y',
                fill: false,
            }},
            {{
                label: 'V8基线净值',
                data: D.raw_nav,
                borderColor: '#9e9e9e',
                borderWidth: 1.2,
                pointRadius: 0,
                tension: 0,
                yAxisID: 'y',
                fill: false,
                borderDash: [4, 2],
            }},
            {{
                label: '策略回撤 (右轴)',
                data: D.raw_dd.map(v => v*100),
                borderColor: '#ff9800',
                borderWidth: 1.2,
                pointRadius: 0,
                tension: 0,
                yAxisID: 'y1',
                fill: false,
            }},
            // 熔断阈值线
            {{
                label: '5%触发线',
                data: D.dates.map(() => -5),
                borderColor: 'rgba(198,40,40,0.5)',
                borderWidth: 1,
                borderDash: [3,3],
                pointRadius: 0,
                yAxisID: 'y1',
                fill: false,
            }},
            {{
                label: '4%解除线',
                data: D.dates.map(() => -4),
                borderColor: 'rgba(46,125,50,0.5)',
                borderWidth: 1,
                borderDash: [3,3],
                pointRadius: 0,
                yAxisID: 'y1',
                fill: false,
            }}
        ]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
            legend: {{ position: 'top', labels: {{ boxWidth: 12, font: {{size: 11}} }} }},
            tooltip: {{
                callbacks: {{
                    label: function(ctx) {{
                        const i = ctx.dataIndex;
                        const nav = ctx.datasetIndex === 0 ? 'V14净值 ' + D.strat_nav[i].toFixed(4) :
                                    ctx.datasetIndex === 1 ? 'V8净值 ' + D.raw_nav[i].toFixed(4) :
                                    ctx.datasetIndex === 2 ? '回撤 ' + (D.raw_dd[i]*100).toFixed(2) + '%' : null;
                        return nav;
                    }},
                    afterBody: function(items) {{
                        const i = items[0].dataIndex;
                        const cb = D.cb_status[i];
                        const cbText = cb === 'TRIGGERED' ? '⚡触发熔断' :
                                       cb === 'IN_CB' ? '⏸熔断中（持国债）' :
                                       cb === 'RELEASED' ? '✓解除熔断' : '正常运行';
                        return [cbText];
                    }}
                }}
            }}
        }},
        scales: {{
            x: {{ ticks: {{ maxTicksLimit: 12, autoSkip: true }} }},
            y: {{
                position: 'left',
                title: {{ display: true, text: '净值' }},
                grid: {{ color: '#ecf0f1' }}
            }},
            y1: {{
                position: 'right',
                title: {{ display: true, text: '回撤 (%)' }},
                grid: {{ drawOnChartArea: false }},
                min: -30, max: 5,
            }}
        }}
    }},
    plugins: [cbBgPlugin]
}});
</script>

</body>
</html>
'''

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/V14策略5_4阈值近1年操作明细.html','w',encoding='utf-8') as f:
    f.write(html)

print(f"HTML报告已生成: V14策略5_4阈值近1年操作明细.html")
print(f"文件大小: {len(html):,} 字符")
