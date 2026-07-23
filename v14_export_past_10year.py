# -*- coding: utf-8 -*-
"""导出近10年每天持仓与操作明细
策略定义：决策日期=T日，决策bf=(T-1收盘/T-1的MA20)-1，T日开盘执行
"""
import pandas as pd
import numpy as np
import os

FEE = 0.0002
DD_TRIGGER = 0.05
DD_RELEASE = 0.04

STOCK_ALL = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}
all_names = {0:'空仓', 1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== 1. 读取数据 =====
dfs = {}
for i in STOCK_ALL + [BOND]:
    name = names[i]
    csv_path = os.path.join(BASE_DIR, 'data', f'{i}_{name}.csv')
    d = pd.read_csv(csv_path, parse_dates=['date'])
    d = d[['date', 'open', 'close']].rename(columns={'open': f'open_{i}', 'close': f'close_{i}'})
    d = d.sort_values('date').reset_index(drop=True)
    if i != BOND:
        d[f'ma20_{i}'] = d[f'close_{i}'].rolling(20).mean()
        d[f'bf_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}'] - 1
        d[f'ratio_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}']
    dfs[i] = d

last_date = dfs[BOND]['date'].max()

# ===== 2. 构建近10年合并数据 =====
start_date = last_date - pd.DateOffset(years=10)
df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
df = df.sort_values('date').reset_index(drop=True)
df = df[(df['date'] >= start_date) & (df['date'] <= last_date)].reset_index(drop=True)

for i in STOCK_ALL:
    cols = ['date', f'open_{i}', f'close_{i}', f'ma20_{i}', f'bf_{i}', f'ratio_{i}']
    df = pd.merge(df, dfs[i][cols], on='date', how='left')

all_ids = STOCK_ALL + [BOND]

# 计算各标的ret（open-to-open）
for i in all_ids:
    df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
last_idx = df.index[-1]
for i in all_ids:
    df[f'ret_{i}'] = np.nan
    mask = df[f'open_{i}_next'].notna() & df[f'open_{i}'].notna()
    df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
    if pd.notna(df.loc[last_idx, f'open_{i}']) and pd.notna(df.loc[last_idx, f'close_{i}']):
        df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

# ===== 3. 动态选股信号 =====
def get_signal(row):
    available = {}
    for i in STOCK_ALL:
        bf_val = row[f'bf_{i}']
        ratio_val = row[f'ratio_{i}']
        if pd.notna(bf_val) and pd.notna(ratio_val):
            available[i] = (bf_val, ratio_val)
    if not available:
        return BOND
    if all(v[1] < 1 for v in available.values()):
        return BOND
    return max(available, key=lambda k: available[k][0])

df['raw_signal'] = df.apply(get_signal, axis=1)
# T-1日收盘信号 → T日开盘执行
df['raw_position'] = df['raw_signal'].shift(1)
df.loc[df.index[0], 'raw_position'] = 0
df['raw_prev_position'] = df['raw_position'].shift(1)
df.loc[df.index[0], 'raw_prev_position'] = df.loc[df.index[0], 'raw_position']

# V8基线收益
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
        if prev in all_ids: cost += FEE
        if pos in all_ids: cost += FEE
    return (1 + gross) * (1 - cost) - 1

df['raw_strat_ret'] = df.apply(get_raw_strat_ret, axis=1)
df['raw_strat_nav'] = (1 + df['raw_strat_ret']).cumprod()
df['raw_cummax'] = df['raw_strat_nav'].cummax()
df['raw_dd'] = df['raw_strat_nav'] / df['raw_cummax'] - 1

# ===== 4. 应用5%/4%熔断 =====
raw_pos = df['raw_position'].values
raw_dd = df['raw_dd'].values
n = len(df)
in_cb = False
final_position = []
cb_events = []
for i in range(n):
    sig = int(raw_pos[i])
    dd = raw_dd[i]
    if not in_cb:
        if dd < -DD_TRIGGER and sig != BOND:
            in_cb = True
            final_position.append(BOND)
            cb_events.append((df['date'].iloc[i], '触发', dd))
        else:
            final_position.append(sig)
    else:
        if dd > -DD_RELEASE:
            in_cb = False
            final_position.append(sig)
            cb_events.append((df['date'].iloc[i], '解除', dd))
        else:
            final_position.append(BOND)
final_position = np.array(final_position)

# V14收益
prev_pos = np.concatenate([[final_position[0]], final_position[:-1]])
v14_rets = np.zeros(n)
for i in range(n):
    p = int(final_position[i])
    if p == 0:
        gross = 0.0
    else:
        ret_val = df[f'ret_{p}'].iloc[i]
        gross = ret_val if pd.notna(ret_val) else 0.0
    cost = 0.0
    if int(prev_pos[i]) != p:
        if int(prev_pos[i]) in all_ids: cost += FEE
        if p in all_ids: cost += FEE
    v14_rets[i] = (1 + gross) * (1 - cost) - 1

df['v14_pos'] = final_position
df['v14_ret'] = v14_rets
df['v14_nav'] = (1 + df['v14_ret']).cumprod()

# ===== 5. 构建导出数据 =====
rows = []
for i in range(n):
    date = df['date'].iloc[i]
    pos = int(df['v14_pos'].iloc[i])
    prev_p = int(prev_pos[i])
    signal = int(df['raw_signal'].iloc[i-1]) if i > 0 else 0  # T-1日信号

    # 决策bf（T-1日收盘）
    if signal in STOCK_ALL:
        signal_bf = df[f'bf_{signal}'].iloc[i-1] if i > 0 else np.nan
    else:
        signal_bf = np.nan

    # 所有成分bf（T-1日收盘）
    bf_strs = []
    for j in STOCK_ALL:
        bf_j = df[f'bf_{j}'].iloc[i-1] if i > 0 else np.nan
        if pd.notna(bf_j):
            above = '↑' if df[f'ratio_{j}'].iloc[i-1] >= 1 else '↓'
            bf_strs.append(f'{names[j]}{above}{bf_j:+.4f}')

    # 当日持仓的收益
    v14_ret = df['v14_ret'].iloc[i]
    v14_nav = df['v14_nav'].iloc[i]
    v8_dd = df['raw_dd'].iloc[i]
    v8_nav = df['raw_strat_nav'].iloc[i]

    changed = pos != prev_p
    is_cb = (pos == BOND and signal != BOND)

    rows.append({
        '决策日期': date.strftime('%Y-%m-%d'),
        '星期': ['一','二','三','四','五','六','日'][date.dayofweek],
        '实际持仓': all_names[pos],
        '前日持仓': all_names[prev_p],
        '是否换仓': '是' if changed else '否',
        '信号标的(T-1收盘)': all_names[signal],
        '决策bf(T-1)': f'{signal_bf:+.4f}' if pd.notna(signal_bf) else '',
        '各成分bf(T-1收盘)': ' | '.join(bf_strs) if bf_strs else '',
        'V14日收益': f'{v14_ret*100:+.2f}%',
        'V14净值': f'{v14_nav:.4f}',
        'V8回撤': f'{v8_dd*100:+.2f}%',
        'V8净值': f'{v8_nav:.4f}',
        '熔断状态': '熔断中' if is_cb else ('解除' if any(d.strftime('%Y-%m-%d')==date.strftime('%Y-%m-%d') and e=='解除' for d,e,_ in cb_events) else ''),
    })

result_df = pd.DataFrame(rows)
out_csv = os.path.join(BASE_DIR, 'v14_past_10year_detail.csv')
result_df.to_csv(out_csv, index=False, encoding='utf-8-sig')
print(f"CSV已导出: {out_csv}")
print(f"共 {len(result_df)} 天")
print(f"\n熔断事件({len(cb_events)}次):")
for d, e, dd in cb_events:
    print(f"  {d.strftime('%Y-%m-%d')} {e} (V8回撤={dd*100:+.2f}%)")

# 汇总统计
print(f"\n=== 近10年汇总 ===")
print(f"起始: {result_df['决策日期'].iloc[0]}")
print(f"结束: {result_df['决策日期'].iloc[-1]}")
print(f"总收益: {(df['v14_nav'].iloc[-1]-1)*100:+.2f}%")
print(f"换仓次数: {(result_df['是否换仓']=='是').sum()}")
holding_pct = result_df['实际持仓'].value_counts(normalize=True) * 100
print(f"\n持仓占比:")
for name, pct in holding_pct.items():
    print(f"  {name}: {pct:.1f}%")

# ===== 6. 生成HTML =====
def pos_tag(name):
    if name == '国债':
        return '<span class="tag tag-bond">国债</span>'
    elif name == '空仓':
        return '<span class="tag tag-empty">空仓</span>'
    else:
        return f'<span class="tag tag-stock">{name}</span>'

def ret_color(val):
    v = float(val.replace('%', '').replace('+', ''))
    cls = 'pos' if v > 0 else ('neg' if v < 0 else '')
    return f'<span class="{cls}">{val}</span>'

def dd_color(val):
    v = float(val.replace('%', '').replace('+', ''))
    if v < -5:
        return f'<span class="neg" style="font-weight:bold">{val}</span>'
    elif v < 0:
        return f'<span class="neg">{val}</span>'
    return val

rows_html = []
for idx, row in result_df.iterrows():
    row_class = ''
    cb_tag = ''
    if row['熔断状态'] == '熔断中':
        row_class = 'row-cb'
        cb_tag = '<span class="tag tag-cb">熔断中</span>'
    elif row['熔断状态'] == '解除':
        row_class = 'row-cb-release'
        cb_tag = '<span class="tag tag-release">解除</span>'
    elif row['是否换仓'] == '是':
        row_class = 'row-change'

    bf_detail = str(row['各成分bf(T-1收盘)']) if pd.notna(row['各成分bf(T-1收盘)']) else ''
    bf_parts = bf_detail.split(' | ') if bf_detail else []
    bf_html_parts = []
    for p in bf_parts:
        if '↑' in p:
            bf_html_parts.append(f'<span class="bf-pos">{p}</span>')
        elif '↓' in p:
            bf_html_parts.append(f'<span class="bf-neg">{p}</span>')
        else:
            bf_html_parts.append(p)
    bf_html = ' | '.join(bf_html_parts)

    sig_bf = str(row['决策bf(T-1)']) if pd.notna(row['决策bf(T-1)']) and row['决策bf(T-1)'] != '' else ''
    if sig_bf:
        sig_bf_val = float(sig_bf)
        bf_cls = 'pos' if sig_bf_val > 0 else 'neg'
        sig_bf = f'<span class="{bf_cls}">{sig_bf}</span>'

    change_icon = '<span style="color:#e65100">🔄</span>' if row['是否换仓'] == '是' else ''

    rows_html.append(f'''<tr class="{row_class}">
<td>{row["决策日期"]}</td>
<td>{row["星期"]}</td>
<td>{pos_tag(row["实际持仓"])}</td>
<td>{pos_tag(row["前日持仓"])}</td>
<td>{change_icon}</td>
<td>{row["信号标的(T-1收盘)"]}</td>
<td>{sig_bf}</td>
<td class="bf-detail">{bf_html}</td>
<td>{ret_color(row["V14日收益"])}</td>
<td class="nav">{row["V14净值"]}</td>
<td>{dd_color(row["V8回撤"])}</td>
<td>{cb_tag}</td>
</tr>''')

rows_str = '\n'.join(rows_html)
total_ret = (df['v14_nav'].iloc[-1]-1)*100
n_changes = (result_df['是否换仓']=='是').sum()
n_cb = len([e for _,e,_ in cb_events if e=='触发'])

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14近10年操作明细</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Microsoft YaHei', sans-serif; background: #f5f5f5; color: #333; padding: 20px; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
h1 {{ text-align: center; font-size: 24px; margin-bottom: 5px; color: #1a1a1a; }}
.subtitle {{ text-align: center; font-size: 14px; color: #888; margin-bottom: 20px; }}
.summary {{ display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }}
.summary-card {{ background: white; padding: 15px 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex: 1; min-width: 150px; text-align: center; }}
.summary-card .label {{ font-size: 12px; color: #888; margin-bottom: 5px; }}
.summary-card .value {{ font-size: 22px; font-weight: bold; }}
.pos {{ color: #e0394b; }}
.neg {{ color: #00897b; }}
.table-wrap {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
thead {{ position: sticky; top: 0; z-index: 10; }}
th {{ background: #2c3e50; color: white; padding: 10px 8px; text-align: center; font-weight: 500; white-space: nowrap; }}
th:first-child {{ text-align: left; padding-left: 15px; }}
td {{ padding: 7px 8px; text-align: center; border-bottom: 1px solid #f0f0f0; white-space: nowrap; }}
td:first-child {{ text-align: left; padding-left: 15px; font-weight: 500; }}
tr:hover {{ background: #f8f9fa; }}
.row-change {{ background: #fff8e1 !important; }}
.row-change:hover {{ background: #fff3cd !important; }}
.row-cb {{ background: #fce4ec !important; }}
.row-cb:hover {{ background: #f8bbd0 !important; }}
.row-cb-release {{ background: #e8f5e9 !important; }}
.row-cb-release:hover {{ background: #c8e6c9 !important; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 500; }}
.tag-bond {{ background: #607d8b; color: white; }}
.tag-stock {{ background: #1565c0; color: white; }}
.tag-empty {{ background: #9e9e9e; color: white; }}
.tag-cb {{ background: #c62828; color: white; }}
.tag-release {{ background: #2e7d32; color: white; }}
.bf-pos {{ color: #e0394b; }}
.bf-neg {{ color: #00897b; }}
.bf-detail {{ font-size: 11px; color: #666; max-width: 350px; white-space: normal; text-align: left; }}
.nav {{ font-family: 'Courier New', monospace; font-size: 12px; }}
.footer {{ text-align: center; margin-top: 15px; font-size: 12px; color: #aaa; }}
.legend {{ display: flex; gap: 15px; margin-bottom: 15px; justify-content: center; font-size: 12px; flex-wrap: wrap; }}
.legend-item {{ display: flex; align-items: center; gap: 5px; }}
.legend-color {{ width: 16px; height: 16px; border-radius: 3px; }}
</style>
</head>
<body>
<div class="container">
<h1>V14 MA20轮动策略 — 近10年操作明细</h1>
<p class="subtitle">{result_df.iloc[0]["决策日期"]} ~ {result_df.iloc[-1]["决策日期"]} | 决策bf=(T-1收盘/T-1 MA20)-1 | 收益口径open-to-open | 手续费0.02%</p>

<div class="summary">
<div class="summary-card"><div class="label">总收益</div><div class="value pos">{total_ret:+.2f}%</div></div>
<div class="summary-card"><div class="label">交易日数</div><div class="value">{len(result_df)}</div></div>
<div class="summary-card"><div class="label">换仓次数</div><div class="value">{n_changes}</div></div>
<div class="summary-card"><div class="label">熔断触发</div><div class="value neg">{n_cb}次</div></div>
</div>

<div class="legend">
<div class="legend-item"><div class="legend-color" style="background:#fff8e1;border:1px solid #ffd54f"></div>换仓日</div>
<div class="legend-item"><div class="legend-color" style="background:#fce4ec;border:1px solid #f48fb1"></div>熔断触发</div>
<div class="legend-item"><div class="legend-color" style="background:#e8f5e9;border:1px solid #81c784"></div>熔断解除</div>
</div>

<div class="table-wrap">
<table>
<thead>
<tr>
<th>决策日期</th>
<th>星期</th>
<th>实际持仓</th>
<th>前日持仓</th>
<th>换仓</th>
<th>信号标的(T-1收盘)</th>
<th>决策bf(T-1)</th>
<th>各成分bf(T-1收盘)</th>
<th>V14日收益</th>
<th>V14净值</th>
<th>V8回撤</th>
<th>熔断状态</th>
</tr>
</thead>
<tbody>
{rows_str}
</tbody>
</table>
</div>
<p class="footer">V14策略：5%/4%组合净值回撤熔断，8股+国债动态标的池 | 数据截至2026-07-22</p>
</div>
</body>
</html>'''

out_html = os.path.join(BASE_DIR, 'v14_past_10year_detail.html')
with open(out_html, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nHTML已导出: {out_html}")
