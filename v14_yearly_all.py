# -*- coding: utf-8 -*-
"""V14(5%/4%)近1/3/5/10/20年逐年统计：收益、夏普率、最大回撤、持仓占比
时段标的池：
  近20年: 上证50、纳斯达克100、沪深300、中证1000 + 国债
  近10年: 上证50、创业板50、纳斯达克100、沪深300、中证500、中证1000、标普500 + 国债
  近5/3/1年: 上述7股 + 科创50 + 国债
"""
import pandas as pd
import numpy as np
import json, os
from functools import reduce

FEE = 0.0002
DD_TRIGGER = 0.05
DD_RELEASE = 0.04

def find_file(name):
    for p in [f'C:/Users/wbl/Desktop/同花顺历史数据/{name}.xlsx',
              f'C:/Users/wbl/Desktop/{name}.xlsx']:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"未找到 {name}.xlsx")

files = {
    1: find_file('上证50'), 2: find_file('创业板50'), 3: find_file('纳斯达克100'),
    4: find_file('沪深300'), 5: find_file('中证500'), 6: find_file('中证1000'),
    7: find_file('标普500'), 8: find_file('科创50'), 9: find_file('国债'),
}
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}
all_names = {0:'空仓', 1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}

dfs = {}
for i, path in files.items():
    d = pd.read_csv(path, sep='\t', encoding='gbk')
    d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
    d = d[['date','开盘','收盘']].rename(columns={'开盘':f'open_{i}','收盘':f'close_{i}'})
    for c in [f'open_{i}',f'close_{i}']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    dfs[i] = d.dropna()

last_date = dfs[9]['date'].max()
print(f"数据最新日期: {last_date.date()}")

STOCK_20Y = [1, 3, 4, 6]
STOCK_10Y = [1, 2, 3, 4, 5, 6, 7]
STOCK_RECENT = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9

periods_config = {
    '近20年': (STOCK_20Y, last_date - pd.DateOffset(years=20)),
    '近10年': (STOCK_10Y, last_date - pd.DateOffset(years=10)),
    '近5年':  (STOCK_RECENT, last_date - pd.DateOffset(years=5)),
    '近3年':  (STOCK_RECENT, last_date - pd.DateOffset(years=3)),
    '近1年':  (STOCK_RECENT, last_date - pd.DateOffset(years=1)),
}

def build_period_data(stock_ids, bond_id, start_date, end_date):
    all_ids = stock_ids + [bond_id]
    df = reduce(lambda a,b: pd.merge(a,b,on='date',how='inner'), [dfs[i] for i in all_ids])
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)

    for i in stock_ids:
        df[f'ma20_{i}'] = df[f'close_{i}'].rolling(20).mean()
        df[f'bf_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}'] - 1
        df[f'ratio_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}']
    df = df.dropna(subset=[f'ma20_{i}' for i in stock_ids]).reset_index(drop=True)

    def get_signal(row):
        ratios = [row[f'ratio_{i}'] for i in stock_ids]
        if all(r < 1 for r in ratios):
            return bond_id
        bfs = {i: row[f'bf_{i}'] for i in stock_ids}
        return max(bfs, key=bfs.get)
    df['raw_signal'] = df.apply(get_signal, axis=1)

    for i in all_ids:
        df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
    last_idx = df.index[-1]
    for i in all_ids:
        df[f'ret_{i}'] = np.nan
        mask = df[f'open_{i}_next'].notna()
        df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
        df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

    df['raw_position'] = df['raw_signal'].shift(1)
    df.loc[df.index[0], 'raw_position'] = 0
    df['raw_prev_position'] = df['raw_position'].shift(1)
    df.loc[df.index[0], 'raw_prev_position'] = df.loc[df.index[0], 'raw_position']

    def get_raw_strat_ret(row):
        pos = int(row['raw_position'])
        gross = row[f'ret_{pos}'] if pos in all_ids else 0.0
        prev = int(row['raw_prev_position'])
        cost = 0.0
        if prev != pos:
            if prev in all_ids: cost += FEE
            if pos in all_ids: cost += FEE
        return (1 + gross) * (1 - cost) - 1
    df['raw_strat_ret'] = df.apply(get_raw_strat_ret, axis=1)
    df['raw_strat_nav'] = (1 + df['raw_strat_ret']).cumprod()
    df['raw_cummax'] = df['raw_strat_nav'].cummax()
    df['raw_dd'] = df['raw_strat_nav'] / df['raw_cummax'] - 1
    return df, all_ids

