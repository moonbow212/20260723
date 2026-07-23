# -*- coding: utf-8 -*-
"""生成 V11 回测HTML报告（V8 + 最小持仓5天约束）"""
import json

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v11_data.json','r',encoding='utf-8') as f:
    data = json.load(f)

results = data['results']
names = data['names']
MIN_HOLD = data.get('min_hold', 5)

# V8数据（用于对比）
v8 = {
    '近10年': {'total':426.77,'ann':19.73,'mdd':-26.56,'sharpe':0.85,'switches':601,'fee':24.02,'blocked':0},
    '近5年':  {'total':130.32,'ann':20.12,'mdd':-22.65,'sharpe':0.76,'switches':289,'fee':12.42,'blocked':0},
    '近3年':  {'total':111.55,'ann':32.01,'mdd':-22.65,'sharpe':0.97,'switches':177,'fee':7.66,'blocked':0},
    '近1年':  {'total':20.27,'ann':24.15,'mdd':-21.42,'sharpe':0.77,'switches':54,'fee':2.74,'blocked':0},
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
        'blocked_switches': r.get('blocked_switches', 0),
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

all_payload = {'table_rows': table_rows, 'chart_data': chart_data, 'v8': v8, 'min_hold': MIN_HOLD}
data_json = json.dumps(all_payload, ensure_ascii=False)

# V11核心数据用于对比块
v11_summary = {}
for p in periods:
    r = results[p]
    v11_summary[p] = {
        'total': r['strat_total']*100,
        'ann': r['strat_ann']*100,
        'mdd': r['strat_mdd']*100,
        'sharpe': r['strat_sharpe'],
        'switches': r['switches'],
        'blocked': r.get('blocked_switches', 0),
        'fee': r['total_fee']*100,
    }

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MA20轮动策略V11回测报告 - 最小持仓5天约束</title>
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
  table { border-collapse:collapse; font-size:11px; min-width:100%; }
  th { background:#f0f2f5; padding:7px 5px; text-align:center; font-weight:600; color:#555; white-space:nowrap; }
  th.group { background:#e8eaf6; color:#333; }
  td { padding:7px 5px; text-align:center; border-bottom:1px solid #eee; white-space:nowrap; }
  td.period { font-weight:700; color:#333; font-size:12px; }
  td.date-range { font-size:9px; color:#999; }
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

<h1>MA20轮动策略V11回测报告</h1>
<p class="subtitle">V8 + 最小持仓5天约束 &nbsp;|&nbsp; 八指数轮动+国债避险 &nbsp;|&nbsp; 手续费万分之二/单边 &nbsp;|&nbsp; 2026-07-21</p>

<div class="strategy-box">
  <h2>策略说明（V11 — V8基础+最小持仓5天约束）</h2>
  <p><span class="formula">买入因子 = 当日收盘价 / 当日MA20 - 1</span></p>
  <p>1. 每日收盘后计算各参与指数的买入因子，持有<b>买入因子最高</b>的指数（信号与V8完全一致）</p>
  <p>2. 所有参与指数的买入因子<b>均小于0</b>（均跌破MA20）→ 买入<b>国债指数</b></p>
  <p>3. 次日开盘价执行，每次买卖收<b>万分之二</b>手续费</p>
  <p>4. <b>【新增约束】最小持仓5天</b>：当前持仓不满5个交易日时，即使出现更优信号也维持现状，满5天后才允许切换</p>
  <p>5. <b>分段参与</b>：近10年用7股票指数（无科创50），近5/3/1年用8股票指数（含科创50）</p>
  <div class="bad">
    ❌ <b>核心结论：最小持仓5天约束得不偿失</b>。手续费确实降了46%（近10年24%→13%），但收益暴跌更多（近10年426%→93%），
    回撤反而恶化（-26%→-43%）。MA20轮动高度依赖及时切换到强势资产，5天延迟导致错过主升浪。
  </div>
</div>

<div class="card">
  <h2>策略核心指标速览</h2>
  <table class="core-table">
    <thead>
      <tr>
        <th>时段</th><th>总收益率</th><th>年化收益</th><th>夏普比率</th>
        <th>最大回撤</th><th>实际切换</th><th>被阻止切换</th><th>累计手续费</th><th>日期范围</th>
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
  <h2>持仓分布与交易成本</h2>
  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>时段</th><th>切换</th><th>被阻止</th><th>手续费</th>
        <th>上证50</th><th>创业板50</th><th>纳指100</th><th>沪深300</th><th>中证500</th><th>中证1000</th><th>标普500</th><th>科创50</th><th>国债</th>
        <th>持仓分布</th>
      </tr>
    </thead>
    <tbody id="posBody"></tbody>
  </table>
  </div>
</div>

<div class="card">
  <h2>V8 vs V11 横向对比（最小持仓5天约束的影响）</h2>
  <div class="table-wrap">
  <table class="compare-table">
    <thead>
      <tr>
        <th rowspan="2">时段</th>
        <th colspan="4">V8（无持仓约束）</th>
        <th colspan="4">V11（最小持仓5天）</th>
        <th colspan="3">变化</th>
      </tr>
      <tr>
        <th>总收益</th><th>最大回撤</th><th>夏普</th><th>切换/手续费</th>
        <th>总收益</th><th>最大回撤</th><th>夏普</th><th>切换/手续费</th>
        <th>收益差</th><th>回撤差</th><th>手续费省</th>
      </tr>
    </thead>
    <tbody id="compareBody"></tbody>
  </table>
  </div>
  <div class="highlight">
    <b>关键发现：降成本成功，但收益代价远超节省</b><br><br>
    • <b>切换次数减半</b>：近10年切换从601次降到325次，被阻止590次切换。手续费从24.02%降到12.98%，节省11.04%<br>
    • <b>但收益暴跌</b>：近10年总收益从426.77%暴跌到93.34%，损失333%。省下的11%手续费远补不回333%的收益损失<br>
    • <b>回撤反而恶化</b>：近10年最大回撤从-26.56%恶化到-43.14%。因为持仓被锁定5天，遇到急跌时无法及时切换到国债避险<br>
    • <b>根源：MA20轮动高度依赖时效性</b>。当某指数快速走强时bf迅速变高，5天延迟导致错过主升浪最肥的一段；当市场急跌时5天延迟导致来不及避险<br>
    • <b>近1年也恶化</b>：20.27%→12.48%，创业板50近1年涨45%但策略因持仓锁定没吃到完整涨幅<br>
    • <b>结论</b>：5天对MA20轮动策略太长了。如果要降成本，建议改用"切换阈值"（只有新资产bf高出当前X%才切换），而非硬性锁仓。这样能过滤无谓切换但保留及时跟进强势资产的能力
  </div>
</div>

<script>
const DATA = __DATA_JSON__;
const COLORS = {1:'#1e88e5',2:'#43a047',3:'#ff9800',4:'#00acc1',5:'#8e24aa',6:'#ec407a',7:'#f57c00',8:'#00897b',9:'#757575'};
const LABELS = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'};

function cc(v){ return v==null||v==='—' ? 'na' : (v>=0?'pos':'neg'); }
function bc(val, arr){ if(val==null) return ''; const f=arr.filter(x=>x!=null); return val===Math.max(...f)?'best':''; }

// 核心指标表
const coreBody=document.getElementById('coreBody');
DATA.table_rows.forEach(row=>{
  const tr=document.createElement('tr');
  tr.innerHTML='<td class="period">'+row.period+'</td>'+
    '<td class="'+cc(row._strat_total)+'">'+row.strat_total+'</td>'+
    '<td class="'+cc(row._strat_ann)+'">'+row.strat_ann+'</td>'+
    '<td>'+row.strat_sharpe+'</td>'+
    '<td class="neg">'+row.strat_mdd+'</td>'+
    '<td>'+row.switches+'</td>'+
    '<td style="color:#e65100;">'+row.blocked_switches+'</td>'+
    '<td class="neg">'+row.total_fee+'</td>'+
    '<td class="date-range">'+row.date_range+'</td>';
  coreBody.appendChild(tr);
});

// 全指标表
const tbody=document.getElementById('tableBody');
DATA.table_rows.forEach(row=>{
  const tots=[row._strat_total]; for(let i=1;i<=9;i++) tots.push(row['_bh'+i+'_total']);
  const anns=[row._strat_ann]; for(let i=1;i<=9;i++) anns.push(row['_bh'+i+'_ann']);
  let html='<td class="period">'+row.period+'</td>';
  html+='<td class="'+cc(row._strat_total)+' '+bc(row._strat_total,tots)+'">'+row.strat_total+'</td>';
  for(let i=1;i<=9;i++) html+='<td class="'+cc(row['_bh'+i+'_total'])+' '+bc(row['_bh'+i+'_total'],tots)+'">'+row['bh'+i+'_total']+'</td>';
  html+='<td class="'+cc(row._strat_ann)+' '+bc(row._strat_ann,anns)+'">'+row.strat_ann+'</td>';
  for(let i=1;i<=9;i++) html+='<td class="'+cc(row['_bh'+i+'_ann'])+' '+bc(row['_bh'+i+'_ann'],anns)+'">'+row['bh'+i+'_ann']+'</td>';
  html+='<td class="neg">'+row.strat_mdd+'</td>';
  for(let i=1;i<=9;i++) html+='<td class="'+(row['bh'+i+'_mdd']==='—'?'na':'neg')+'">'+row['bh'+i+'_mdd']+'</td>';
  html+='<td>'+row.strat_sharpe+'</td>';
  for(let i=1;i<=9;i++) html+='<td>'+row['bh'+i+'_sharpe']+'</td>';
  const tr=document.createElement('tr'); tr.innerHTML=html; tbody.appendChild(tr);
});

// 持仓表
const posBody=document.getElementById('posBody');
DATA.table_rows.forEach(row=>{
  let html='<td class="period">'+row.period+'</td><td>'+row.switches+'</td><td style="color:#e65100;">'+row.blocked_switches+'</td><td class="neg">'+row.total_fee+'</td>';
  for(let i=1;i<=9;i++) html+='<td>'+row['hold'+i+'_pct']+'</td>';
  let bar='<div class="pos-bar">';
  for(let i=1;i<=9;i++){ const p=row['_hold'+i+'_pct']; bar+='<div style="width:'+(p*100)+'%;background:'+COLORS[i]+'">'+(p>0.08?row['hold'+i+'_pct']:'')+'</div>'; }
  bar+='</div>';
  html+='<td style="min-width:300px;">'+bar+'</td>';
  const tr=document.createElement('tr'); tr.innerHTML=html; posBody.appendChild(tr);
});

// 对比表
const v8=DATA.v8;
const compareBody=document.getElementById('compareBody');
const v11data={
  '近10年':{total:93.34,mdd:-43.14,sharpe:0.43,switches:325,fee:12.98},
  '近5年':{total:46.96,mdd:-25.46,sharpe:0.46,switches:156,fee:6.22},
  '近3年':{total:37.68,mdd:-25.46,sharpe:0.57,switches:93,fee:3.70},
  '近1年':{total:12.48,mdd:-22.84,sharpe:0.56,switches:33,fee:1.30},
};
['近10年','近5年','近3年','近1年'].forEach(p=>{
  const a=v8[p], b=v11data[p];
  const diffTotal=b.total-a.total;
  const diffMdd=b.mdd-a.mdd;
  const feeSaved=a.fee-b.fee;
  const tr=document.createElement('tr');
  tr.innerHTML='<td class="period">'+p+'</td>'+
    '<td class="pos">'+a.total.toFixed(2)+'%</td><td class="neg">'+a.mdd.toFixed(2)+'%</td><td>'+a.sharpe.toFixed(2)+'</td><td style="font-size:11px;">'+a.switches+'/'+a.fee.toFixed(2)+'%</td>'+
    '<td class="pos">'+b.total.toFixed(2)+'%</td><td class="neg">'+b.mdd.toFixed(2)+'%</td><td>'+b.sharpe.toFixed(2)+'</td><td style="font-size:11px;">'+b.switches+'/'+b.fee.toFixed(2)+'%</td>'+
    '<td class="neg" style="font-weight:700;">'+(diffTotal>0?'+':'')+diffTotal.toFixed(2)+'%</td>'+
    '<td class="'+(diffMdd>0?'neg':'pos')+'" style="font-weight:700;">'+(diffMdd>0?'+':'')+diffMdd.toFixed(2)+'%</td>'+
    '<td class="pos" style="font-weight:700;">+'+feeSaved.toFixed(2)+'%</td>';
  compareBody.appendChild(tr);
});

// 图表
Chart.defaults.font.family="'PingFang SC','Microsoft YaHei',sans-serif";
Chart.defaults.font.size=11;

function makeChart(canvasId, cd, allIds, showLegend){
  const ctx=document.getElementById(canvasId); if(!ctx) return;
  const datasets=[{label:'轮动策略V11',data:cd.strat,borderColor:'#e53935',backgroundColor:'rgba(229,57,53,0.08)',borderWidth:2.5,pointRadius:0,fill:true,tension:0.1}];
  allIds.forEach(i=>{ datasets.push({label:LABELS[i],data:cd['bh'+i],borderColor:COLORS[i],borderWidth:1.2,pointRadius:0,fill:false,tension:0.1}); });
  return new Chart(ctx,{type:'line',data:{labels:cd.dates,datasets:datasets},
    options:{responsive:true,maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{legend:{display:showLegend,position:'top',labels:{boxWidth:12,font:{size:11}}},
        tooltip:{callbacks:{label:function(c){return c.dataset.label+': '+c.parsed.y.toFixed(4);}}}},
      scales:{x:{ticks:{maxTicksLimit:8,maxRotation:0},grid:{display:false}},
        y:{ticks:{callback:function(v){return v.toFixed(2);}},grid:{color:'#f0f0f0'}}}}});
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

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/MA20轮动策略V11回测报告.html','w',encoding='utf-8') as f:
    f.write(html)
print("HTML报告已生成: MA20轮动策略V11回测报告.html")
