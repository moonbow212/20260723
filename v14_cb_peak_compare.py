# -*- coding: utf-8 -*-
"""V14熔断基准变体对比：历史最高点 vs 近1年最高点 vs 近3年最高点

策略：MA20轮动 + 5%/4%熔断 + 动态避险v2(金>20日MA→黄金ETF, 金<=20日MA→国债)
费率：万0.5 | 收益口径：open-to-open
新标的池(9只)：创业板50, 纳斯达克100, 中证500, 中证1000, 标普500, 科创50, 中证A500, 北证50, 中证A50

变体说明：
- 原版：回撤 = 当前净值 / 历史最高净值 - 1
- 近1年：回撤 = 当前净值 / 近252个交易日最高净值 - 1
- 近3年：回撤 = 当前净值 / 近756个交易日最高净值 - 1
"""
import pandas as pd
import numpy as np
import json, os

DD_TRIGGER = 0.05
DD_RELEASE = 0.04
FEE = 0.00005
MA_PERIOD = 20
GOLD_START = pd.Timestamp('2013-07-29')

STOCK_ALL = [2, 3, 5, 6, 7, 8, 11, 12, 13]
BOND = 9
GOLD = 10
names = {
    2:'创业板50', 3:'纳斯达克100', 5:'中证500', 6:'中证1000',
    7:'标普500', 8:'科创50', 9:'国债', 10:'黄金ETF',
    11:'中证A500', 12:'北证50', 13:'中证A50'
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== 1. 读取数据 =====
print("读取数据...")
dfs = {}
for i in STOCK_ALL + [BOND, GOLD]:
    name = names[i]
    csv_path = os.path.join(BASE_DIR, 'data', f'{i}_{name}.csv')
    if not os.path.exists(csv_path):
        print(f"  跳过 {name}（无数据文件）")
        continue
    d = pd.read_csv(csv_path, parse_dates=['date'])
    d = d[['date', 'open', 'close']].rename(columns={'open': f'open_{i}', 'close': f'close_{i}'})
    d = d.sort_values('date').reset_index(drop=True)
    if i != BOND:
        d[f'ma{MA_PERIOD}_{i}'] = d[f'close_{i}'].rolling(MA_PERIOD).mean()
        d[f'bf{MA_PERIOD}_{i}'] = d[f'close_{i}'] / d[f'ma{MA_PERIOD}_{i}'] - 1
        d[f'ratio{MA_PERIOD}_{i}'] = d[f'close_{i}'] / d[f'ma{MA_PERIOD}_{i}']
    dfs[i] = d
    print(f"  {names[i]}: {d['date'].iloc[0].date()} ~ {d['date'].iloc[-1].date()}, {len(d)}条")

last_date = dfs[BOND]['date'].max()

# ===== 2. 构建合并数据 =====
start_date = last_date - pd.DateOffset(years=20)
df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
df = df.sort_values('date').reset_index(drop=True)
df = df[(df['date'] >= start_date) & (df['date'] <= last_date)].reset_index(drop=True)

for i in STOCK_ALL:
    if i not in dfs:
        continue
    ma_col = f'ma{MA_PERIOD}_{i}'
    bf_col = f'bf{MA_PERIOD}_{i}'
    ratio_col = f'ratio{MA_PERIOD}_{i}'
    cols = ['date', f'open_{i}', f'close_{i}', ma_col, bf_col, ratio_col]
    df = pd.merge(df, dfs[i][cols], on='date', how='left')

# 合并黄金ETF数据
gold_cols = ['date', f'open_{GOLD}', f'close_{GOLD}']
df = pd.merge(df, dfs[GOLD][gold_cols], on='date', how='left')

# 动态避险v2
df['gold_ma20'] = df[f'close_{GOLD}'].rolling(20).mean()
df['safe_haven'] = BOND
mask_gold = df['date'] >= GOLD_START
mask_ma = df['gold_ma20'].notna()
mask_above = df[f'close_{GOLD}'] > df['gold_ma20']
df.loc[mask_gold & mask_ma & mask_above, 'safe_haven'] = GOLD

all_ids = STOCK_ALL + [BOND, GOLD]
all_ids_set = set(all_ids)

# 计算收益
for i in all_ids:
    df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
last_idx = df.index[-1]
for i in all_ids:
    df[f'ret_{i}'] = np.nan
    mask = df[f'open_{i}_next'].notna() & df[f'open_{i}'].notna()
    df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
    if pd.notna(df.loc[last_idx, f'open_{i}']) and pd.notna(df.loc[last_idx, f'close_{i}']):
        df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

# ===== 3. V8基线（无熔断） =====
bf_prefix = f'bf{MA_PERIOD}'
ratio_prefix = f'ratio{MA_PERIOD}'

def get_signal(row):
    available = {}
    for i in STOCK_ALL:
        if i not in dfs:
            continue
        bf_val = row[f'{bf_prefix}_{i}']
        ratio_val = row[f'{ratio_prefix}_{i}']
        if pd.notna(bf_val) and pd.notna(ratio_val):
            available[i] = (bf_val, ratio_val)
    safe = int(row['safe_haven'])
    if not available:
        return safe
    if all(v[1] < 1 for v in available.values()):
        return safe
    return max(available, key=lambda k: available[k][0])

df['raw_signal'] = df.apply(get_signal, axis=1)
df['raw_position'] = df['raw_signal'].shift(1)
df.loc[df.index[0], 'raw_position'] = 0
df['raw_prev_position'] = df['raw_position'].shift(1)
df.loc[df.index[0], 'raw_prev_position'] = df.loc[df.index[0], 'raw_position']

def get_raw_strat_ret(row):
    pos = int(row['raw_position'])
    if pos == 0:
        gross = 0.0
    else:
        ret_val = row[f'ret_{pos}']
        gross = ret_val if pd.notna(ret_val) else 0.0
    prev = int(row['raw_prev_position'])
    cost = 0.0
    if prev != pos:
        if prev in all_ids_set: cost += FEE
        if pos in all_ids_set: cost += FEE
    return (1 + gross) * (1 - cost) - 1

df['raw_strat_ret'] = df.apply(get_raw_strat_ret, axis=1)
df['raw_strat_nav'] = (1 + df['raw_strat_ret']).cumprod()

# ===== 4. 三种回撤计算 =====
# 原版：历史最高点
df['dd_alltime'] = df['raw_strat_nav'] / df['raw_strat_nav'].cummax() - 1

# 近1年最高点（252个交易日）
df['peak_1y'] = df['raw_strat_nav'].rolling(252, min_periods=1).max()
df['dd_1y'] = df['raw_strat_nav'] / df['peak_1y'] - 1

# 近3年最高点（756个交易日）
df['peak_3y'] = df['raw_strat_nav'].rolling(756, min_periods=1).max()
df['dd_3y'] = df['raw_strat_nav'] / df['peak_3y'] - 1

# ===== 5. 应用熔断 =====
def apply_circuit_breaker(df, dd_col):
    raw_pos = df['raw_position'].values
    dd = df[dd_col].values
    safe_havens = df['safe_haven'].values
    n = len(df)
    in_cb = False
    final_position = []
    cb_count = 0
    for i in range(n):
        sig = int(raw_pos[i])
        d = dd[i]
        safe = int(safe_havens[i])
        if not in_cb:
            if d < -DD_TRIGGER and sig != safe:
                in_cb = True
                final_position.append(safe)
                cb_count += 1
            else:
                final_position.append(sig)
        else:
            if d > -DD_RELEASE:
                in_cb = False
                final_position.append(sig)
            else:
                final_position.append(safe)
    return np.array(final_position), cb_count

def compute_v14_ret(df, pos):
    n = len(df)
    prev_pos = np.concatenate([[pos[0]], pos[:-1]])
    rets = np.zeros(n)
    for i in range(n):
        p = int(pos[i])
        if p == 0:
            gross = 0.0
        else:
            ret_val = df[f'ret_{p}'].iloc[i]
            gross = ret_val if pd.notna(ret_val) else 0.0
        cost = 0.0
        if int(prev_pos[i]) != p:
            if int(prev_pos[i]) in all_ids_set: cost += FEE
            if p in all_ids_set: cost += FEE
        rets[i] = (1 + gross) * (1 - cost) - 1
    return rets

# ===== 6. 跑三个变体 =====
variants = [
    ('dd_alltime', '历史最高点(原版)'),
    ('dd_1y', '近1年最高点'),
    ('dd_3y', '近3年最高点'),
]

results = {}
for dd_col, label in variants:
    print(f"\n=== {label} ===")
    pos, cb_count = apply_circuit_breaker(df, dd_col)
    rets = compute_v14_ret(df, pos)
    df[f'ret_{dd_col}'] = rets
    df[f'pos_{dd_col}'] = pos
    df[f'nav_{dd_col}'] = (1 + rets).cumprod()

    # 逐年收益
    df['year'] = df['date'].dt.year
    years = sorted(df['year'].unique())
    yearly_list = []
    for y in years:
        sub = df[df['year'] == y]
        year_ret = (1 + sub[f'ret_{dd_col}']).prod() - 1
        year_nav = (1 + sub[f'ret_{dd_col}']).cumprod()
        year_mdd = ((year_nav - year_nav.cummax()) / year_nav.cummax()).min()
        yearly_list.append({
            'year': int(y),
            'n_days': int(len(sub)),
            'ret': round(float(year_ret) * 100, 2),
            'mdd': round(float(year_mdd) * 100, 2),
        })

    total_ret = (1 + rets).prod() - 1
    nav_all = np.cumprod(1 + rets)
    mdd_all = ((nav_all - np.maximum.accumulate(nav_all)) / np.maximum.accumulate(nav_all)).min()
    std_all = np.std(rets)
    sharpe_all = np.sqrt(252) * np.mean(rets) / std_all if std_all > 0 else 0
    ann_all = (1 + total_ret) ** (252 / len(df)) - 1
    switches = int(np.sum(np.diff(pos) != 0))

    results[label] = {
        'dd_col': dd_col,
        'yearly': yearly_list,
        'overall': {
            'total_ret': round(float(total_ret) * 100, 2),
            'ann_ret': round(float(ann_all) * 100, 2),
            'mdd': round(float(mdd_all) * 100, 2),
            'sharpe': round(float(sharpe_all), 2),
            'ann_vol': round(float(std_all * np.sqrt(252)) * 100, 2),
            'switches': switches,
            'cb_count': cb_count,
        },
    }
    o = results[label]['overall']
    print(f"  总收益={o['total_ret']:+.2f}% 年化={o['ann_ret']:+.2f}% 夏普={o['sharpe']:.2f} 回撤={o['mdd']:.2f}% 熔断{cb_count}次 切换{switches}次")
    for yl in yearly_list:
        print(f"  {yl['year']}: {yl['ret']:+.2f}% (回撤{yl['mdd']:.2f}%, {yl['n_days']}天)")

with open(os.path.join(BASE_DIR, 'v14_cb_peak_compare.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\n数据已保存到 v14_cb_peak_compare.json")

# ===== 7. 生成HTML =====
all_years = sorted(set(y['year'] for v in results.values() for y in v['yearly']))
labels = [l for _, l in variants]
dd_cols = [c for c, _ in variants]
colors_dd = {'历史最高点(原版)': '#3498db', '近1年最高点': '#e74c3c', '近3年最高点': '#2ecc71'}

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14熔断基准对比：历史最高点 vs 近1年 vs 近3年</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Microsoft YaHei','Segoe UI',sans-serif; background:#f5f6fa; color:#333; padding:20px; }}
h1 {{ text-align:center; font-size:22px; margin-bottom:5px; }}
.sub {{ text-align:center; font-size:13px; color:#666; margin-bottom:16px; }}
.note {{ background:#fff8e1; border:1px solid #ffe082; border-radius:6px; padding:12px 16px; margin-bottom:20px; font-size:13px; color:#5d4037; line-height:1.8; }}
.summary-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:24px; }}
.summary-card {{ background:#fff; border-radius:10px; padding:16px; box-shadow:0 2px 8px rgba(0,0,0,0.08); border-top:4px solid {colors_dd.get(labels[0],'#3498db')}; }}
.summary-card:nth-child(2) {{ border-top-color: {colors_dd.get(labels[1],'#e74c3c')}; }}
.summary-card:nth-child(3) {{ border-top-color: {colors_dd.get(labels[2],'#2ecc71')}; }}
.summary-card h3 {{ font-size:15px; margin-bottom:10px; }}
.summary-card .metric {{ display:flex; justify-content:space-between; margin:4px 0; font-size:13px; }}
.summary-card .metric .label {{ color:#888; }}
.summary-card .metric .val {{ font-weight:700; }}
.pos {{ color:#e74c3c; }}
.neg {{ color:#27ae60; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.06); }}
th {{ background:#2c3e50; color:#fff; padding:10px 6px; text-align:center; font-weight:500; white-space:nowrap; }}
td {{ padding:7px 6px; text-align:center; border-bottom:1px solid #eee; }}
tr:hover td {{ background:#f8fffe; }}
.col-0 {{ background:#e3f2fd; }}
.col-1 {{ background:#fff3e0; }}
.col-2 {{ background:#e8f5e9; }}
.overall-row {{ background:#fffde7 !important; font-weight:700; }}
.overall-row td {{ border-top:2px solid #f0e68c; border-bottom:2px solid #f0e68c; }}
.diff-pos {{ color:#e74c3c; font-weight:600; }}
.diff-neg {{ color:#27ae60; font-weight:600; }}
</style>
</head>
<body>
<h1>V14熔断基准对比：历史最高点 vs 近1年最高点 vs 近3年最高点</h1>
<div class="sub">新标的池(9只) · MA20轮动 · 费率万0.5 · 5%/4%熔断 · 动态避险v2 · open-to-open · 近20年</div>
<div class="note">
<b>变体说明：</b><br>
&nbsp;&nbsp;• <b>历史最高点(原版)</b>：回撤 = 当前净值 / 历史累计最高净值 - 1（一旦创新高，旧峰值永远有效）<br>
&nbsp;&nbsp;• <b>近1年最高点</b>：回撤 = 当前净值 / 近252个交易日最高净值 - 1（峰值1年后失效，回撤"重置"）<br>
&nbsp;&nbsp;• <b>近3年最高点</b>：回撤 = 当前净值 / 近756个交易日最高净值 - 1（峰值3年后失效，回撤"重置"）<br>
<span style="color:#666">逻辑：峰值窗口越短，回撤更容易"重置"为零，熔断更难触发；窗口越长，越接近原版</span>
</div>
'''

# 汇总卡片
html += '<div class="summary-grid">'
for idx, label in enumerate(labels):
    o = results[label]['overall']
    ret_cls = 'pos' if o['total_ret'] >= 0 else 'neg'
    html += f'''<div class="summary-card" style="border-top-color:{colors_dd.get(label,'#3498db')}">
        <h3 style="color:{colors_dd.get(label,'#3498db')}">{label}</h3>
        <div class="metric"><span class="label">总收益</span><span class="val {ret_cls}">{o["total_ret"]:+.2f}%</span></div>
        <div class="metric"><span class="label">年化收益</span><span class="val {ret_cls}">{o["ann_ret"]:+.2f}%</span></div>
        <div class="metric"><span class="label">最大回撤</span><span class="val neg">{o["mdd"]:.2f}%</span></div>
        <div class="metric"><span class="label">夏普率</span><span class="val">{o["sharpe"]:.2f}</span></div>
        <div class="metric"><span class="label">年化波动</span><span class="val">{o["ann_vol"]:.2f}%</span></div>
        <div class="metric"><span class="label">熔断次数</span><span class="val">{o["cb_count"]}</span></div>
        <div class="metric"><span class="label">切换次数</span><span class="val">{o["switches"]}</span></div>
    </div>'''
html += '</div>'

# 逐年对比表
html += '''<table>
<thead><tr>
    <th rowspan="2">年份</th>
    <th rowspan="2">交易日</th>
'''
for idx, label in enumerate(labels):
    col_cls = f'col-{idx}'
    short = label.replace('(原版)', '')
    html += f'<th colspan="2" class="{col_cls}" style="border-right:1px solid #ddd;">{short}</th>'
html += '<th rowspan="2">1年-原版</th><th rowspan="2">3年-原版</th></tr><tr>'
for idx, label in enumerate(labels):
    col_cls = f'col-{idx}'
    html += f'<th class="{col_cls}">收益</th><th class="{col_cls}">回撤</th>'
html += '</tr></thead><tbody>'

base_ret = {y['year']: y['ret'] for y in results['历史最高点(原版)']['yearly']}

for y in all_years:
    html += f'<tr><td>{y}</td>'
    # 交易日
    n_days = None
    for label in labels:
        yl = next((yy for yy in results[label]['yearly'] if yy['year'] == y), None)
        if yl:
            n_days = yl['n_days']
            break
    html += f'<td>{n_days or "-"}</td>'

    for idx, label in enumerate(labels):
        col_cls = f'col-{idx}'
        yl = next((yy for yy in results[label]['yearly'] if yy['year'] == y), None)
        if yl:
            ret_cls = 'pos' if yl['ret'] >= 0 else 'neg'
            html += f'<td class="{col_cls} {ret_cls}">{yl["ret"]:+.2f}%</td>'
            html += f'<td class="{col_cls}">{yl["mdd"]:.2f}%</td>'
        else:
            html += f'<td class="{col_cls}">-</td><td class="{col_cls}">-</td>'

    # 差异
    base_r = base_ret.get(y)
    r_1y = next((yy['ret'] for yy in results['近1年最高点']['yearly'] if yy['year'] == y), None)
    r_3y = next((yy['ret'] for yy in results['近3年最高点']['yearly'] if yy['year'] == y), None)

    if base_r is not None and r_1y is not None:
        diff = r_1y - base_r
        cls = 'diff-pos' if diff >= 0 else 'diff-neg'
        html += f'<td class="{cls}">{diff:+.2f}%</td>'
    else:
        html += '<td>-</td>'

    if base_r is not None and r_3y is not None:
        diff = r_3y - base_r
        cls = 'diff-pos' if diff >= 0 else 'diff-neg'
        html += f'<td class="{cls}">{diff:+.2f}%</td>'
    else:
        html += '<td>-</td>'

    html += '</tr>'

# 整体行
html += '<tr class="overall-row"><td>整体</td><td>-</td>'
for idx, label in enumerate(labels):
    col_cls = f'col-{idx}'
    o = results[label]['overall']
    ret_cls = 'pos' if o['total_ret'] >= 0 else 'neg'
    html += f'<td class="{col_cls} {ret_cls}">{o["total_ret"]:+.2f}%</td>'
    html += f'<td class="{col_cls}">{o["mdd"]:.2f}%</td>'

diff_1y = results['近1年最高点']['overall']['total_ret'] - results['历史最高点(原版)']['overall']['total_ret']
diff_3y = results['近3年最高点']['overall']['total_ret'] - results['历史最高点(原版)']['overall']['total_ret']
cls_1y = 'diff-pos' if diff_1y >= 0 else 'diff-neg'
cls_3y = 'diff-pos' if diff_3y >= 0 else 'diff-neg'
html += f'<td class="{cls_1y}">{diff_1y:+.2f}%</td>'
html += f'<td class="{cls_3y}">{diff_3y:+.2f}%</td>'
html += '</tr>'

html += '</tbody></table>'

html += '''
<div style="text-align:center;font-size:12px;color:#999;margin-top:16px;">
回撤基准：原版=历史累计最高净值 · 近1年=252交易日滚动最高 · 近3年=756交易日滚动最高<br>
峰值窗口越短 → 回撤更容易"重置"为零 → 熔断更难触发 → 策略更激进
</div>
</body></html>'''

out_path = os.path.join(BASE_DIR, 'v14_cb_peak_compare.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nHTML报告已生成: {out_path}")
