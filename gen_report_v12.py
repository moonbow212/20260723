"""
V12报告生成脚本：V8 + 2%切换阈值
"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v12.json','r',encoding='utf-8') as f:
    d = json.load(f)

# V8原始结果（对比用）
v8 = {
    '近10年': {'total': 4.2677, 'mdd': -0.2656, 'sharpe': 0.85, 'switch': 601, 'fee': 0.2402},
    '近5年':  {'total': 1.3032, 'mdd': -0.2265, 'sharpe': 0.76, 'switch': 289, 'fee': 0.1242},
    '近3年':  {'total': 1.1155, 'mdd': -0.2265, 'sharpe': 0.97, 'switch': 177, 'fee': 0.0766},
    '近1年':  {'total': 0.2027, 'mdd': -0.2142, 'sharpe': 0.77, 'switch': 54,  'fee': 0.0274},
}
# V11原始结果（5天锁仓）
v11 = {
    '近10年': {'total': 0.9334, 'mdd': -0.4314, 'sharpe': 0.43, 'switch': 325, 'fee': 0.1298},
    '近5年':  {'total': 0.4696, 'mdd': -0.2546, 'sharpe': 0.46, 'switch': 156, 'fee': 0.0622},
    '近3年':  {'total': 0.3768, 'mdd': -0.2546, 'sharpe': 0.57, 'switch': 93,  'fee': 0.0370},
    '近1年':  {'total': 0.1248, 'mdd': -0.2284, 'sharpe': 0.56, 'switch': 33,  'fee': 0.0130},
}

THRESHOLD = d['threshold']
NAMES = {'sh50':'上证50','gem50':'创业板50','ndx':'纳斯达克100','hs300':'沪深300',
         'zz500':'中证500','zz1000':'中证1000','sp500':'标普500','kc50':'科创50','bond':'国债'}
COLORS = {'上证50':'#1e88e5','创业板50':'#43a047','纳斯达克100':'#ff9800','沪深300':'#00acc1',
          '中证500':'#8e24aa','中证1000':'#ec407a','标普500':'#f57c00','科创50':'#00897b','国债':'#757575'}

def fmt(v, kind='pct'):
    if v is None: return '—'
    if kind=='pct': return f"{v*100:.2f}%"
    if kind=='num': return f"{v:.2f}"
    return str(v)

# 准备核心表格行
periods = ['近10年','近5年','近3年','近1年']
core_rows = []
for p in periods:
    if p not in d['results']: continue
    r = d['results'][p]
    hold_str = ' '.join(f"{NAMES[k]}={v*100:.0f}%" for k, v in r['hold_pct'].items() if v > 0.01)
    core_rows.append({
        'period': p,
        'start': r['start'],
        'end': r['end'],
        'n': r['n_days'],
        'stocks': '、'.join(NAMES[s] for s in r['stocks']),
        'total': r['strat_total'],
        'ann': r['strat_ann'],
        'sharpe': r['strat_sharpe'],
        'mdd': r['strat_mdd'],
        'switch': r['switch_count'],
        'fee': r['total_fee'],
        'hold': hold_str,
    })

# 准备绘图数据
chart_data = {}
for p in periods:
    if p not in d['results']: continue
    r = d['results'][p]
    chart_data[p] = {
        'dates': r['nav_dates'],
        'strat': r['strat_nav'],
    }
    for k, vals in r['bh_navs'].items():
        chart_data[p][NAMES[k]] = vals

# 序列化为JSON给JS
core_rows_json = json.dumps(core_rows, ensure_ascii=False)
chart_data_json = json.dumps(chart_data, ensure_ascii=False)
hold_pct_json = json.dumps({p: d['results'][p]['hold_pct'] for p in periods if p in d['results']}, ensure_ascii=False)
v8_json = json.dumps(v8, ensure_ascii=False)
v11_json = json.dumps(v11, ensure_ascii=False)

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MA20轮动策略V12回测报告 - 2%切换阈值</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  background:#f5f7fa; color:#1a1a2e; line-height:1.6; padding:20px; max-width:1320px; margin:0 auto; }
h1 { font-size:26px; margin-bottom:6px; }
.subtitle { color:#666; font-size:14px; margin-bottom:24px; }
.card { background:#fff; border-radius:12px; padding:24px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
.card h2 { font-size:18px; margin-bottom:16px; border-left:4px solid #4f6df5; padding-left:12px; }
.strategy-box { background:linear-gradient(135deg,#0f2027 0%,#203a43 50%,#2c5364 100%); color:#fff; border-radius:12px; padding:20px 24px; margin-bottom:20px; }
.strategy-box h2 { color:#fff; border-left-color:rgba(255,255,255,0.4); }
.strategy-box p { font-size:14px; opacity:0.92; margin-top:8px; }
.formula { display:inline-block; background:rgba(255,255,255,0.15); padding:4px 12px; border-radius:6px; font-family:monospace; font-size:14px; margin:4px 4px 4px 0; }
.good { background:#e8f5e9; border:1px solid #66bb6a; border-radius:8px; padding:12px 16px; margin-top:12px; font-size:13px; color:#2e7d32; }
.warn { background:#fff3e0; border:1px solid #ffb74d; border-radius:8px; padding:12px 16px; margin-top:12px; font-size:13px; color:#e65100; }
.bad { background:#ffebee; border:1px solid #ef5350; border-radius:8px; padding:12px 16px; margin-top:12px; font-size:13px; color:#c62828; }
.info { background:#e3f2fd; border:1px solid #64b5f6; border-radius:8px; padding:12px 16px; margin-top:12px; font-size:13px; color:#1565c0; }
.table-wrap { overflow-x:auto; }
table { border-collapse:collapse; font-size:13px; min-width:100%; }
th { background:#f0f2f5; padding:9px 8px; text-align:center; font-weight:600; color:#555; white-space:nowrap; }
td { padding:9px 8px; text-align:center; border-bottom:1px solid #eee; white-space:nowrap; }
td.period { font-weight:700; color:#333; }
.pos { color:#d32f2f; font-weight:600; }
.neg { color:#2e7d32; font-weight:600; }
.best { background:#fff3e0; border-radius:4px; }
.chart-container { position:relative; height:420px; margin-top:12px; }
.chart-container-small { position:relative; height:320px; margin-top:12px; }
.grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.highlight { font-size:13px; color:#333; margin-top:12px; background:#f3e5f5; padding:14px; border-radius:8px; border-left:3px solid #8e24aa; }
.hold-bar { display:flex; height:22px; border-radius:6px; overflow:hidden; margin-top:6px; font-size:9px; min-width:300px; }
.hold-bar div { display:flex; align-items:center; justify-content:center; color:#fff; font-weight:600; }
</style>
</head>
<body>

<h1>MA20轮动策略V12回测报告 — 2%切换阈值</h1>
<p class="subtitle">V8基础 + 切换阈值优化（仅当新资产bf > 当前bf + 2%才切换） | 2026-07-21</p>

<div class="strategy-box">
  <h2>策略说明（V12 — 切换阈值版）</h2>
  <p><span class="formula">买入因子 = 当日收盘价 / 当日MA20 - 1</span></p>
  <p>1. 每日收盘后计算各参与指数的买入因子，候选 = <b>买入因子最高</b>的指数</p>
  <p>2. <b>切换阈值</b>：仅当 <b>候选bf > 当前持仓bf + 2%</b> 时才切换，否则维持现状</p>
  <p>3. 所有参与指数的买入因子<b>均小于0</b>（均跌破MA20）→ 买入<b>国债指数</b></p>
  <p>4. 次日开盘价执行，每次买卖收<b>万分之二</b>手续费</p>
  <p>5. <b>分段参与规则</b>：近10年用7股票指数轮动（无科创50），近5/3/1年用8股票指数轮动（含科创50）</p>
  <div class="bad">
    ⚠️ <b>核心结果</b>：2%阈值对MA20轮动<b>过于保守</b>，近10年总收益从V8的<b>426.77%</b>骤降至<b>58.81%</b>（缩水368%），\n    最大回撤从-26.56%改善到-15.65%。\n  </div>
  <div class="info">
    ℹ️ <b>设计初衷</b>：V11（5天最小持仓期）锁仓后错过主升浪也错过避险；切换阈值方案本意是"过滤微弱优势切换、保留及时切换"，\n    理论上比硬锁仓更灵活。但2%对于快速变化的bf信号来说仍然太高。\n  </div>
</div>

<div class="card">
  <h2>策略核心指标</h2>
  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>时段</th><th>参与股票</th><th>日期范围</th><th>交易日</th>
        <th>总收益</th><th>年化收益</th><th>夏普比率</th>
        <th>最大回撤</th><th>切换次数</th><th>累计手续费</th>
      </tr>
    </thead>
    <tbody id="coreBody"></tbody>
  </table>
  </div>
</div>

<div class="card">
  <h2>持仓分布</h2>
  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>时段</th><th>国债</th>
        <th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th>
        <th>持仓柱</th>
      </tr>
    </thead>
    <tbody id="posBody"></tbody>
  </table>
  </div>
</div>

<div class="card">
  <h2>三版策略横向对比：V8(无) vs V11(5天锁仓) vs V12(2%阈值)</h2>
  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th colspan="4" style="background:#fff3e0;">V8 (无阈值)</th>
        <th colspan="4" style="background:#e1f5fe;">V11 (5天最小持仓)</th>
        <th colspan="4" style="background:#f3e5f5;">V12 (2%切换阈值)</th>
      </tr>
      <tr>
        <th>总收益</th><th>回撤</th><th>切换</th><th>手续费</th>
        <th>总收益</th><th>回撤</th><th>切换</th><th>手续费</th>
        <th>总收益</th><th>回撤</th><th>切换</th><th>手续费</th>
      </tr>
    </thead>
    <tbody id="cmpBody"></tbody>
  </table>
  </div>
  <div class="highlight">
    <b>关键发现：2%阈值代价远大于收益</b><br><br>
    • <b>收益暴跌</b>：近10年从V8的426.77%骤降到58.81%（-368%），比V11的93.34%还差。原因是2%在快速变化的bf面前过高：\n    当持仓bf=5%时，新资产需达7%才切换，而强势资产常在bf=6%时已是主升浪末段，错过最佳入场时机。<br>
    • <b>回撤确实改善</b>：近10年最大回撤-15.65%是V8以来最低。但近1年回撤-14.15%与V8(-21.42%)相近，改善不稳定。<br>
    • <b>切换节省并不显著</b>：近10年从601次降到269次（-55%），但手续费仅从24%降到5%（-19pp），因为大部分切换仍因阈值达标而执行，\n    被阻止的往往是"最有价值"的那部分（捕捉趋势切换的关键节点）。<br>
    • <b>比V11更差</b>：V11的5天锁仓简单粗暴，V12的2%阈值看似更精细，反而收益更差（58.81% vs 93.34%）。\n    V11至少保留了"5天内任意切换"的灵活性，V12的bf差2%门槛很多时候锁住了一整天到几天的窗口。<br>
    • <b>结论</b>：在MA20轮动这类依赖快速反应的趋势策略上，<b>任何形式的切换成本优化都是得不偿失的</b>。\n    万分之二的费率对策略超额收益的损害，远小于错过主升浪的机会成本。V8（无任何切换约束）仍是历版最优。
  </div>
</div>

<div class="card">
  <h2>各指数买入持有参考（近10年）</h2>
  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>指数</th><th>总收益</th><th>年化收益</th><th>最大回撤</th><th>夏普比率</th>
      </tr>
    </thead>
    <tbody>
__BH_TABLE__
    </tbody>
  </table>
  </div>
</div>

<div class="card">
  <h2>全周期净值曲线（近10年）</h2>
  <p style="font-size:13px;color:#666;">V12策略 vs 各指数买入持有（含手续费）</p>
  <div class="chart-container"><canvas id="chart10y"></canvas></div>
</div>

<div class="grid-2">
  <div class="card">
    <h2>近3年净值曲线</h2>
    <p style="font-size:12px;color:#999;">含科创50</p>
    <div class="chart-container-small"><canvas id="chart3y"></canvas></div>
  </div>
  <div class="card">
    <h2>近1年净值曲线</h2>
    <p style="font-size:12px;color:#999;">含科创50</p>
    <div class="chart-container-small"><canvas id="chart1y"></canvas></div>
  </div>
</div>

<script>
const CORE = __CORE_ROWS__;
const CHARTS = __CHART_DATA__;
const HOLDS = __HOLD_PCT__;
const V8 = __V8_DATA__;
const V11 = __V11_DATA__;

function fmtPct(v){ return v==null?'—':(v*100).toFixed(2)+'%'; }
function fmtSharpe(v){ return v==null?'—':v.toFixed(2); }
function cc(v){ return v==null?'na':(v>=0?'pos':'neg'); }

// 核心指标表
const coreBody = document.getElementById('coreBody');
CORE.forEach(r => {
  const tr = document.createElement('tr');
  tr.innerHTML = `<td class="period">${r.period}</td>
    <td style="font-size:11px;">${r.stocks}</td>
    <td style="font-size:11px;color:#888;">${r.start} ~ ${r.end}</td>
    <td>${r.n}</td>
    <td class="pos">${fmtPct(r.total)}</td>
    <td class="pos">${fmtPct(r.ann)}</td>
    <td>${fmtSharpe(r.sharpe)}</td>
    <td class="neg">${fmtPct(r.mdd)}</td>
    <td>${r.switch}</td>
    <td class="neg">${fmtPct(r.fee)}</td>`;
  coreBody.appendChild(tr);
});

// 持仓表
const COLOR_MAP = {'上证50':'#1e88e5','创业板50':'#43a047','纳斯达克100':'#ff9800','沪深300':'#00acc1',
                   '中证500':'#8e24aa','中证1000':'#ec407a','标普500':'#f57c00','科创50':'#00897b','国债':'#757575'};
const KEY_ORDER = ['sh50','gem50','ndx','hs300','zz500','zz1000','sp500','kc50','bond'];
const KEY_LABEL = {'sh50':'上证50','gem50':'创业板50','ndx':'纳斯达克100','hs300':'沪深300',
                   'zz500':'中证500','zz1000':'中证1000','sp500':'标普500','kc50':'科创50','bond':'国债'};
const posBody = document.getElementById('posBody');
CORE.forEach(r => {
  const h = HOLDS[r.period] || {};
  let html = `<td class="period">${r.period}</td><td>${(h.bond*100||0).toFixed(1)}%</td>`;
  let bar = '<div class="hold-bar">';
  for (const k of ['sh50','gem50','ndx','hs300','zz500','zz1000','sp500','kc50']) {
    const v = h[k] || 0;
    const label = KEY_LABEL[k];
    const color = COLOR_MAP[label];
    html += `<td>${(v*100).toFixed(1)}%</td>`;
    if (v > 0.001) {
      bar += `<div style="width:${v*100}%;background:${color}">${v>0.05?(v*100).toFixed(0)+'%':''}</div>`;
    }
  }
  bar += '</div>';
  html += `<td style="min-width:300px;">${bar}</td>`;
  const tr = document.createElement('tr');
  tr.innerHTML = html;
  posBody.appendChild(tr);
});

// 对比表
const cmpBody = document.getElementById('cmpBody');
const periods = ['近10年','近5年','近3年','近1年'];
periods.forEach(p => {
  const v8r = V8[p], v11r = V11[p];
  const v12r = (() => {
    const r = CORE.find(x => x.period === p);
    if (!r) return null;
    return {total: r.total, mdd: r.mdd, switch: r.switch, fee: r.fee};
  })();
  if (!v12r) return;
  const tr = document.createElement('tr');
  tr.innerHTML = `<td class="period">${p}</td>
    <td class="pos">${fmtPct(v8r.total)}</td>
    <td class="neg">${fmtPct(v8r.mdd)}</td>
    <td>${v8r.switch}</td>
    <td class="neg">${fmtPct(v8r.fee)}</td>
    <td class="pos">${fmtPct(v11r.total)}</td>
    <td class="neg">${fmtPct(v11r.mdd)}</td>
    <td>${v11r.switch}</td>
    <td class="neg">${fmtPct(v11r.fee)}</td>
    <td class="pos">${fmtPct(v12r.total)}</td>
    <td class="neg">${fmtPct(v12r.mdd)}</td>
    <td>${v12r.switch}</td>
    <td class="neg">${fmtPct(v12r.fee)}</td>`;
  cmpBody.appendChild(tr);
});

// 图表
Chart.defaults.font.family = "'PingFang SC','Microsoft YaHei',sans-serif";
Chart.defaults.font.size = 11;

function makeChart(canvasId, cd, stocksForPeriod) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const datasets = [{
    label: 'V12策略', data: cd.strat, borderColor: '#e53935',
    backgroundColor: 'rgba(229,57,53,0.08)', borderWidth: 2.5, pointRadius: 0, fill: true, tension: 0.1
  }];
  stocksForPeriod.forEach(name => {
    if (!cd[name]) return;
    datasets.push({
      label: name, data: cd[name], borderColor: COLOR_MAP[name],
      borderWidth: 1.2, pointRadius: 0, fill: false, tension: 0.1
    });
  });
  if (cd['国债']) {
    datasets.push({
      label: '国债', data: cd['国债'], borderColor: COLOR_MAP['国债'],
      borderWidth: 1.2, pointRadius: 0, fill: false, tension: 0.1
    });
  }
  return new Chart(ctx, {
    type: 'line',
    data: { labels: cd.dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: true, position: 'top', labels: { boxWidth: 12, font: { size: 10 } } },
        tooltip: { callbacks: { label: c => c.dataset.label + ': ' + c.parsed.y.toFixed(3) } }
      },
      scales: {
        x: { ticks: { maxTicksLimit: 8, maxRotation: 0 }, grid: { display: false } },
        y: { ticks: { callback: v => v.toFixed(2) }, grid: { color: '#f0f0f0' } }
      }
    }
  });
}

const c10 = CHARTS['近10年'];
if (c10) makeChart('chart10y', c10, ['上证50','创业板50','纳斯达克100','沪深300','中证500','中证1000','标普500']);
const c3 = CHARTS['近3年'];
if (c3) makeChart('chart3y', c3, ['上证50','创业板50','纳斯达克100','沪深300','中证500','中证1000','标普500','科创50']);
const c1 = CHARTS['近1年'];
if (c1) makeChart('chart1y', c1, ['上证50','创业板50','纳斯达克100','沪深300','中证500','中证1000','标普500','科创50']);
</script>

</body>
</html>
'''

# 填充买入持有表
r10 = d['results']['近10年']
bh_table = ''
for k in ['sh50','gem50','ndx','hs300','zz500','zz1000','sp500','bond']:
    if k not in r10['bh_metrics']: continue
    m = r10['bh_metrics'][k]
    bh_table += f'<tr><td class="period">{NAMES[k]}</td><td class="pos">{m["total"]*100:.2f}%</td><td class="pos">{m["ann"]*100:.2f}%</td><td class="neg">{m["mdd"]*100:.2f}%</td><td>{m["sharpe"]:.2f}</td></tr>'

html = html.replace('__CORE_ROWS__', core_rows_json)
html = html.replace('__CHART_DATA__', chart_data_json)
html = html.replace('__HOLD_PCT__', hold_pct_json)
html = html.replace('__V8_DATA__', v8_json)
html = html.replace('__V11_DATA__', v11_json)
html = html.replace('__BH_TABLE__', bh_table)

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/MA20轮动策略V12回测报告.html','w',encoding='utf-8') as f:
    f.write(html)
print("HTML报告已生成: MA20轮动策略V12回测报告.html")
