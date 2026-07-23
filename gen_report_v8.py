# -*- coding: utf-8 -*-
"""生成V8 HTML回测报告 - 八指数轮动(科创50仅近5/3/1年)+国债避险"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v8_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

names = {int(k):v for k,v in data['names'].items()}
# 1=上证50 2=创业板50 3=纳斯达克100 4=沪深300 5=中证500 6=中证1000 7=标普500 8=科创50 9=国债
ALL_POSSIBLE = [1,2,3,4,5,6,7,8,9]  # 所有可能出现的指数
BOND = 9
periods = ['近10年','近5年','近3年','近1年']

def fmt_pct(v):
    return "—" if v is None else f"{v*100:.2f}%"

def fmt_f(v):
    return "—" if v is None else f"{v:.2f}"

# 为每个时段准备表格行数据
table_rows = []
for p in periods:
    r = data['results'].get(p)
    if not r:
        continue
    stocks = r['stock_ids']
    all_ids = stocks + [BOND]
    row = {
        'period': p,
        'date_range': f"{r['start_date']} ~ {r['end_date']}",
        'n_days': r['n_days'],
        'stocks': stocks,
        'all_ids': all_ids,
        'switches': r['switches'],
        'total_fee': fmt_pct(r['total_fee']),
        'strat_total': fmt_pct(r['strat_total']),
        'strat_ann': fmt_pct(r['strat_ann']),
        'strat_mdd': fmt_pct(r['strat_mdd']),
        'strat_sharpe': fmt_f(r['strat_sharpe']),
        '_strat_total': r['strat_total'],
        '_strat_ann': r['strat_ann'],
    }
    for i in ALL_POSSIBLE:
        if i in all_ids:
            row[f'bh{i}_total'] = fmt_pct(r[f'bh{i}_total'])
            row[f'bh{i}_ann'] = fmt_pct(r[f'bh{i}_ann'])
            row[f'bh{i}_mdd'] = fmt_pct(r[f'bh{i}_mdd'])
            row[f'bh{i}_sharpe'] = fmt_f(r[f'bh{i}_sharpe'])
            row[f'hold{i}_pct'] = fmt_pct(r[f'hold{i}_pct'])
            row[f'_bh{i}_total'] = r[f'bh{i}_total']
            row[f'_bh{i}_ann'] = r[f'bh{i}_ann']
            h = r[f'hold{i}_pct']
            row[f'_hold{i}_pct'] = h if h is not None else 0
        else:
            row[f'bh{i}_total'] = '—'
            row[f'bh{i}_ann'] = '—'
            row[f'bh{i}_mdd'] = '—'
            row[f'bh{i}_sharpe'] = '—'
            row[f'hold{i}_pct'] = '—'
            row[f'_bh{i}_total'] = None
            row[f'_bh{i}_ann'] = None
            row[f'_hold{i}_pct'] = 0
    row['cash_pct'] = fmt_pct(r['cash_pct'])
    table_rows.append(row)

# 净值曲线降采样
def downsample(nav_list, dates, target=800):
    n = len(dates)
    step = max(1, n // target)
    return dates[::step], nav_list[::step]

chart_data = {}
for p in periods:
    r = data['results'].get(p)
    if not r: continue
    stocks = r['stock_ids']
    all_ids = stocks + [BOND]
    d, s = downsample(r['strat_nav'], r['nav_dates'])
    cd = {'dates': d, 'strat': s}
    for i in all_ids:
        d2, s2 = downsample(r[f'bh{i}_nav'], r['nav_dates'])
        cd[f'bh{i}'] = s2
    chart_data[p] = cd

all_payload = {'table_rows': table_rows, 'chart_data': chart_data}
data_json = json.dumps(all_payload, ensure_ascii=False)

# 颜色
COLORS = {1:'#1e88e5',2:'#43a047',3:'#ff9800',4:'#00acc1',5:'#8e24aa',6:'#ec407a',7:'#f57c00',8:'#00897b',9:'#757575'}

HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MA20轮动策略V8回测报告 - 八指数轮动</title>
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
  .strategy-box .formula { display:inline-block; background:rgba(255,255,255,0.15); padding:4px 12px; border-radius:6px; font-family:monospace; font-size:14px; margin:4px 4px 4px 0; }
  .good { background:#e8f5e9; border:1px solid #66bb6a; border-radius:8px; padding:12px 16px; margin-top:12px; font-size:13px; color:#2e7d32; }
  .info { background:#e3f2fd; border:1px solid #64b5f6; border-radius:8px; padding:12px 16px; margin-top:12px; font-size:13px; color:#1565c0; }
  .warn { background:#fff3e0; border:1px solid #ffb74d; border-radius:8px; padding:12px 16px; margin-top:12px; font-size:13px; color:#e65100; }
  .table-wrap { overflow-x:auto; }
  table { border-collapse:collapse; font-size:10px; min-width:100%; }
  th { background:#f0f2f5; padding:6px 4px; text-align:center; font-weight:600; color:#555; white-space:nowrap; }
  th.group { background:#e8eaf6; color:#333; }
  td { padding:6px 4px; text-align:center; border-bottom:1px solid #eee; white-space:nowrap; }
  td.period { font-weight:700; color:#333; font-size:12px; }
  td.date-range { font-size:9px; color:#999; }
  td.na { color:#ccc; }
  .pos { color:#d32f2f; font-weight:600; }
  .neg { color:#2e7d32; font-weight:600; }
  .best { background:#fff3e0; border-radius:4px; }
  .chart-container { position:relative; height:420px; margin-top:12px; }
  .chart-container-small { position:relative; height:320px; margin-top:12px; }
  .grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
  .pos-bar { display:flex; height:24px; border-radius:6px; overflow:hidden; margin-top:8px; font-size:9px; min-width:300px; }
  .pos-bar div { display:flex; align-items:center; justify-content:center; color:#fff; font-weight:600; }
  .legend { display:flex; gap:12px; margin-top:12px; font-size:12px; flex-wrap:wrap; }
  .legend-item { display:flex; align-items:center; gap:5px; }
  .legend-dot { width:12px; height:12px; border-radius:3px; }
  .highlight { font-size:13px; color:#555; margin-top:12px; background:#f3e5f5; padding:14px; border-radius:8px; border-left:3px solid #8e24aa; }
  .compare-table td { font-size:13px; padding:10px 8px; }
  .core-table td { font-size:13px; padding:9px 8px; }
  .core-table th { font-size:12px; padding:9px 8px; }
</style>
</head>
<body>

<h1>MA20轮动策略V8回测报告</h1>
<p class="subtitle">上证50/创业板50/纳斯达克100/沪深300/中证500/中证1000/标普500/科创50 八指数轮动 + 国债避险 &nbsp;|&nbsp; 手续费万分之二/单边 &nbsp;|&nbsp; 2026-07-20</p>

<div class="strategy-box">
  <h2>策略说明（V8 — 八指数轮动版，科创50分段加入）</h2>
  <p><span class="formula">买入因子 = 当日收盘价 / 当日MA20 - 1</span></p>
  <p>1. 每日收盘后计算各参与指数的买入因子，持有<b>买入因子最高</b>的指数</p>
  <p>2. 所有参与指数的买入因子<b>均小于0</b>（均跌破MA20）→ 买入<b>国债指数</b></p>
  <p>3. 次日开盘价执行，每次买卖收<b>万分之二</b>手续费</p>
  <p>4. <b>分段参与规则</b>（因科创50指数2019年12月才发布）：</p>
  <p>&nbsp;&nbsp;&nbsp;• <b>近10年</b>：7股票指数轮动（上证50/创业板50/纳斯达克100/沪深300/中证500/中证1000/标普500）+国债</p>
  <p>&nbsp;&nbsp;&nbsp;• <b>近5/3/1年</b>：8股票指数轮动（上述7个<b>+科创50</b>）+国债</p>
  <div class="good">
    ✅ <b>核心成果</b>：近3年因科创50加入收益提升至<b>111.55%</b>（年化32.01%，夏普0.97），
    近10年加入标普500后最大回撤降至<b>-26.56%</b>（V7为-27.58%），为历版最低回撤。
  </div>
  <div class="info">
    ℹ️ <b>与V7的区别</b>：V7为六指数轮动（无标普500、无科创50）。V8新增标普500（2010年起，近10年涨240%年化14.2%）
    全程参与，科创50（2019年12月起，近3年涨87%）仅在数据可用的近5/3/1年参与。
  </div>
  <div class="warn">
    ⚠️ <b>可比性说明</b>：各时段参与指数数不同（近10年7股票 vs 近5/3/1年8股票），且因内连接+MA20计算，各时段起止日期略有差异，
    故V7与V8的横向对比仅供参考，非严格同条件对比。
  </div>
</div>

<div class="card">
  <h2>策略核心指标速览</h2>
  <table class="core-table">
    <thead>
      <tr>
        <th>时段</th><th>参与股票数</th><th>总收益率</th><th>年化收益</th><th>夏普比率</th>
        <th>最大回撤</th><th>切换次数</th><th>累计手续费</th><th>日期范围</th>
      </tr>
    </thead>
    <tbody id="coreBody"></tbody>
  </table>
</div>

<div class="card">
  <h2>各时段全指标对比（策略 vs 各指数买入持有）</h2>
  <p style="font-size:12px;color:#999;margin-bottom:8px;">"—"表示该指数未参与该时段回测（如近10年的科创50）</p>
  <div class="table-wrap">
  <table id="mainTable">
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th colspan="10" class="group">总收益率</th>
        <th colspan="10" class="group">年化收益率</th>
        <th colspan="10" class="group">最大回撤</th>
        <th colspan="10" class="group">夏普比率</th>
      </tr>
      <tr>
        <th>策略</th>
        <th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th><th>国债</th>
        <th>策略</th>
        <th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th><th>国债</th>
        <th>策略</th>
        <th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th><th>国债</th>
        <th>策略</th>
        <th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th><th>国债</th>
      </tr>
    </thead>
    <tbody id="tableBody"></tbody>
  </table>
  </div>
</div>

<div class="card">
  <h2>全周期净值曲线（近10年）</h2>
  <p style="font-size:13px;color:#666;">含手续费 | 八条净值线对比（近10年无科创50）</p>
  <div class="chart-container"><canvas id="chart10y"></canvas></div>
</div>

<div class="grid-2">
  <div class="card">
    <h2>近3年净值曲线</h2>
    <p style="font-size:12px;color:#999;">含科创50（九条线）</p>
    <div class="chart-container-small"><canvas id="chart3y"></canvas></div>
  </div>
  <div class="card">
    <h2>近1年净值曲线</h2>
    <p style="font-size:12px;color:#999;">含科创50（九条线）</p>
    <div class="chart-container-small"><canvas id="chart1y"></canvas></div>
  </div>
</div>

<div class="card">
  <h2>持仓分布与交易成本</h2>
  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>时段</th><th>切换</th><th>手续费</th>
        <th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th><th>国债</th>
        <th>持仓分布</th>
      </tr>
    </thead>
    <tbody id="posBody"></tbody>
  </table>
  </div>
</div>

<div class="card">
  <h2>V7 vs V8 横向对比</h2>
  <div class="table-wrap">
  <table class="compare-table">
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th colspan="3">V7（六指数：无标普500/科创50）</th>
        <th colspan="3">V8（八指数：+标普500/+科创50）</th>
      </tr>
      <tr>
        <th>总收益</th><th>最大回撤</th><th>夏普</th>
        <th>总收益</th><th>最大回撤</th><th>夏普</th>
      </tr>
    </thead>
    <tbody>
      <tr><td class="period">近10年</td><td class="pos">428.63%</td><td class="neg">-27.58%</td><td>0.84</td><td class="pos">426.77%</td><td class="neg best">-26.56%</td><td>0.85</td></tr>
      <tr><td class="period">近5年</td><td class="pos">139.20%</td><td class="neg">-23.27%</td><td>0.83</td><td class="pos">130.32%</td><td class="neg best">-22.65%</td><td>0.76</td></tr>
      <tr><td class="period">近3年</td><td class="pos">99.79%</td><td class="neg">-23.27%</td><td>0.94</td><td class="pos best">111.55%</td><td class="neg best">-22.65%</td><td class="best">0.97</td></tr>
      <tr><td class="period">近1年</td><td class="pos best">25.42%</td><td class="neg best">-18.37%</td><td class="best">0.97</td><td class="pos">20.27%</td><td class="neg">-21.42%</td><td>0.77</td></tr>
    </tbody>
  </table>
  </div>
  <div class="highlight">
    <b>关键发现：标普500改善回撤，科创50提升近3年收益</b><br><br>
    • <b>近3年提升最显著</b>：科创50近3年涨87.15%（年化26.15%），加入轮动后策略从99.79%提升至111.55%（+11.76%），夏普0.94→0.97，是V8最亮的改进<br>
    • <b>近10年回撤改善</b>：标普500近10年涨240%（年化14.2%），虽收益略逊纳指100(21.68%)，但作为低相关资产分走11%持仓，使最大回撤从-27.58%降至-26.56%（历版最低）<br>
    • <b>近1年有所回落</b>：V8近1年20.27%低于V7的25.42%。科创50近1年涨59%但波动大（回撤-22%），策略追入后频繁切换，且起止日期偏移导致对比非严格同条件<br>
    • <b>持仓分布</b>：纳指100仍是主力（近10年占26%），创业板50占23%，上证50/标普500/中证1000各占约10%，科创50在近3年占17%、近1年占27%——科创50已成为重要轮动标的<br>
    • <b>代价：切换更频繁</b>：近10年切换601次（V7为557次），手续费24.02%（V7为22.28%），更多资产带来更多切换成本<br>
    • <b>沪深300仍边缘化</b>：近10年仅占2%，因与上证50高度相关且bf通常更低，几乎总被替代<br>
    • <b>结论</b>：标普500+科创50的加入使策略回撤控制更优、近3年收益更强，但近1年因切换频繁略有折损。V8在风险调整后收益（夏普）上与V7互有胜负，整体仍是历版顶尖水平
  </div>
</div>

<script>
const DATA = __DATA_JSON__;
const COLORS = {1:'#1e88e5',2:'#43a047',3:'#ff9800',4:'#00acc1',5:'#8e24aa',6:'#ec407a',7:'#f57c00',8:'#00897b',9:'#757575'};
const LABELS = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'};

function cc(v){ return v==null||v==='—' ? 'na' : (v>=0?'pos':'neg'); }
function bc(val, arr){ if(val==null) return ''; const f=arr.filter(x=>x!=null); return val===Math.max(...f)?'best':''; }

const coreBody=document.getElementById('coreBody');
DATA.table_rows.forEach(row=>{
  const tr=document.createElement('tr');
  tr.innerHTML=`<td class="period">${row.period}</td><td>${row.stocks.length}只</td>
    <td class="${cc(row._strat_total)}">${row.strat_total}</td>
    <td class="${cc(row._strat_ann)}">${row.strat_ann}</td>
    <td>${row.strat_sharpe}</td>
    <td class="neg">${row.strat_mdd}</td>
    <td>${row.switches}</td><td class="neg">${row.total_fee}</td>
    <td class="date-range">${row.date_range}</td>`;
  coreBody.appendChild(tr);
});

const tbody=document.getElementById('tableBody');
DATA.table_rows.forEach(row=>{
  const tots=[row._strat_total]; for(let i=1;i<=9;i++) tots.push(row['_bh'+i+'_total']);
  const anns=[row._strat_ann]; for(let i=1;i<=9;i++) anns.push(row['_bh'+i+'_ann']);
  let html=`<td class="period">${row.period}</td>`;
  html+=`<td class="${cc(row._strat_total)} ${bc(row._strat_total,tots)}">${row.strat_total}</td>`;
  for(let i=1;i<=9;i++) html+=`<td class="${cc(row['_bh'+i+'_total'])} ${bc(row['_bh'+i+'_total'],tots)}">${row['bh'+i+'_total']}</td>`;
  html+=`<td class="${cc(row._strat_ann)} ${bc(row._strat_ann,anns)}">${row.strat_ann}</td>`;
  for(let i=1;i<=9;i++) html+=`<td class="${cc(row['_bh'+i+'_ann'])} ${bc(row['_bh'+i+'_ann'],anns)}">${row['bh'+i+'_ann']}</td>`;
  html+=`<td class="neg">${row.strat_mdd}</td>`;
  for(let i=1;i<=9;i++) html+=`<td class="${row['bh'+i+'_mdd']==='—'?'na':'neg'}">${row['bh'+i+'_mdd']}</td>`;
  html+=`<td>${row.strat_sharpe}</td>`;
  for(let i=1;i<=9;i++) html+=`<td>${row['bh'+i+'_sharpe']}</td>`;
  const tr=document.createElement('tr'); tr.innerHTML=html; tbody.appendChild(tr);
});

const posBody=document.getElementById('posBody');
DATA.table_rows.forEach(row=>{
  let html=`<td class="period">${row.period}</td><td>${row.switches}</td><td class="neg">${row.total_fee}</td>`;
  for(let i=1;i<=9;i++) html+=`<td>${row['hold'+i+'_pct']}</td>`;
  let bar='<div class="pos-bar">';
  for(let i=1;i<=9;i++){ const p=row['_hold'+i+'_pct']; bar+=`<div style="width:${p*100}%;background:${COLORS[i]}">${p>0.08?row['hold'+i+'_pct']:''}</div>`; }
  bar+='</div>';
  html+=`<td style="min-width:300px;">${bar}</td>`;
  const tr=document.createElement('tr'); tr.innerHTML=html; posBody.appendChild(tr);
});

Chart.defaults.font.family="'PingFang SC','Microsoft YaHei',sans-serif";
Chart.defaults.font.size=11;

function makeChart(canvasId, cd, allIds, showLegend){
  const ctx=document.getElementById(canvasId); if(!ctx) return;
  const datasets=[{label:'轮动策略V8',data:cd.strat,borderColor:'#e53935',backgroundColor:'rgba(229,57,53,0.08)',borderWidth:2.5,pointRadius:0,fill:true,tension:0.1}];
  allIds.forEach(i=>{ datasets.push({label:LABELS[i],data:cd['bh'+i],borderColor:COLORS[i],borderWidth:1.2,pointRadius:0,fill:false,tension:0.1}); });
  return new Chart(ctx,{type:'line',data:{labels:cd.dates,datasets},
    options:{responsive:true,maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{legend:{display:showLegend,position:'top',labels:{boxWidth:12,font:{size:11}}},
        tooltip:{callbacks:{label:c=>c.dataset.label+': '+c.parsed.y.toFixed(4)}}},
      scales:{x:{ticks:{maxTicksLimit:8,maxRotation:0},grid:{display:false}},
        y:{ticks:{callback:v=>v.toFixed(2)},grid:{color:'#f0f0f0'}}}}});
}

const r10=DATA.chart_data['近10年'];
if(r10) makeChart('chart10y',r10,[1,2,3,4,5,6,7,9],true);
const r3=DATA.chart_data['近3年'];
if(r3) makeChart('chart3y',r3,[1,2,3,4,5,6,7,8,9],false);
const r1=DATA.chart_data['近1年'];
if(r1) makeChart('chart1y',r1,[1,2,3,4,5,6,7,8,9],false);
</script>

</body>
</html>
'''

html = HTML.replace('__DATA_JSON__', data_json)

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/MA20轮动策略V8回测报告.html','w',encoding='utf-8') as f:
    f.write(html)
print("HTML报告已生成: MA20轮动策略V8回测报告.html")
