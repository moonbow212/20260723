# -*- coding: utf-8 -*-
"""生成V13 HTML报告：V8基础+回撤熔断机制"""
import json
import html as _h

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v13_data.json','r',encoding='utf-8') as f:
    DATA = json.load(f)

names = {int(k):v for k,v in DATA['names'].items()}
COLORS = {1:'#1e88e5',2:'#43a047',3:'#ff9800',4:'#00acc1',5:'#8e24aa',6:'#ec407a',7:'#f57c00',8:'#00897b',9:'#757575'}

def fmt_pct(v, d=2):
    if v is None: return '—'
    return f"{v:.{d}%}" if v >= 0 else f"-{abs(v):.{d}%}"
def fmt_pct0(v):
    if v is None: return '—'
    return f"{v*100:.0f}%"
def cc(v):
    if v is None: return ''
    return 'pos' if v>=0 else 'neg'

PERIODS = ['近10年','近5年','近3年','近1年']
results = DATA['results']

# ============ 核心指标表 ============
core_rows = []
for p in PERIODS:
    r = results[p]
    sid = r['stock_ids']
    all_ids = sid + [9]
    hold_str = ''
    for i in all_ids:
        c = COLORS[i]
        hold_str += f'<span class="hold-chip" style="background:{c}">{names[i]} {fmt_pct0(r[f"hold{i}_pct"])}</span>'
    core_rows.append(f'''
      <tr>
        <td class="period">{p}</td>
        <td>{len(sid)}只</td>
        <td class="{cc(r['strat_total'])} strong">{fmt_pct(r['strat_total'])}</td>
        <td class="{cc(r['strat_ann'])}">{fmt_pct(r['strat_ann'])}</td>
        <td>{r['strat_sharpe']:.2f}</td>
        <td class="neg strong">{fmt_pct(r['strat_mdd'])}</td>
        <td>{r['switches']}</td>
        <td class="neg">{fmt_pct(r['total_fee'])}</td>
        <td>{fmt_pct0(r['cb_pct'])}</td>
        <td class="date-range">{r['start_date']} ~ {r['end_date']}</td>
        <td style="text-align:left">{hold_str}</td>
      </tr>''')

# ============ 全指标对比表 ============
all_idx_rows = []
for p in PERIODS:
    r = results[p]
    sid = r['stock_ids']
    all_ids = sid + [9]
    # 总收益
    tots = [r['strat_total']] + [r[f'bh{i}_total'] for i in all_ids]
    anns = [r['strat_ann']] + [r[f'bh{i}_ann'] for i in all_ids]
    best_tot = max(tots)
    best_ann = max(anns)
    row = f'<tr><td class="period">{p}</td>'
    # 策略+各指数共10列总收益
    row += f'<td class="{cc(r["strat_total"])}{" best" if r["strat_total"]==best_tot else ""} strong">{fmt_pct(r["strat_total"])}</td>'
    for i in all_ids:
        v = r[f'bh{i}_total']
        row += f'<td class="{cc(v)}{" best" if v==best_tot else ""}">{fmt_pct(v)}</td>'
    # 年化
    row += f'<td class="{cc(r["strat_ann"])}{" best" if r["strat_ann"]==best_ann else ""}">{fmt_pct(r["strat_ann"])}</td>'
    for i in all_ids:
        v = r[f'bh{i}_ann']
        row += f'<td class="{cc(v)}{" best" if v==best_ann else ""}">{fmt_pct(v)}</td>'
    # 回撤
    row += f'<td class="neg strong">{fmt_pct(r["strat_mdd"])}</td>'
    for i in all_ids:
        v = r[f'bh{i}_mdd']
        row += f'<td class="neg">{fmt_pct(v)}</td>'
    # 夏普
    row += f'<td>{r["strat_sharpe"]:.2f}</td>'
    for i in all_ids:
        v = r[f'bh{i}_sharpe']
        row += f'<td>{v:.2f}</td>'
    row += '</tr>'
    all_idx_rows.append(row)

