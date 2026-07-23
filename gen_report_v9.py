# -*- coding: utf-8 -*-
"""生成 V9 回测HTML报告（多头排列趋势确认版）"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v9_data.json','r',encoding='utf-8') as f:
    data = json.load(f)

results = data['results']
names = data['names']

# V8数据（用于对比）
v8 = {
    '近10年': {'total':426.77,'ann':19.73,'mdd':-26.56,'sharpe':0.85,'switches':601,'fee':24.02},
    '近5年':  {'total':130.32,'ann':20.12,'mdd':-22.65,'sharpe':0.76,'switches':289,'fee':12.42},
    '近3年':  {'total':111.55,'ann':32.01,'mdd':-22.65,'sharpe':0.97,'switches':177,'fee':7.66},
    '近1年':  {'total':20.27,'ann':24.15,'mdd':-21.42,'sharpe':0.77,'switches':54,'fee':2.74},
}

periods = ['近10年','近5年','近3年','近1年']

# 构建表格行数据
table_rows = []
for p in periods:
    r = results[p]
    stocks = r['stock_ids']
    all_ids = stocks + [9]
    row = {
        'period': p,
        'stocks': stocks,
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

# 图表数据
chart_data = {}
for p in periods:
    r = results[p]
    stocks = r['stock_ids']
    all_ids = stocks + [9]
    cd = {'dates': r['nav_dates'], 'strat': r['strat_nav']}
    for i in all_ids:
        cd[f'bh{i}'] = r[f'bh{i}_nav']
    chart_data[p] = cd

all_payload = {'table_rows': table_rows, 'chart_data': chart_data, 'v8': v8}
data_json = json.dumps(all_payload, ensure_ascii=False)

COLORS = {1:'#1e88e5',2:'#43a047',3:'#ff9800',4:'#00acc1',5:'#8e24aa',6:'#ec407a',7:'#f57c00',8:'#00897b',9:'#757575'}
LABELS = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}
colors_json = json.dumps(COLORS)
labels_json = json.dumps(LABELS)

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MA20轮动策略V9回测报告 - 多头排列趋势确认</title>
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
  th.na { background:#f5f5f5; color:#bbb; }
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

<h1>MA20轮动策略V9回测报告</h1>
<p class="subtitle">八指数轮动 + 国债避险 + 多头排列趋势确认(close>MA20>MA60) &nbsp;|&nbsp; 手续费万分之二/单边 &nbsp;|&nbsp; 2026-07-20</p>

<div class="strategy-box">
  <h2>策略说明（V9 — 多头排列趋势确认版）</h2>
  <p><span class="formula">买入因子 = 当日收盘价 / 当日MA20 - 1</span></p>
  <p><span class="formula">趋势确认条件：当日收盘价 &gt; MA20 &gt; MA60</span>（多头排列）</p>
  <p>1. 每日收盘后计算各指数买入因子，并判断是否满足<b>多头排列</b>（close&gt;MA20&gt;MA60）</p>
  <p>2. 在<b>满足趋势确认</b>的指数中，持有<b>买入因子最高</b>的</p>
  <p>3. 若<b>无指数满足趋势确认</b> → 买入<b>国债指数</b></p>
  <p>4. 次日开盘价执行，每次买卖收<b>万分之二</b>手续费</p>
  <p>5. <b>分段参与规则</b>（因科创50指数2019年12月才发布）：</p>
  <p>&nbsp;&nbsp;&nbsp;• <b>近10年</b>：7股票指数轮动（上证50/创业板50/纳斯达克100/沪深300/中证500/中证1000/标普500）+国债</p>
  <p>&nbsp;&nbsp;&nbsp;• <b>近5/3/1年</b>：8股票指数轮动（上述7个<b>+科创50</b>）+国债</p>
  <div class="good">
    ✅ <b>回撤改善</b>：近10年最大回撤从V8的-26.56%降至<b>-22.96%</b>，近1年从-21.42%降至<b>-16.63%</b>。
    趋势确认过滤了"假突破"，在下跌行情中更快转国债避险。
  </div>
  <div class="bad">
    ❌ <b>收益大幅下降</b>：近10年收益从V8的426.77%降至<b>179.43%</b>，近5年从130.32%降至<b>24.77%</b>。
    原因：趋势确认条件过严，要求close&gt;MA20&gt;MA60意味着必须等多头排列完全确立才买入，错过趋势启动初期的涨幅。
  </div>
  <div class="info">
    ℹ️ <b>切换减少</b>：近10年切换从601次降至463次，手续费从24.02%降至18.50%。趋势确认起到了"信号平滑"作用。
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
  <h2>V8 vs V9 横向对比（加入趋势确认的影响）</h2>
  <div class="table-wrap">
  <table class="compare-table">
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th colspan="3">V8（无趋势确认）</th>
        <th colspan="3">V9（+close&gt;MA20&gt;MA60）</th>
        <th colspan="2">变化</th>
      </tr>
      <tr>
        <th>总收益</th><th>最大回撤</th><th>夏普</th>
        <th>总收益</th><th>最大回撤</th><th>夏普</th>
        <th>收益差</th><th>回撤差</th>
      </tr>
    </thead>
    <tbody id="compareBody"></tbody>
  </table>
  </div>
  <div class="highlight">
    <b>关键发现：趋势确认是双刃剑——降回撤但牺牲更多收益</b><br><br>
    • <b>收益全面下降</b>：四时段收益全部低于V8。近10年426.77%→179.43%（-247%），近5年130.32%→24.77%（-106%），近3年111.55%→42.45%（-69%）<br>
    • <b>回撤部分改善</b>：近10年-26.56%→-22.96%（改善3.6%），近1年-21.42%→-16.63%（改善4.8%），但近5年-22.65%→-26.73%（恶化），近3年-22.65%→-24.66%（恶化）<br>
    • <b>根源：信号滞后</b>。要求close&gt;MA20&gt;MA60意味着：①MA20需先上穿MA60（这本身滞后）②close需在MA20之上。双重条件使买入信号比V8晚数天到数周，错过趋势启动初期的快速上涨<br>
    • <b>切换减少但不够</b>：近10年切换601→463次（-23%），手续费24%→18.5%，但收益下降幅度远大于手续费节省<br>
    • <b>国债持仓增加</b>：近10年国债占比25%（V8约15%），更多时间在"等待确认"，错失行情<br>
    • <b>结论</b>：close&gt;MA20&gt;MA60条件<b>过于保守</b>。可作为<b>辅助过滤器</b>而非硬性门槛，或放松为单一条件（如仅close&gt;MA20，或仅MA20&gt;MA60）。V8仍为当前最优版本
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

function cc(v){ return v==null||v==='—' ? 'na' : (v>=0?'pos':'neg'); }

// 核心指标表
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

// 全指标表
const tbody=document.getElementById('tableBody');
DATA.table_rows.forEach(row=>{
  const tots=[row._strat_total]; for(let i=1;i<=9;i++) tots.push(row['_bh'+i+'_total']);
  const anns=[row._strat_ann]; for(let i=1;i<=9;i++) anns.push(row['_bh'+i+'_ann']);
  let html='<td class="period">'+row.period+'</td>';
  // 总收益
  html+='<td class="'+cc(row._strat_total)+'">'+row.strat_total+'</td>';
  for(let i=1;i<=9;i++) html+='<td class="'+cc(row['_bh'+i+'_total'])+'">'+row['bh'+i+'_total']+'</td>';
  // 年化
  html+='<td class="'+cc(row._strat_ann)+'">'+row.strat_ann+'</td>';
  for(let i=1;i<=9;i++) html+='<td class="'+cc(row['_bh'+i+'_ann'])+'">'+row['bh'+i+'_ann']+'</td>';
  // 回撤
  html+='<td class="neg">'+row.strat_mdd+'</td>';
  for(let i=1;i<=9;i++) html+='<td class="'+(row['bh'+i+'_mdd']==='—'?'na':'neg')+'">'+row['bh'+i+'_mdd']+'</td>';
  // 夏普
  html+='<td>'+row.strat_sharpe+'</td>';
  for(let i=1;i<=9;i++) html+='<td>'+row['bh'+i+'_sharpe']+'</td>';
  const tr=document.createElement('tr'); tr.innerHTML=html; tbody.appendChild(tr);
});

// V8 vs V9 对比表
const compareBody=document.getElementById('compareBody');
['近10年','近5年','近3年','近1年'].forEach(p=>{
  const v8d=V8[p];
  const v9=DATA.table_rows.find(r=>r.period===p);
  if(!v8d||!v9) return;
  const v9total=parseFloat(v9.strat_total);
  const v9mdd=parseFloat(v9.strat_mdd);
  const diff_t=v9total-v8d.total;
  const diff_m=v9mdd-v8d.mdd;
  const tr=document.createElement('tr');
  tr.innerHTML='<td class="period">'+p+'</td>'+
    '<td class="pos">'+v8d.total.toFixed(2)+'%</td><td class="neg">'+v8d.mdd.toFixed(2)+'%</td><td>'+v8d.sharpe.toFixed(2)+'</td>'+
    '<td class="pos">'+v9.strat_total+'</td><td class="neg">'+v9.strat_mdd+'</td><td>'+v9.strat_sharpe+'</td>'+
    '<td class="'+(diff_t>=0?'pos':'neg')+'">'+(diff_t>=0?'+':'')+diff_t.toFixed(2)+'%</td>'+
    '<td class="'+(diff_m>=0?'neg':'pos')+'">'+(diff_m>=0?'+':'')+diff_m.toFixed(2)+'%</td>';
  compareBody.appendChild(tr);
});

// 持仓表
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

// 图表
Chart.defaults.font.family="'PingFang SC','Microsoft YaHei',sans-serif";
Chart.defaults.font.size=11;

function makeChart(canvasId, cd, allIds, showLegend){
  const ctx=document.getElementById(canvasId); if(!ctx) return;
  const datasets=[{label:'轮动策略V9',data:cd.strat,borderColor:'#e53935',backgroundColor:'rgba(229,57,53,0.08)',borderWidth:2.5,pointRadius:0,fill:true,tension:0.1}];
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
html = html.replace('__V8_JSON__', json.dumps(v8))

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/MA20轮动策略V9回测报告.html','w',encoding='utf-8') as f:
    f.write(html)
print("HTML报告已生成: MA20轮动策略V9回测报告.html")
