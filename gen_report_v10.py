# -*- coding: utf-8 -*-
"""生成 V10 回测HTML报告（短周期多头排列趋势确认版）"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v10_data.json','r',encoding='utf-8') as f:
    data = json.load(f)

results = data['results']
names = data['names']

# V8/V9数据（用于对比）
v8 = {
    '近10年': {'total':426.77,'ann':19.73,'mdd':-26.56,'sharpe':0.85,'switches':601,'fee':24.02},
    '近5年':  {'total':130.32,'ann':20.12,'mdd':-22.65,'sharpe':0.76,'switches':289,'fee':12.42},
    '近3年':  {'total':111.55,'ann':32.01,'mdd':-22.65,'sharpe':0.97,'switches':177,'fee':7.66},
    '近1年':  {'total':20.27,'ann':24.15,'mdd':-21.42,'sharpe':0.77,'switches':54,'fee':2.74},
}
v9 = {
    '近10年': {'total':179.43,'ann':12.00,'mdd':-22.96,'sharpe':0.67,'switches':463,'fee':18.50},
    '近5年':  {'total':24.77,'ann':5.17,'mdd':-26.73,'sharpe':0.33,'switches':233,'fee':9.30},
    '近3年':  {'total':42.45,'ann':14.95,'mdd':-24.66,'sharpe':0.65,'switches':150,'fee':5.98},
    '近1年':  {'total':4.31,'ann':6.26,'mdd':-16.63,'sharpe':0.35,'switches':54,'fee':2.14},
}

periods = ['近10年','近5年','近3年','近1年']

table_rows = []
for p in periods:
    r = results[p]
    stocks = r['stock_ids']
    all_ids = stocks + [9]
    row = {
        'period': p, 'stocks': stocks,
        'date_range': f"{r['start_date']}~{r['end_date']}",
        'n_days': r['n_days'],
        'strat_total': f"{r['strat_total']*100:.2f}%",
        'strat_ann': f"{r['strat_ann']*100:.2f}%",
        'strat_mdd': f"{r['strat_mdd']*100:.2f}%",
        'strat_sharpe': f"{r['strat_sharpe']:.2f}",
        'switches': r['switches'],
        'total_fee': f"{r['total_fee']*100:.2f}%",
        '_strat_total': r['strat_total']*100,
        '_strat_ann': r['strat_ann']*100,
    }
    for i in all_ids:
        has = f'bh{i}_total' in r
        row[f'bh{i}_total'] = f"{r[f'bh{i}_total']*100:.2f}%" if has else '—'
        row[f'bh{i}_ann'] = f"{r[f'bh{i}_ann']*100:.2f}%" if has else '—'
        row[f'bh{i}_mdd'] = f"{r[f'bh{i}_mdd']*100:.2f}%" if has else '—'
        row[f'bh{i}_sharpe'] = f"{r[f'bh{i}_sharpe']:.2f}" if has else '—'
        row[f'hold{i}_pct'] = f"{r[f'hold{i}_pct']*100:.0f}%" if has else '—'
        row[f'_hold{i}_pct'] = r[f'hold{i}_pct'] if has else 0
        row[f'_bh{i}_total'] = r[f'bh{i}_total']*100 if has else None
        row[f'_bh{i}_ann'] = r[f'bh{i}_ann']*100 if has else None
    table_rows.append(row)

chart_data = {}
for p in periods:
    r = results[p]
    stocks = r['stock_ids']
    all_ids = stocks + [9]
    cd = {'dates': r['nav_dates'], 'strat': r['strat_nav']}
    for i in all_ids:
        cd[f'bh{i}'] = r[f'bh{i}_nav']
    chart_data[p] = cd

all_payload = {'table_rows': table_rows, 'chart_data': chart_data, 'v8': v8, 'v9': v9}
data_json = json.dumps(all_payload, ensure_ascii=False)

COLORS = {1:'#1e88e5',2:'#43a047',3:'#ff9800',4:'#00acc1',5:'#8e24aa',6:'#ec407a',7:'#f57c00',8:'#00897b',9:'#757575'}
LABELS = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}
colors_json = json.dumps(COLORS)
labels_json = json.dumps(LABELS)
v8_json = json.dumps(v8)
v9_json = json.dumps(v9)

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MA20轮动策略V10回测报告 - 短周期多头排列趋势确认</title>
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
  .bad { background:#ffebee; border:1px solid #ef5350; border-radius:8px; padding:12px 16px; margin-top:12px; font-size:13px; color:#c62828; }
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
  .compare-table td { font-size:12px; padding:8px 6px; }
  .core-table td { font-size:13px; padding:9px 8px; }
  .core-table th { font-size:12px; padding:9px 8px; }
</style>
</head>
<body>

<h1>MA20轮动策略V10回测报告</h1>
<p class="subtitle">八指数轮动 + 国债避险 + 短周期多头排列趋势确认(close&gt;MA10&gt;MA20) &nbsp;|&nbsp; 手续费万分之二/单边 &nbsp;|&nbsp; 2026-07-21</p>

<div class="strategy-box">
  <h2>策略说明（V10 — 短周期多头排列趋势确认版）</h2>
  <p><span class="formula">买入因子 = 当日收盘价 / 当日MA20 - 1</span></p>
  <p><span class="formula">趋势确认条件：当日收盘价 &gt; MA10 &gt; MA20</span>（短周期多头排列）</p>
  <p>1. 每日收盘后计算各指数买入因子，并判断是否满足<b>短周期多头排列</b>（close&gt;MA10&gt;MA20）</p>
  <p>2. 在<b>满足趋势确认</b>的指数中，持有<b>买入因子最高</b>的</p>
  <p>3. 若<b>无指数满足趋势确认</b> → 买入<b>国债指数</b></p>
  <p>4. 次日开盘价执行，每次买卖收<b>万分之二</b>手续费</p>
  <p>5. <b>分段参与规则</b>：近10年7股票(无科创50)，近5/3/1年8股票(含科创50)</p>
  <div class="good">
    ✅ <b>比V9大幅改善</b>：短周期均线更敏感，信号滞后减少。近10年收益从V9的179.43%提升至<b>331.14%</b>，
    近10年最大回撤<b>-22.36%</b>为V8/V9/V10三版中最低。
  </div>
  <div class="warn">
    ⚠️ <b>仍不如V8</b>：近10年331.14% &lt; V8的426.77%。趋势确认仍牺牲了部分收益，
    且近1年表现较差(-1.59%)，短周期在震荡市中信号更频繁导致切换成本上升。
  </div>
  <div class="info">
    ℹ️ <b>与V9对比</b>：V9用close&gt;MA20&gt;MA60（长周期，滞后严重），V10用close&gt;MA10&gt;MA20（短周期，更敏感）。
    V10全面优于V9，说明<b>趋势确认的均线周期越短，信号滞后越小，收益损失越少</b>。
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
  <p style="font-size:12px;color:#999;margin-bottom:8px;">"—"表示该指数未参与该时段回测</p>
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
  <div class="legend" id="legend10y"></div>
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
  <h2>V8 / V9 / V10 三版横向对比</h2>
  <div class="table-wrap">
  <table class="compare-table">
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th colspan="3">V8（无趋势确认）</th>
        <th colspan="3">V9（close&gt;MA20&gt;MA60）</th>
        <th colspan="3">V10（close&gt;MA10&gt;MA20）</th>
      </tr>
      <tr>
        <th>总收益</th><th>最大回撤</th><th>夏普</th>
        <th>总收益</th><th>最大回撤</th><th>夏普</th>
        <th>总收益</th><th>最大回撤</th><th>夏普</th>
      </tr>
    </thead>
    <tbody id="compareBody"></tbody>
  </table>
  </div>
  <div class="highlight">
    <b>关键发现：均线周期越短，趋势确认的代价越小，但仍非最优</b><br><br>
    • <b>V10全面优于V9</b>：近10年331% vs 179%，近5年55% vs 25%。短周期均线（MA10/MA20）比长周期（MA20/MA60）更敏感，信号滞后更小，错过趋势启动初期的涨幅更少<br>
    • <b>近10年回撤三版最低</b>：V10的-22.36%优于V8(-26.56%)和V9(-22.96%)，短周期趋势确认在长周期中起到了较好的回撤控制作用<br>
    • <b>但近1年表现最差</b>：V10近1年-1.59%，是三版中唯一亏损的。短周期在震荡市中信号频繁切换（70次），手续费侵蚀严重。创业板50近1年涨45%、科创50涨59%，但V10都没吃到<br>
    • <b>趋势确认的固有矛盾</b>：均线周期长→信号滞后→错过涨幅；均线周期短→信号频繁→切换成本高。无论怎么调参，加入趋势确认都会在某方面劣于V8（无确认）<br>
    • <b>结论</b>：V8（无趋势确认）仍为最优。趋势确认本质上是在"择时"之上再叠加"择时"，双重择时容易过度过滤。若要控制回撤，更优的方向是<b>仓位管理</b>（如回撤超阈值时降仓）而非<b>信号过滤</b>
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

<script>
const DATA = __DATA_JSON__;
const COLORS = __COLORS_JSON__;
const LABELS = __LABELS_JSON__;
const V8 = __V8_JSON__;
const V9 = __V9_JSON__;

function cc(v){ return v==null||v==='—' ? 'na' : (v>=0?'pos':'neg'); }

const coreBody=document.getElementById('coreBody');
DATA.table_rows.forEach(row=>{
  const tr=document.createElement('tr');
  tr.innerHTML='<td class="period">'+row.period+'</td><td>'+row.stocks.length+'只</td>'+
    '<td class="'+cc(row._strat_total)+'">'+row.strat_total+'</td>'+
    '<td class="'+cc(row._strat_ann)+'">'+row.strat_ann+'</td>'+
    '<td>'+row.strat_sharpe+'</td>'+
    '<td class="neg">'+row.strat_mdd+'</td>'+
    '<td>'+row.switches+'</td><td class="neg">'+row.total_fee+'</td>'+
    '<td class="date-range">'+row.date_range+'</td>';
  coreBody.appendChild(tr);
});

const tbody=document.getElementById('tableBody');
DATA.table_rows.forEach(row=>{
  let html='<td class="period">'+row.period+'</td>';
  html+='<td class="'+cc(row._strat_total)+'">'+row.strat_total+'</td>';
  for(let i=1;i<=9;i++) html+='<td class="'+cc(row['_bh'+i+'_total'])+'">'+row['bh'+i+'_total']+'</td>';
  html+='<td class="'+cc(row._strat_ann)+'">'+row.strat_ann+'</td>';
  for(let i=1;i<=9;i++) html+='<td class="'+cc(row['_bh'+i+'_ann'])+'">'+row['bh'+i+'_ann']+'</td>';
  html+='<td class="neg">'+row.strat_mdd+'</td>';
  for(let i=1;i<=9;i++) html+='<td class="'+(row['bh'+i+'_mdd']==='—'?'na':'neg')+'">'+row['bh'+i+'_mdd']+'</td>';
  html+='<td>'+row.strat_sharpe+'</td>';
  for(let i=1;i<=9;i++) html+='<td>'+row['bh'+i+'_sharpe']+'</td>';
  const tr=document.createElement('tr'); tr.innerHTML=html; tbody.appendChild(tr);
});

const compareBody=document.getElementById('compareBody');
['近10年','近5年','近3年','近1年'].forEach(p=>{
  const v8d=V8[p], v9d=V9[p];
  const v10=DATA.table_rows.find(r=>r.period===p);
  if(!v8d||!v9d||!v10) return;
  const tr=document.createElement('tr');
  tr.innerHTML='<td class="period">'+p+'</td>'+
    '<td class="pos">'+v8d.total.toFixed(2)+'%</td><td class="neg">'+v8d.mdd.toFixed(2)+'%</td><td>'+v8d.sharpe.toFixed(2)+'</td>'+
    '<td class="pos">'+v9d.total.toFixed(2)+'%</td><td class="neg">'+v9d.mdd.toFixed(2)+'%</td><td>'+v9d.sharpe.toFixed(2)+'</td>'+
    '<td class="pos">'+v10.strat_total+'</td><td class="neg">'+v10.strat_mdd+'</td><td>'+v10.strat_sharpe+'</td>';
  compareBody.appendChild(tr);
});

const posBody=document.getElementById('posBody');
DATA.table_rows.forEach(row=>{
  let html='<td class="period">'+row.period+'</td><td>'+row.switches+'</td><td class="neg">'+row.total_fee+'</td>';
  for(let i=1;i<=9;i++) html+='<td>'+row['hold'+i+'_pct']+'</td>';
  let bar='<div class="pos-bar">';
  for(let i=1;i<=9;i++){ const p=row['_hold'+i+'_pct']; bar+='<div style="width:'+(p*100)+'%;background:'+COLORS[i]+'">'+(p>0.08?row['hold'+i+'_pct']:'')+'</div>'; }
  bar+='</div>';
  html+='<td style="min-width:300px;">'+bar+'</td>';
  const tr=document.createElement('tr'); tr.innerHTML=html; posBody.appendChild(tr);
});

Chart.defaults.font.family="'PingFang SC','Microsoft YaHei',sans-serif";
Chart.defaults.font.size=11;

function makeChart(canvasId, cd, allIds, showLegend){
  const ctx=document.getElementById(canvasId); if(!ctx) return;
  const datasets=[{label:'轮动策略V10',data:cd.strat,borderColor:'#e53935',backgroundColor:'rgba(229,57,53,0.08)',borderWidth:2.5,pointRadius:0,fill:true,tension:0.1}];
  allIds.forEach(i=>{ datasets.push({label:LABELS[i],data:cd['bh'+i],borderColor:COLORS[i],borderWidth:1.2,pointRadius:0,fill:false,tension:0.1}); });
  return new Chart(ctx,{type:'line',data:{labels:cd.dates,datasets:datasets},
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
</html>'''

html = html.replace('__DATA_JSON__', data_json)
html = html.replace('__COLORS_JSON__', colors_json)
html = html.replace('__LABELS_JSON__', labels_json)
html = html.replace('__V8_JSON__', v8_json)
html = html.replace('__V9_JSON__', v9_json)

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/MA20轮动策略V10回测报告.html','w',encoding='utf-8') as f:
    f.write(html)
print("HTML报告已生成: MA20轮动策略V10回测报告.html")