def apply_circuit_breaker(df, all_ids, bond_id):
    raw_pos = df['raw_position'].values
    raw_dd = df['raw_dd'].values
    n = len(df)
    in_cb = False
    final_position = []
    for i in range(n):
        sig = int(raw_pos[i])
        dd = raw_dd[i]
        if not in_cb:
            if dd < -DD_TRIGGER and sig != bond_id:
                in_cb = True
                final_position.append(bond_id)
            else:
                final_position.append(sig)
        else:
            if dd > -DD_RELEASE:
                in_cb = False
                final_position.append(sig)
            else:
                final_position.append(bond_id)
    return np.array(final_position)

def compute_v14_ret(df, all_ids, bond_id, pos):
    n = len(df)
    prev_pos = np.concatenate([[pos[0]], pos[:-1]])
    rets = np.zeros(n)
    for i in range(n):
        p = int(pos[i])
        gross = df[f'ret_{p}'].iloc[i] if p in all_ids else 0.0
        cost = 0.0
        if int(prev_pos[i]) != p:
            if int(prev_pos[i]) in all_ids: cost += FEE
            if p in all_ids: cost += FEE
        rets[i] = (1 + gross) * (1 - cost) - 1
    return rets

# ===== 跑各时段 =====
all_period_results = {}
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    stocks, sd = periods_config[pname]
    df, all_ids = build_period_data(stocks, BOND, sd, last_date)
    pos_v14 = apply_circuit_breaker(df, all_ids, BOND)
    v14_rets = compute_v14_ret(df, all_ids, BOND, pos_v14)
    df['v14_pos'] = pos_v14
    df['v14_ret'] = v14_rets
    df['year'] = df['date'].dt.year

    stock_ids = stocks
    years = sorted(df['year'].unique())
    yearly_list = []
    for y in years:
        sub = df[df['year'] == y].copy()
        ny = len(sub)
        year_ret = (1 + sub['v14_ret']).prod() - 1
        year_nav = (1 + sub['v14_ret']).cumprod()
        year_mdd = ((year_nav - year_nav.cummax()) / year_nav.cummax()).min()
        std = sub['v14_ret'].std()
        sharpe = np.sqrt(252) * sub['v14_ret'].mean() / std if std > 0 else 0
        ann_vol = std * np.sqrt(252)
        # 持仓占比
        holding = {}
        for a in stock_ids + [BOND, 0]:
            cnt = int((sub['v14_pos'] == a).sum())
            if cnt > 0:
                holding[all_names[a]] = {'days': cnt, 'pct': round(cnt/ny*100, 2)}
        yearly_list.append({
            'year': int(y),
            'n_days': int(ny),
            'start': sub['date'].iloc[0].strftime('%Y-%m-%d'),
            'end': sub['date'].iloc[-1].strftime('%Y-%m-%d'),
            'ret': round(float(year_ret)*100, 2),
            'sharpe': round(float(sharpe), 2),
            'mdd': round(float(year_mdd)*100, 2),
            'ann_vol': round(float(ann_vol)*100, 2),
            'holding': holding,
            'switches': int(np.sum(np.diff(sub['v14_pos'].values) != 0)),
        })

    # 整体统计
    total_ret = (1 + df['v14_ret']).prod() - 1
    nav_all = (1 + df['v14_ret']).cumprod()
    mdd_all = ((nav_all - nav_all.cummax()) / nav_all.cummax()).min()
    std_all = df['v14_ret'].std()
    sharpe_all = np.sqrt(252) * df['v14_ret'].mean() / std_all if std_all > 0 else 0
    ann_all = (1 + total_ret) ** (252/len(df)) - 1
    overall_holding = {}
    for a in stock_ids + [BOND, 0]:
        cnt = int((df['v14_pos'] == a).sum())
        if cnt > 0:
            overall_holding[all_names[a]] = {'days': cnt, 'pct': round(cnt/len(df)*100, 2)}

    all_period_results[pname] = {
        'start': df['date'].iloc[0].strftime('%Y-%m-%d'),
        'end': df['date'].iloc[-1].strftime('%Y-%m-%d'),
        'n_days': int(len(df)),
        'stock_names': [names[i] for i in stock_ids],
        'yearly': yearly_list,
        'overall': {
            'total_ret': round(float(total_ret)*100, 2),
            'ann_ret': round(float(ann_all)*100, 2),
            'mdd': round(float(mdd_all)*100, 2),
            'sharpe': round(float(sharpe_all), 2),
            'ann_vol': round(float(std_all * np.sqrt(252))*100, 2),
            'holding': overall_holding,
        },
    }
    print(f"{pname}: {df['date'].iloc[0].date()}~{df['date'].iloc[-1].date()}, {len(df)}天, {len(years)}年")