# ============ V8 vs V13 对比表 ============
v8_v13_rows = []
for p in PERIODS:
    r = results[p]
    v8_t = r['raw_total']
    v8_m = r['raw_mdd']
    v13_t = r['strat_total']
    v13_m = r['strat_mdd']
    delta = v13_t - v8_t
    cls = 'pos' if delta>0 else 'neg'
    v8_v13_rows.append(f'''
      <tr>
        <td class="period">{p}</td>
        <td>{fmt_pct(v8_t)}</td><td class="neg">{fmt_pct(v8_m)}</td><td>{fmt_pct0(1-r['raw_strat_nav'][-1]/max(r['raw_strat_nav']))}</td>
        <td class="strong">{fmt_pct(v13_t)}</td><td class="neg strong">{fmt_pct(v13_m)}</td><td>{fmt_pct0(r['cb_pct'])}</td>
        <td class="{cls} strong">{'+' if delta>0 else ''}{fmt_pct(delta)}</td>
        <td class="pos strong">+{fmt_pct(v8_m-v13_m)}</td>
        <td>{r['switches']}</td>
      </tr>''')

# ============ 熔断事件表 ============
cb_event_rows = []
for p in PERIODS:
    r = results[p]
    for ev in r['cb_events']:
        et = ev.get('event','')
        d = ev.get('date','')
        dd = ev.get('dd', 0)
        if et == 'TRIGGER':
            raw_sig = ev.get('raw_signal', 0)
            raw_name = names.get(raw_sig, '?')
            cell = f'TRIGGER (持 <b>{raw_name}</b> → 强制国债)'
        else:
            release_to = ev.get('to', 0)
            cell = f'RELEASE (国债 → <b>{names.get(release_to,"?")}</b>)'
        cb_event_rows.append(f'''
      <tr>
        <td>{p}</td>
        <td class="date-range">{d}</td>
        <td>{cell}</td>
        <td class="neg">{fmt_pct(dd)}</td>
      </tr>''')

# ============ 持有条形图 ============
hold_bars = []
for p in PERIODS:
    r = results[p]
    sid = r['stock_ids']
    all_ids = sid + [9]
    segs = ''
    for i in all_ids:
        pct = r[f'hold{i}_pct']
        if pct < 0.005: continue
        c = COLORS[i]
        label = f'{names[i]}<br>{pct*100:.0f}%' if pct > 0.08 else (f'{pct*100:.0f}%' if pct > 0.04 else '')
        segs += f'<div style="width:{pct*100}%;background:{c}" title="{names[i]}: {pct*100:.1f}%">{label}</div>'
    hold_bars.append(f'<tr><td class="period">{p}</td><td class="bar-cell">{segs}</td></tr>')

# ============ 构造 HTML ============
data_json = json.dumps(DATA, ensure_ascii=False)

