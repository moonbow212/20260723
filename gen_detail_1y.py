# -*- coding: utf-8 -*-
"""生成V8近1年操作明细HTML报告"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v8_detail_1y.json','r',encoding='utf-8') as f:
    data = json.load(f)

switches = data['switches']
daily = data['daily_records']

# 颜色映射
COLORS = {'上证50':'#1e88e5','创业板50':'#43a047','纳斯达克100':'#ff9800','沪深300':'#00acc1','中证500':'#8e24aa','中证1000':'#ec407a','标普500':'#f57c00','科创50':'#00897b','国债':'#757575','空仓':'#bdbdbd'}

# 构建切换明细表行
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
    is_bond = s['to'] == '国债'
    row_class = 'switch-bond' if is_bond else ('switch-init' if s['from'] == '空仓' else '')
    
    period_ret = s.get('period_ret')
    if period_ret is None:
        period_cell = '<td class="muted">—</td>'
    else:
        period_cell = f'<td class="{"pos" if period_ret>=0 else "neg"}">{period_ret:+.2%}</td>'
    
    switch_rows += f'''<tr class="{row_class}">
        <td class="idx">{idx+1}</td>
        <td class="date">{s['date']}</td>
        <td><span class="tag" style="background:{from_color}">{s['from']}</span></td>
        <td>→</td>
        <td><span class="tag" style="background:{to_color}">{s['to']}</span></td>
        {bf_cells}
        <td class="cost">{s['cost']*10000:.0f}‱</td>
        <td class="nav">{s['nav_after']:.4f}</td>
        <td class="{'pos' if s['ret']>=0 else 'neg'}">{s['ret']:+.2%}</td>
        {period_cell}
    </tr>'''

# 最后一段：持有至今
last_nav = daily[-1]['nav']
last_ret = data['last_period_ret']
last_asset = switches[-1]['to']
last_color = COLORS.get(last_asset, '#999')
switch_rows += f'''<tr class="switch-hold">
    <td class="idx">—</td>
    <td class="date">{switches[-1]['date']}→{data['end_date']}</td>
    <td><span class="tag" style="background:{last_color}">{last_asset}</span></td>
    <td>持有</td>
    <td>至今</td>
    <td colspan="8" style="color:#999;font-size:11px;">持有 {last_asset} 至今（未调仓）</td>
    <td>—</td>
    <td class="nav">{last_nav:.4f}</td>
    <td>—</td>
    <td class="{'pos' if last_ret>=0 else 'neg'}">{last_ret:+.2%}</td>
</tr>'''

# 构建每日持仓记录（只显示切换日 + 每月首个交易日 + 最后一天）
# 为了不太多，显示所有切换日及其前后各1天
switch_dates = set(s['date'] for s in switches)
daily_filtered = []
for i, d in enumerate(daily):
    # 显示切换日，或每月第一天，或最后一天
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
    daily_rows += f'''<tr>
        <td class="date">{d['date']}</td>
        <td><span class="tag-sm" style="background:{pos_color}">{d['position']}</span> {switch_badge}</td>
        <td style="color:#999;font-size:11px;">→ {d['signal']}</td>
        {bf_cells}
        <td class="{'pos' if d['ret']>=0 else 'neg'}">{d['ret']:+.2%}</td>
        <td class="cost">{d['cost']*10000:.0f}‱</td>
        <td class="nav">{d['nav']:.4f}</td>
    </tr>'''

# 持仓分布
hold_pct = data['hold_pct']
hold_bars = ''
total = sum(hold_pct.values())
for name in ['创业板50','科创50','中证500','国债','纳斯达克100','标普500','中证1000','上证50','沪深300','空仓']:
    p = hold_pct.get(name, 0)
    if p > 0:
        hold_bars += f'<div style="width:{p*100}%;background:{COLORS.get(name,"#999")};">{name} {p:.0%}</div>'

# 切换统计
from collections import Counter
switch_pairs = Counter()
for s in switches:
    switch_pairs[f"{s['from']}→{s['to']}"] += 1
pair_stats = sorted(switch_pairs.items(), key=lambda x: -x[1])[:10]
pair_html = ''
for pair, cnt in pair_stats:
    pair_html += f'<tr><td>{pair}</td><td class="pos">{cnt}</td></tr>'

# 按资产统计切换次数
asset_switches = {'上证50':0,'创业板50':0,'纳斯达克100':0,'沪深300':0,'中证500':0,'中证1000':0,'标普500':0,'科创50':0,'国债':0}
for s in switches:
    asset_switches[s['to']] = asset_switches.get(s['to'], 0) + 1
asset_html = ''
for name in ['创业板50','科创50','中证500','纳斯达克100','标普500','中证1000','上证50','国债','沪深300']:
    cnt = asset_switches.get(name, 0)
    if cnt > 0:
        asset_html += f'<tr><td><span class="tag-sm" style="background:{COLORS[name]}">{name}</span></td><td class="pos">{cnt}</td><td>{cnt/len(switches)*100:.0f}%</td></tr>'

data_json = json.dumps({
    'dates': [d['date'] for d in daily],
    'strat_nav': [d['nav'] for d in daily],
    'positions': [d['pos_id'] for d in daily],
}, ensure_ascii=False)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V8策略近1年操作明细</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
    background:#f5f7fa; color:#1a1a2e; line-height:1.6; padding:20px; max-width:1400px; margin:0 auto; }}
  h1 {{ font-size:24px; margin-bottom:4px; }}
  .subtitle {{ color:#666; font-size:13px; margin-bottom:20px; }}
  .card {{ background:#fff; border-radius:12px; padding:20px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }}
  .card h2 {{ font-size:17px; margin-bottom:14px; border-left:4px solid #4f6df5; padding-left:10px; }}
  .stats-grid {{ display:grid; grid-template-columns:repeat(6,1fr); gap:12px; margin-bottom:8px; }}
  .stat {{ background:#f8f9fb; border-radius:8px; padding:12px; text-align:center; }}
  .stat .label {{ font-size:11px; color:#888; margin-bottom:4px; }}
  .stat .value {{ font-size:18px; font-weight:700; }}
  .stat .value.pos {{ color:#d32f2f; }}
  .stat .value.neg {{ color:#2e7d32; }}
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
  tr.switch-bond {{ background:#fafafa; }}
  tr.switch-bond td:nth-child(5) .tag {{ box-shadow:0 0 0 2px #757575; }}
  tr.switch-init {{ background:#e3f2fd; }}
  tr.switch-hold {{ background:#f3e5f5; font-style:italic; }}
  td.muted {{ color:#ccc; }}
  .tag {{ display:inline-block; padding:2px 8px; border-radius:4px; color:#fff; font-size:10px; font-weight:600; }}
  .tag-sm {{ display:inline-block; padding:1px 6px; border-radius:3px; color:#fff; font-size:10px; font-weight:600; }}
  .switch-badge {{ display:inline-block; background:#e53935; color:#fff; font-size:9px; padding:1px 5px; border-radius:3px; margin-left:4px; }}
  .legend {{ font-size:11px; color:#888; margin-top:8px; }}
  .grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  .chart-container {{ position:relative; height:300px; margin-top:8px; }}
  .note {{ background:#e3f2fd; border:1px solid #64b5f6; border-radius:8px; padding:12px; font-size:12px; color:#1565c0; margin-top:12px; }}
</style>
</head>
<body>

<h1>V8策略近1年操作明细</h1>
<p class="subtitle">{data['start_date']} ~ {data['end_date']} | {data['n_days']}个交易日 | 八指数轮动+国债避险 | 手续费万分之二/单边</p>

<div class="card">
  <h2>核心数据概览</h2>
  <div class="stats-grid">
    <div class="stat"><div class="label">总收益率</div><div class="value pos">{data['strat_total']*100:.2f}%</div></div>
    <div class="stat"><div class="label">年化收益</div><div class="value pos">{data['strat_ann']*100:.2f}%</div></div>
    <div class="stat"><div class="label">夏普比率</div><div class="value">{data['strat_sharpe']:.2f}</div></div>
    <div class="stat"><div class="label">最大回撤</div><div class="value neg">{data['strat_mdd']*100:.2f}%</div></div>
    <div class="stat"><div class="label">切换次数</div><div class="value">{data['total_switches']}</div></div>
    <div class="stat"><div class="label">累计手续费</div><div class="value neg">{data['total_fee']*100:.2f}%</div></div>
  </div>
  <p style="font-size:12px;color:#666;margin-top:12px;margin-bottom:4px;">持仓分布：</p>
  <div class="pos-bar">{hold_bars}</div>
</div>

<div class="card">
  <h2>策略净值曲线（近1年）</h2>
  <div class="chart-container"><canvas id="navChart"></canvas></div>
  <p class="legend">红线为策略净值（含手续费），背景色块标注持仓资产</p>
</div>

<div class="grid-2">
  <div class="card">
    <h2>切换方向 TOP10</h2>
    <table>
      <thead><tr><th>切换方向</th><th>次数</th></tr></thead>
      <tbody>{pair_html}</tbody>
    </table>
  </div>
  <div class="card">
    <h2>买入目标统计</h2>
    <table>
      <thead><tr><th>买入资产</th><th>次数</th><th>占比</th></tr></thead>
      <tbody>{asset_html}</tbody>
    </table>
  </div>
</div>

<div class="card">
  <h2>全部切换操作明细（{len(switches)}次）</h2>
  <p style="font-size:12px;color:#888;margin-bottom:10px;">黄色高亮 = 当次买入的资产（买入因子最高） | <b>区间收益</b> = 从上次调仓到本次调仓持有资产的累计收益（含手续费） | 灰底 = 避险转国债 | 蓝底 = 初始建仓 | 紫底 = 持有至今</p>
  <div class="table-wrap" style="max-height:600px;overflow-y:auto;">
  <table>
    <thead>
      <tr>
        <th>#</th><th>日期</th><th>从</th><th></th><th>买入</th>
        <th class="bf-group" colspan="8">当日各指数买入因子（close/MA20-1）</th>
        <th>手续费</th><th>切换后净值</th><th>当日收益</th><th>区间收益</th>
      </tr>
      <tr>
        <th colspan="5"></th>
        <th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th>
        <th colspan="4"></th>
      </tr>
    </thead>
    <tbody>{switch_rows}</tbody>
  </table>
  </div>
</div>

<div class="card">
  <h2>每日持仓记录（切换日 + 月初 + 末日）</h2>
  <p style="font-size:12px;color:#888;margin-bottom:10px;">仅展示关键节点，完整{data['n_days']}天记录见数据文件</p>
  <div class="table-wrap" style="max-height:500px;overflow-y:auto;">
  <table>
    <thead>
      <tr>
        <th>日期</th><th>实际持仓</th><th>信号</th>
        <th class="bf-group" colspan="8">各指数买入因子</th>
        <th>当日收益</th><th>手续费</th><th>净值</th>
      </tr>
      <tr>
        <th colspan="3"></th>
        <th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th>
        <th colspan="3"></th>
      </tr>
    </thead>
    <tbody>{daily_rows}</tbody>
  </table>
  </div>
</div>

<div class="note">
  ℹ️ <b>说明</b>：买入因子 = 当日收盘价/当日MA20 - 1。策略每日收盘后计算8个股票指数的买入因子，持有因子最高的那个；
  若全部跌破MA20（因子均<0）则买国债避险。次日开盘价执行，每次买卖收万分之二手续费（单边）。<br>
  上表中"买入"列黄色高亮的就是当日买入因子最高的资产。<b>"区间收益"</b>列表示从上一次调仓到本次调仓这段时间内，持有原资产的累计收益率（含手续费影响）。初始建仓为蓝底，避险转国债为灰底，持有至今为紫底。
</div>

<script>
const D = {data_json};
Chart.defaults.font.family="'PingFang SC','Microsoft YaHei',sans-serif";
Chart.defaults.font.size=11;

const COLORS = {{1:'#1e88e5',2:'#43a047',3:'#ff9800',4:'#00acc1',5:'#8e24aa',6:'#ec407a',7:'#f57c00',8:'#00897b',9:'#757575',0:'#bdbdbd'}};
const ctx = document.getElementById('navChart');
const bgColors = D.positions.map(p => COLORS[p] || '#eee');
new Chart(ctx, {{
  type: 'line',
  data: {{
    labels: D.dates,
    datasets: [{{
      label: '策略净值',
      data: D.strat_nav,
      borderColor: '#e53935',
      backgroundColor: 'rgba(229,57,53,0.08)',
      borderWidth: 2,
      pointRadius: 0,
      fill: true,
      tension: 0.1
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{ callbacks: {{ label: function(c) {{ return '净值: ' + c.parsed.y.toFixed(4); }} }} }}
    }},
    scales: {{
      x: {{ ticks: {{ maxTicksLimit: 12, maxRotation: 0 }}, grid: {{ display: false }} }},
      y: {{ ticks: {{ callback: function(v) {{ return v.toFixed(2); }} }}, grid: {{ color: '#f0f0f0' }} }}
    }}
  }}
}});
</script>

</body>
</html>'''

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/V8近1年操作明细.html','w',encoding='utf-8') as f:
    f.write(html)
print("HTML报告已生成: V8近1年操作明细.html")