# 导出JSON
with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_yearly_all.json', 'w', encoding='utf-8') as f:
    json.dump(all_period_results, f, ensure_ascii=False, indent=2)
print("\n数据已保存到 v14_yearly_all.json")

# ===== 生成HTML =====
def gen_holding_cell(holding, stock_names):
    """生成单个持仓占比单元格"""
    colors = {
        '上证50': '#e74c3c', '创业板50': '#f39c12', '纳斯达克100': '#3498db',
        '沪深300': '#2ecc71', '中证500': '#9b59b6', '中证1000': '#1abc9c',
        '标普500': '#e67e22', '科创50': '#d35400', '国债': '#95a5a6', '空仓': '#bdc3c7',
    }
    parts = []
    for name in stock_names + ['国债', '空仓']:
        if name in holding:
            pct = holding[name]['pct']
            if pct > 0:
                color = colors.get(name, '#888')
                label = name if pct >= 5 else ''
                parts.append(f'<span class="hb" style="width:{pct}%;background:{color}"><span class="hb-l">{label}</span></span>')
    return f'<div class="hbar">{"".join(parts)}</div>'

# 控制流修正
html_parts = []
html_parts.append('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>V14策略(5%/4%) 近1/3/5/10/20年逐年统计</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Microsoft YaHei','Segoe UI',sans-serif; background:#f5f6fa; color:#333; padding:20px; }
h1 { text-align:center; font-size:22px; margin-bottom:5px; }
.sub { text-align:center; font-size:13px; color:#666; margin-bottom:20px; }
.period-card { background:#fff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.08); margin-bottom:24px; overflow:hidden; }
.period-header { background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; padding:14px 20px; display:flex; justify-content:space-between; align-items:center; }
.period-header h2 { font-size:18px; }
.period-header .info { font-size:13px; opacity:0.9; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th { background:#f8f9fa; padding:10px 8px; text-align:center; font-weight:600; border-bottom:2px solid #e0e0e0; white-space:nowrap; }
td { padding:8px; text-align:center; border-bottom:1px solid #eee; }
tr:hover td { background:#f8f9ff; }
.pos { color:#e74c3c; font-weight:600; }
.neg { color:#27ae60; font-weight:600; }
.mdd-val { color:#e74c3c; }
.sharpe-pos { color:#e74c3c; font-weight:600; }
.sharpe-neg { color:#27ae60; }
.hbar { display:flex; width:180px; height:20px; border-radius:4px; overflow:hidden; margin:0 auto; }
.hb { display:inline-flex; align-items:center; justify-content:center; height:100%; font-size:10px; color:#fff; white-space:nowrap; overflow:hidden; }
.hb-l { font-size:9px; }
.overall-row { background:#fffde7 !important; font-weight:600; }
.overall-row td { border-top:2px solid #f0e68c; border-bottom:2px solid #f0e68c; }
.legend { display:flex; gap:12px; justify-content:center; flex-wrap:wrap; margin-bottom:16px; }
.legend-item { display:flex; align-items:center; gap:4px; font-size:12px; }
.legend-color { width:14px; height:14px; border-radius:3px; }
.summary-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:24px; }
.summary-card { background:#fff; border-radius:8px; padding:14px; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.06); }
.summary-card h3 { font-size:14px; color:#666; margin-bottom:8px; }
.summary-card .val { font-size:20px; font-weight:700; }
.summary-card .sub-val { font-size:12px; color:#888; margin-top:4px; }
</style>
</head>
<body>
<h1>V14策略 (5%/4%阈值) 逐年统计</h1>
<div class="sub">MA20轮动 · 5%回撤触发熔断/4%解除 · T日收盘信号→T+1开盘执行 · 手续费0.02%</div>
''')

# 图例
html_parts.append('<div class="legend">')
legend_colors = {
    '上证50': '#e74c3c', '创业板50': '#f39c12', '纳斯达克100': '#3498db',
    '沪深300': '#2ecc71', '中证500': '#9b59b6', '中证1000': '#1abc9c',
    '标普500': '#e67e22', '科创50': '#d35400', '国债': '#95a5a6', '空仓': '#bdc3c7',
}
for name, color in legend_colors.items():
    html_parts.append(f'<div class="legend-item"><div class="legend-color" style="background:{color}"></div>{name}</div>')
html_parts.append('</div>')

# 各时段汇总卡片
html_parts.append('<div class="summary-grid">')
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = all_period_results[pname]
    o = r['overall']
    ret_class = 'pos' if o['total_ret'] >= 0 else 'neg'
    sharpe_class = 'sharpe-pos' if o['sharpe'] >= 0 else 'sharpe-neg'
    html_parts.append(f'''<div class="summary-card">
    <h3>{pname}</h3>
    <div class="val {ret_class}">{o["total_ret"]:+.2f}%</div>
    <div class="sub-val">年化 {o["ann_ret"]:+.2f}% · 夏普 {o["sharpe"]:.2f}</div>
    <div class="sub-val">回撤 {o["mdd"]:.2f}% · 波动 {o["ann_vol"]:.2f}%</div>
    <div class="sub-val">{r["n_days"]}天 · {len(r["stock_names"])}股+国债</div>
    </div>''')
html_parts.append('</div>')

# 各时段表格
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = all_period_results[pname]
    stock_names = r['stock_names']
    html_parts.append(f'''<div class="period-card">
    <div class="period-header">
        <h2>{pname}</h2>
        <div class="info">{r["start"]} ~ {r["end"]} · {r["n_days"]}天 · 标的: {", ".join(stock_names)} + 国债</div>
    </div>
    <table>
    <thead><tr>
        <th>年份</th><th>交易日</th><th>年度收益</th><th>夏普率</th><th>最大回撤</th><th>年化波动</th><th>切换次数</th><th>持仓占比</th>
    </tr></thead><tbody>''')

    for yd in r['yearly']:
        ret_cls = 'pos' if yd['ret'] >= 0 else 'neg'
        sharpe_cls = 'sharpe-pos' if yd['sharpe'] >= 0 else 'sharpe-neg'
        holding_html = gen_holding_cell(yd['holding'], stock_names)
        html_parts.append(f'''<tr>
            <td>{yd["year"]}</td>
            <td>{yd["n_days"]}</td>
            <td class="{ret_cls}">{yd["ret"]:+.2f}%</td>
            <td class="{sharpe_cls}">{yd["sharpe"]:.2f}</td>
            <td class="mdd-val">{yd["mdd"]:.2f}%</td>
            <td>{yd["ann_vol"]:.2f}%</td>
            <td>{yd["switches"]}</td>
            <td>{holding_html}</td>
        </tr>''')

    # 整体行
    o = r['overall']
    ret_cls = 'pos' if o['total_ret'] >= 0 else 'neg'
    sharpe_cls = 'sharpe-pos' if o['sharpe'] >= 0 else 'sharpe-neg'
    holding_html = gen_holding_cell(o['holding'], stock_names)
    html_parts.append(f'''<tr class="overall-row">
        <td>整体</td>
        <td>{r["n_days"]}</td>
        <td class="{ret_cls}">{o["total_ret"]:+.2f}%</td>
        <td class="{sharpe_cls}">{o["sharpe"]:.2f}</td>
        <td class="mdd-val">{o["mdd"]:.2f}%</td>
        <td>{o["ann_vol"]:.2f}%</td>
        <td>-</td>
        <td>{holding_html}</td>
    </tr>''')

    html_parts.append('</tbody></table></div>')

html_parts.append('''
<div style="text-align:center;font-size:12px;color:#999;margin-top:20px;">
收益口径: open-to-open · 夏普率: 年化(√252) · 最大回撤: 年内峰值回撤 · 持仓占比: 按交易日天数统计
</div>
</body></html>''')

html = '\n'.join(html_parts)

out_path = 'C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_yearly_all.html'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nHTML报告已生成: {out_path}")