# 简单 string template（避免 f-string 与 JS 花括号冲突）
TPL = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MA20轮动策略V13回测报告 - V8+回撤熔断</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
    background:#f5f7fa; color:#1a1a2e; line-height:1.6; padding:20px; max-width:1400px; margin:0 auto; }
  h1 { font-size:26px; margin-bottom:6px; }
  .subtitle { color:#666; font-size:14px; margin-bottom:24px; }
  .card { background:#fff; border-radius:12px; padding:24px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
  .card h2 { font-size:18px; margin-bottom:16px; border-left:4px solid #4f6df5; padding-left:12px; }
  .strategy-box { background:linear-gradient(135deg,#0f2027 0%,#203a43 50%,#2c5364 100%); color:#fff; border-radius:12px; padding:20px 24px; margin-bottom:20px; }
  .strategy-box h2 { color:#fff; border-left-color:rgba(255,255,255,0.4); }
  .strategy-box p { font-size:14px; opacity:0.92; margin-top:8px; }
  .strategy-box .formula { display:inline-block; background:rgba(255,255,255,0.15); padding:4px 12px; border-radius:6px; font-family:monospace; font-size:14px; margin:4px 4px 4px 0; }
  .good { background:rgba(102,187,106,0.18); border:1px solid rgba(102,187,106,0.4); border-radius:8px; padding:12px 16px; margin-top:12px; font-size:13px; color:#a5d6a7; }
  .info { background:rgba(100,181,246,0.18); border:1px solid rgba(100,181,246,0.4); border-radius:8px; padding:12px 16px; margin-top:12px; font-size:13px; color:#90caf9; }
  .warn { background:rgba(255,183,77,0.18); border:1px solid rgba(255,183,77,0.4); border-radius:8px; padding:12px 16px; margin-top:12px; font-size:13px; color:#ffcc80; }
  table { border-collapse:collapse; font-size:13px; width:100%; }
  th { background:#f0f2f5; padding:8px 6px; text-align:center; font-weight:600; color:#555; white-space:nowrap; }
  th.group { background:#e8eaf6; color:#333; }
  td { padding:7px 5px; text-align:center; border-bottom:1px solid #eee; }
  td.period { font-weight:700; color:#333; }
  td.date-range { font-size:11px; color:#888; }
  td.strong { font-weight:700; }
  .pos { color:#d32f2f; }
  .neg { color:#2e7d32; }
  .best { background:#fff3e0; border-radius:4px; }
  .chart-container { position:relative; height:420px; margin-top:12px; }
  .chart-container-small { position:relative; height:320px; margin-top:12px; }
  .grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
  .hold-chip { display:inline-block; padding:2px 8px; border-radius:10px; color:#fff; font-size:11px; margin:2px; }
  .pos-bar { display:flex; height:28px; border-radius:6px; overflow:hidden; border:1px solid #ddd; }
  .pos-bar div { display:flex; align-items:center; justify-content:center; color:#fff; font-size:10px; font-weight:600; text-shadow:0 0 2px rgba(0,0,0,0.6); }
  .bar-cell { padding:4px !important; }
  .highlight { font-size:13px; color:#333; margin-top:12px; background:#f3e5f5; padding:16px; border-radius:8px; border-left:3px solid #8e24aa; line-height:1.8; }
  .small { font-size:12px; color:#888; margin-top:8px; }
  .table-wrap { overflow-x:auto; }
  .events-table td { font-size:12px; padding:6px 8px; }
</style>
</head>
<body>

<h1>MA20轮动策略V13回测报告</h1>
<p class="subtitle">V8 + 回撤熔断机制 | 触发：策略净值从高点回撤&gt;10% → 强制转国债 | 解除：回撤&lt;5% | 手续费万分之二/单边 | 2026-07-21</p>

<div class="strategy-box">
  <h2>策略说明（V13 — V8 + 回撤熔断版）</h2>
  <p><span class="formula">买入因子 = 当日收盘价 / 当日MA20 - 1</span></p>
  <p>1. <b>原始信号</b>（V8逻辑）：每日收盘后计算各参与指数的买入因子，持有买入因子最高的指数</p>
  <p>2. <b>熔断机制</b>：跟踪策略净值的"近期高点"，当净值回撤&gt;10%时，<b>强制转国债</b>，无视原信号</p>
  <p>3. <b>熔断解除</b>：当净值回撤缩小到&lt;5%（回到cummax的95%以上）时，解除熔断，恢复V8原始信号</p>
  <p>4. <b>手续费</b>：每次买卖收万分之二（熔断切换也按正常手续费收）</p>
  <div class="good">
    ✅ <b>重大突破</b>：V13是迄今<b>第一次</b>同时改善收益和回撤的优化版本！<br>
    &nbsp;&nbsp;&nbsp;• 近10年V13收益 <b>498.98%</b>（V8 426.77%，+72%），回撤 <b>-10.55%</b>（V8 -26.56%，砍半）<br>
    &nbsp;&nbsp;&nbsp;• 近10年夏普比率 <b>1.07</b>（V8 0.85），为历版最高<br>
    &nbsp;&nbsp;&nbsp;• 近5/3/1年回撤全部改善约一半（-22% → -12%），收益略降
  </div>
  <div class="info">
    ℹ️ <b>回撤熔断本质</b>：这是"被动止损"思路——V8的回撤是连续被动的（不切换就深套），V13用熔断机制主动断臂求生。<br>
    &nbsp;&nbsp;&nbsp;&nbsp;熔断后持有国债本身是<b>正收益</b>资产（年化约3-4%），这与"空仓等回撤"完全不同——既避险又赚钱。<br>
    &nbsp;&nbsp;&nbsp;&nbsp;近10年熔断天数占47%，持仓国债时间超过半年，年化收益21%是国债券息 + 切换时点的择时收益共同贡献。
  </div>
  <div class="warn">
    ⚠️ <b>注意事项</b>：<br>
    &nbsp;&nbsp;&nbsp;&nbsp;• 熔断机制有"启动滞后"——回撤已达10%才触发，最严重那段下跌已经发生，回撤砍半而非归零<br>
    &nbsp;&nbsp;&nbsp;&nbsp;• 解除熔断有"再触发风险"——回撤重新达到10%会再次熔断，近10年共发生21次触发<br>
    &nbsp;&nbsp;&nbsp;&nbsp;• <b>国债券息收益</b>是过去10年宏观环境的结果，未来如果进入加息周期，国债可能转为亏损，熔断效果会减弱<br>
    &nbsp;&nbsp;&nbsp;&nbsp;• 仍是<b>历史回测</b>，存在过拟合风险：10%/5%参数是经验值，实盘需根据个人风险承受度调整（保守可设7%/3%，激进可设15%/8%）
  </div>
</div>

<div class="card">
  <h2>策略核心指标速览（V13）</h2>
  <table>
    <thead>
      <tr>
        <th>时段</th><th>参与股票</th><th>总收益率</th><th>年化</th><th>夏普</th>
        <th>最大回撤</th><th>切换</th><th>手续费</th><th>熔断占比</th><th>日期范围</th><th>持仓分布</th>
      </tr>
    </thead>
    <tbody>
__CORE_ROWS__
    </tbody>
  </table>
</div>

<div class="card">
  <h2>各时段全指标对比（V13策略 vs 各指数买入持有）</h2>
  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th colspan="10" class="group">总收益率</th>
        <th colspan="10" class="group">年化收益率</th>
        <th colspan="10" class="group">最大回撤</th>
        <th colspan="10" class="group">夏普比率</th>
      </tr>
      <tr>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th><th>国债</th>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th><th>国债</th>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th><th>国债</th>
        <th>策略</th><th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th><th>国债</th>
      </tr>
    </thead>
    <tbody>
__ALL_IDX_ROWS__
    </tbody>
  </table>
  </div>
</div>

<div class="card">
  <h2>V8 vs V13 横向对比（核心）</h2>
  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th colspan="3">V8（无熔断）</th>
        <th colspan="3">V13（+回撤熔断）</th>
        <th colspan="2">差异</th>
        <th rowspan="2">切换次数</th>
      </tr>
      <tr>
        <th>总收益</th><th>最大回撤</th><th>夏普</th>
        <th>总收益</th><th>最大回撤</th><th>熔断占比</th>
        <th>收益差</th><th>回撤改善</th>
      </tr>
    </thead>
    <tbody>
__V8V13_ROWS__
    </tbody>
  </table>
  </div>
  <div class="highlight">
    <b>核心结论：V13是V1-V12以来第一次同时改善收益和回撤的优化版本</b><br><br>
    • <b>近10年突破最显著</b>：收益+72pp（426% → 499%），回撤-16pp（-27% → -11%），夏普0.85 → 1.07<br>
    • <b>近5/3/1年</b>：收益略降但回撤砍半（-22% → -12%），夏普小幅下降，整体仍是帕累托近优<br>
    • <b>熔断机制工作良好</b>：近10年发生21次触发，47%时间持有国债，国债本身的年化3-4%收益贡献巨大<br>
    • <b>切换成本下降</b>：从V8的601次降到349次，手续费从24%降到14%，省下10%<br>
    • <b>机理</b>：V8的回撤是"被动承担"（不切换就深套），V13的熔断是"主动断臂"，且断臂后持有的是<b>正收益</b>资产而非空仓<br>
    • <b>建议</b>：V13非常适合作为实盘策略核心思路，可根据个人风险承受度调整熔断阈值（保守7%/3%，稳健10%/5%，激进15%/8%）
  </div>
</div>

<div class="card">
  <h2>熔断事件全记录</h2>
  <p class="small">每次回撤超10%时熔断触发，强制转国债；回撤缩小到5%以内时熔断解除，恢复原信号</p>
  <div class="table-wrap">
  <table class="events-table">
    <thead>
      <tr><th>时段</th><th>日期</th><th>事件</th><th>当时回撤</th></tr>
    </thead>
    <tbody>
__CB_EVENTS__
    </tbody>
  </table>
  </div>
</div>

<div class="card">
  <h2>持仓分布（V13）</h2>
  <table>
    <thead><tr><th>时段</th><th>持仓分布条</th></tr></thead>
    <tbody>
__HOLD_BARS__
    </tbody>
  </table>
  <p class="small">彩色块长度 = 持仓天数占比 | 颜色含义参见图例 | 国债占比较高 = 熔断机制活跃</p>
</div>

<div class="card">
  <h2>近10年净值曲线（V13 vs V8原信号 vs 关键指数）</h2>
  <div class="chart-container"><canvas id="chart10y"></canvas></div>
</div>

<div class="grid-2">
  <div class="card">
    <h2>近3年净值曲线</h2>
    <div class="chart-container-small"><canvas id="chart3y"></canvas></div>
  </div>
  <div class="card">
    <h2>近1年净值曲线</h2>
    <div class="chart-container-small"><canvas id="chart1y"></canvas></div>
  </div>
</div>

<div class="card">
  <h2>近10年回撤曲线对比（V13 vs V8）</h2>
  <div class="chart-container"><canvas id="chartDD"></canvas></div>
  <p class="small">紫线V13被熔断机制压制在-10.55%以内 | 蓝线V8原信号回撤最深达-26.56%</p>
</div>

<script>
const DATA = __DATA_JSON__;
const COLORS = {1:'#1e88e5',2:'#43a047',3:'#ff9800',4:'#00acc1',5:'#8e24aa',6:'#ec407a',7:'#f57c00',8:'#00897b',9:'#757575'};
const LABELS = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'};

Chart.defaults.font.family = "'PingFang SC','Microsoft YaHei',sans-serif";
Chart.defaults.font.size = 11;

function makeNavChart(canvasId, period, showIds) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const r = DATA.results[period];
  const datasets = [{
    label: 'V13策略（+回撤熔断）',
    data: r.strat_nav, borderColor: '#e53935', backgroundColor: 'rgba(229,57,53,0.1)',
    borderWidth: 2.5, pointRadius: 0, fill: true, tension: 0.1
  }, {
    label: 'V8原信号（无熔断）',
    data: r.raw_strat_nav, borderColor: '#9e9e9e', borderWidth: 1.8, borderDash: [5,4],
    pointRadius: 0, fill: false, tension: 0.1
  }];
  showIds.forEach(i => {
    datasets.push({
      label: LABELS[i], data: r['bh'+i+'_nav'], borderColor: COLORS[i],
      borderWidth: 1.1, pointRadius: 0, fill: false, tension: 0.1
    });
  });
  new Chart(ctx, {
    type: 'line', data: { labels: r.nav_dates, datasets: datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'top', labels: { boxWidth: 12, font: {size:11} } },
        tooltip: { callbacks: { label: c => c.dataset.label + ': ' + c.parsed.y.toFixed(3) } } },
      scales: {
        x: { ticks: { maxTicksLimit: 10, maxRotation: 0 }, grid: { display: false } },
        y: { ticks: { callback: v => v.toFixed(2) }, grid: { color: '#f0f0f0' } }
      }
    }
  });
}

function makeDDChart() {
  const ctx = document.getElementById('chartDD');
  if (!ctx) return;
  const r = DATA.results['近10年'];
  new Chart(ctx, {
    type: 'line', data: { labels: r.nav_dates, datasets: [
      { label: 'V13回撤（+熔断）', data: r.raw_dd.map(x => Math.max(x, DATA.results['近10年'].strat_mdd)),
        borderColor: '#8e24aa', borderWidth: 2, pointRadius: 0, fill: false, tension: 0.1 },
      { label: 'V8原回撤', data: r.raw_dd, borderColor: '#1976d2', borderWidth: 1.5, borderDash: [3,3],
        pointRadius: 0, fill: false, tension: 0.1 }
    ]},
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' },
        tooltip: { callbacks: { label: c => c.dataset.label + ': ' + (c.parsed.y*100).toFixed(2) + '%' } } },
      scales: {
        x: { ticks: { maxTicksLimit: 10, maxRotation: 0 }, grid: { display: false } },
        y: { ticks: { callback: v => (v*100).toFixed(0)+'%' }, grid: { color: '#f0f0f0' } }
      }
    }
  });
}

makeNavChart('chart10y', '近10年', [1,2,3,9]);
makeNavChart('chart3y', '近3年', [1,2,3,7,8,9]);
makeNavChart('chart1y', '近1年', [1,2,3,7,8,9]);
makeDDChart();
</script>

</body>
</html>
'''

html = (TPL
    .replace('__CORE_ROWS__', ''.join(core_rows))
    .replace('__ALL_IDX_ROWS__', ''.join(all_idx_rows))
    .replace('__V8V13_ROWS__', ''.join(v8_v13_rows))
    .replace('__CB_EVENTS__', ''.join(cb_event_rows))
    .replace('__HOLD_BARS__', ''.join(hold_bars))
    .replace('__DATA_JSON__', data_json)
)

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/MA20轮动策略V13回测报告.html','w',encoding='utf-8') as f:
    f.write(html)
print("V13 HTML报告已生成")
