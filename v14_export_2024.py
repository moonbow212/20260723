# -*- coding: utf-8 -*-
"""导出2024年每天持仓与操作明细
策略定义：决策日期=T日，决策bf=(T-1收盘/T-1的MA20)-1，T日开盘执行
新标的池：创业板50·纳斯达克100·中证500·中证1000·标普500·科创50·中证A500·北证50·中证A50
动态避险：金>20日MA→黄金ETF，金≤20日MA→国债
费率：万0.5
"""
import pandas as pd
import numpy as np
import os

FEE = 0.00005
DD_TRIGGER = 0.05
DD_RELEASE = 0.04
GOLD_START = pd.Timestamp('2013-07-29')

STOCK_ALL = [2, 3, 5, 6, 7, 8, 11, 12, 13]
BOND = 9
GOLD = 10
names = {2:'创业板50',3:'纳斯达克100',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债',10:'黄金ETF',11:'中证A500',12:'北证50',13:'中证A50'}
all_names = {0:'空仓',2:'创业板50',3:'纳斯达克100',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债',10:'黄金ETF',11:'中证A500',12:'北证50',13:'中证A50'}

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
        d[f'ma20_{i}'] = d[f'close_{i}'].rolling(20).mean()
        d[f'bf_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}'] - 1
        d[f'ratio_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}']
    dfs[i] = d
    print(f"  {names[i]}: {d['date'].iloc[0].date()} ~ {d['date'].iloc[-1].date()}, {len(d)}条")

last_date = dfs[BOND]['date'].max()

# ===== 2. 构建合并数据（近20年，动态join）=====
start_date = last_date - pd.DateOffset(years=20)
df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
df = df.sort_values('date').reset_index(drop=True)
df = df[(df['date'] >= start_date) & (df['date'] <= last_date)].reset_index(drop=True)

for i in STOCK_ALL:
    if i not in dfs:
        continue
    cols = ['date', f'open_{i}', f'close_{i}', f'ma20_{i}', f'bf_{i}', f'ratio_{i}']
    df = pd.merge(df, dfs[i][cols], on='date', how='left')

# 合并黄金ETF数据
gold_cols = ['date', f'open_{GOLD}', f'close_{GOLD}']
df = pd.merge(df, dfs[GOLD][gold_cols], on='date', how='left')

# 避险资产：黄金收盘价>20日均线→黄金ETF，≤20日均线→国债
df['gold_ma20'] = df[f'close_{GOLD}'].rolling(20).mean()
df['safe_haven'] = BOND
mask_gold_available = df['date'] >= GOLD_START
mask_ma_available = df['gold_ma20'].notna()
mask_above_ma = df[f'close_{GOLD}'] > df['gold_ma20']
df.loc[mask_gold_available & mask_ma_available & mask_above_ma, 'safe_haven'] = GOLD

all_ids = STOCK_ALL + [BOND, GOLD]

# 计算收益率（open-to-open）
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
        if i not in dfs:
            continue
        bf_val = row[f'bf_{i}']
        ratio_val = row[f'ratio_{i}']
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
safe_havens = df['safe_haven'].values
n = len(df)
in_cb = False
final_position = []
cb_events = []

for i in range(n):
    sig = int(raw_pos[i])
    dd = raw_dd[i]
    safe = int(safe_havens[i])
    if not in_cb:
        if dd < -DD_TRIGGER and sig != safe:
            in_cb = True
            cb_events.append({'idx': i, 'date': df['date'].iloc[i], 'event': 'TRIGGER', 'dd': float(dd), 'from': sig, 'to': safe})
            final_position.append(safe)
        else:
            final_position.append(sig)
    else:
        if dd > -DD_RELEASE:
            in_cb = False
            cb_events.append({'idx': i, 'date': df['date'].iloc[i], 'event': 'RELEASE', 'dd': float(dd), 'from': safe, 'to': sig})
            final_position.append(sig)
        else:
            final_position.append(safe)

final_position = np.array(final_position)
prev_pos_arr = np.concatenate([[final_position[0]], final_position[:-1]])

# V14收益率
v14_rets = np.zeros(n)
for i in range(n):
    p = int(final_position[i])
    if p == 0:
        gross = 0.0
    else:
        ret_val = df[f'ret_{p}'].iloc[i]
        gross = ret_val if pd.notna(ret_val) else 0.0
    cost = 0.0
    if int(prev_pos_arr[i]) != p:
        if int(prev_pos_arr[i]) in all_ids: cost += FEE
        if p in all_ids: cost += FEE
    v14_rets[i] = (1 + gross) * (1 - cost) - 1

df['v14_pos'] = final_position
df['v14_ret'] = v14_rets
df['v14_nav'] = (1 + df['v14_ret']).cumprod()

# ===== 5. 筛选2024年数据 =====
df_2024 = df[(df['date'] >= '2024-01-01') & (df['date'] <= '2024-12-31')].copy()
n2024 = len(df_2024)
print(f"\n2024年共 {n2024} 个交易日")

# ===== 6. 构建导出数据 =====
rows = []
for idx in df_2024.index:
    date = df['date'].iloc[idx]
    pos = int(df['v14_pos'].iloc[idx])
    prev_p = int(prev_pos_arr[idx])
    signal = int(df['raw_signal'].iloc[idx - 1]) if idx > 0 else 0
    safe = int(df['safe_haven'].iloc[idx])

    # 决策bf（T-1日收盘）
    if signal in STOCK_ALL:
        signal_bf = df[f'bf_{signal}'].iloc[idx - 1] if idx > 0 else np.nan
    else:
        signal_bf = np.nan

    # 各成分bf（T-1日收盘）
    bf_strs = []
    for j in STOCK_ALL:
        if j not in dfs:
            continue
        bf_j = df[f'bf_{j}'].iloc[idx - 1] if idx > 0 else np.nan
        if pd.notna(bf_j):
            above = '↑' if df[f'ratio_{j}'].iloc[idx - 1] >= 1 else '↓'
            bf_strs.append(f'{names[j]}{above}{bf_j:+.4f}')

    v14_ret = df['v14_ret'].iloc[idx]
    v14_nav = df['v14_nav'].iloc[idx]
    v8_dd = df['raw_dd'].iloc[idx]
    v8_nav = df['raw_strat_nav'].iloc[idx]

    changed = pos != prev_p
    is_cb = (pos == safe and signal != safe and pos in [BOND, GOLD])

    rows.append({
        '决策日期': date.strftime('%Y-%m-%d'),
        '星期': ['一','二','三','四','五','六','日'][date.dayofweek],
        '实际持仓': all_names[pos],
        '前日持仓': all_names[prev_p],
        '是否换仓': '是' if changed else '否',
        '信号标的(T-1收盘)': all_names[signal],
        '决策bf(T-1)': f'{signal_bf:+.4f}' if pd.notna(signal_bf) else '',
        '避险资产': names[safe],
        '各成分bf(T-1收盘)': ' | '.join(bf_strs) if bf_strs else '',
        'V14日收益': f'{v14_ret*100:+.2f}%',
        'V14净值': f'{v14_nav:.4f}',
        'V8回撤': f'{v8_dd*100:+.2f}%',
        'V8净值': f'{v8_nav:.4f}',
        '熔断状态': '熔断中' if is_cb else '',
    })

result_df = pd.DataFrame(rows)
out_csv = os.path.join(BASE_DIR, 'v14_2024_detail.csv')
result_df.to_csv(out_csv, index=False, encoding='utf-8-sig')
print(f"CSV已导出: {out_csv}")

# 2024年汇总
nav_start = float(df['v14_nav'].iloc[df_2024.index[0] - 1]) if df_2024.index[0] > 0 else 1.0
nav_end = float(df['v14_nav'].iloc[df_2024.index[-1]])
year_ret = (nav_end / nav_start - 1) * 100
print(f"\n=== 2024年汇总 ===")
print(f"起始日期: {result_df['决策日期'].iloc[0]}")
print(f"结束日期: {result_df['决策日期'].iloc[-1]}")
print(f"年初净值: {nav_start:.4f}")
print(f"年末净值: {nav_end:.4f}")
print(f"全年收益: {year_ret:+.2f}%")
print(f"换仓次数: {(result_df['是否换仓']=='是').sum()}")
holding_pct = result_df['实际持仓'].value_counts(normalize=True) * 100
print(f"\n持仓占比:")
for name, pct in holding_pct.items():
    print(f"  {name}: {pct:.1f}%")

# 熔断事件
cb_2024 = [e for e in cb_events if df['date'].iloc[e['idx']].year == 2024]
print(f"\n2024年熔断事件:")
for e in cb_2024:
    print(f"  {df['date'].iloc[e['idx']].strftime('%Y-%m-%d')} {e['event']} (V8回撤={e['dd']*100:+.2f}%, {all_names[e['from']]}→{all_names[e['to']]})")

# ===== 7. 生成HTML报告 =====
# 构建换仓明细
changes = result_df[result_df['是否换仓'] == '是'].copy()
change_rows = ''
for _, r in changes.iterrows():
    change_rows += f"""
        <tr>
            <td>{r['决策日期']}</td>
            <td>{r['星期']}</td>
            <td><span class="from">{r['前日持仓']}</span> → <span class="to">{r['实际持仓']}</span></td>
            <td>{r['信号标的(T-1收盘)']}</td>
            <td>{r['决策bf(T-1)']}</td>
            <td class="{'pos' if '+' in r['V14日收益'] else 'neg'}">{r['V14日收益']}</td>
            <td>{r['V14净值']}</td>
            <td>{r['V8回撤']}</td>
        </tr>"""

# 构建每日明细表格
daily_rows = ''
for _, r in result_df.iterrows():
    is_change = r['是否换仓'] == '是'
    row_class = 'change' if is_change else ''
    if '熔断中' in r['熔断状态']:
        row_class = 'cb'
    daily_rows += f"""
        <tr class="{row_class}">
            <td>{r['决策日期']}</td>
            <td>{r['星期']}</td>
            <td><b>{r['实际持仓']}</b></td>
            <td>{r['是否换仓']}</td>
            <td>{r['信号标的(T-1收盘)']}</td>
            <td>{r['决策bf(T-1)']}</td>
            <td>{r['避险资产']}</td>
            <td class="{'pos' if '+' in r['V14日收益'] else 'neg'}">{r['V14日收益']}</td>
            <td>{r['V14净值']}</td>
            <td>{r['V8回撤']}</td>
            <td>{r['熔断状态']}</td>
        </tr>"""

# 持仓占比
holding_bars = ''
for name, pct in holding_pct.items():
    color = '#3498db' if name not in ['国债', '黄金ETF'] else ('#95a5a6' if name == '国债' else '#d4a017')
    holding_bars += f"""
        <div style="display:flex;align-items:center;gap:8px;margin:4px 0;">
            <span style="width:90px;text-align:right;font-size:12px;">{name}</span>
            <div style="flex:1;background:#f0f0f0;height:20px;border-radius:4px;overflow:hidden;">
                <div style="width:{pct:.1f}%;height:100%;background:{color};border-radius:4px;"></div>
            </div>
            <span style="width:50px;font-size:12px;">{pct:.1f}%</span>
        </div>"""

# 月度收益
result_df['月份'] = result_df['决策日期'].str[:7]
monthly = []
for month, group in result_df.groupby('月份'):
    m_nav_start = float(group['V14净值'].iloc[0])
    m_nav_end = float(group['V14净值'].iloc[-1])
    # 需要前一个月末净值
    first_idx_in_month = df_2024.index[group.index[0]]
    if first_idx_in_month > 0:
        prev_nav = float(df['v14_nav'].iloc[first_idx_in_month - 1])
    else:
        prev_nav = m_nav_start
    m_ret = (m_nav_end / prev_nav - 1) * 100
    m_changes = (group['是否换仓'] == '是').sum()
    monthly.append({'月份': month, '收益': m_ret, '换仓': m_changes, '天数': len(group)})

monthly_rows = ''
for m in monthly:
    monthly_rows += f"""
        <tr>
            <td>{m['月份']}</td>
            <td class="{'pos' if m['收益'] > 0 else 'neg'}">{m['收益']:+.2f}%</td>
            <td>{m['换仓']}</td>
            <td>{m['天数']}</td>
        </tr>"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14策略 2024年操作明细</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif; background:#f5f5f5; color:#333; padding:16px; }}
.container {{ max-width:1100px; margin:0 auto; }}
h1 {{ font-size:20px; margin-bottom:8px; }}
h2 {{ font-size:16px; margin:20px 0 10px; padding-bottom:6px; border-bottom:2px solid #3498db; }}
.sub {{ font-size:13px; color:#888; margin-bottom:16px; }}
.summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:20px; }}
.card {{ background:#fff; border-radius:10px; padding:14px 18px; box-shadow:0 2px 8px rgba(0,0,0,0.06); }}
.card .label {{ font-size:12px; color:#888; margin-bottom:4px; }}
.card .value {{ font-size:22px; font-weight:700; }}
.card .value.pos {{ color:#e74c3c; }}
.card .value.neg {{ color:#27ae60; }}
table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.06); font-size:13px; }}
th {{ background:#2c3e50; color:#fff; padding:8px 10px; text-align:left; font-weight:500; white-space:nowrap; }}
td {{ padding:7px 10px; border-bottom:1px solid #f0f0f0; white-space:nowrap; }}
tr.change {{ background:#fff8e1; }}
tr.cb {{ background:#ffebee; }}
.pos {{ color:#e74c3c; font-weight:600; }}
.neg {{ color:#27ae60; font-weight:600; }}
.from {{ color:#999; }}
.to {{ color:#e74c3c; font-weight:600; }}
.scroll {{ overflow-x:auto; }}
.holding {{ background:#fff; border-radius:8px; padding:14px 18px; box-shadow:0 2px 8px rgba(0,0,0,0.06); }}
</style>
</head>
<body>
<div class="container">
    <h1>V14策略 2024年操作明细</h1>
    <div class="sub">新标的池(9只) · 动态避险(金>20日MA→黄金ETF,金≤20日MA→国债) · 费率万0.5 · 5%/4%熔断 · open-to-open口径</div>

    <div class="summary">
        <div class="card"><div class="label">全年收益</div><div class="value {'pos' if year_ret > 0 else 'neg'}">{year_ret:+.2f}%</div></div>
        <div class="card"><div class="label">年初净值</div><div class="value">{nav_start:.2f}</div></div>
        <div class="card"><div class="label">年末净值</div><div class="value">{nav_end:.2f}</div></div>
        <div class="card"><div class="label">交易日数</div><div class="value">{n2024}</div></div>
        <div class="card"><div class="label">换仓次数</div><div class="value">{(result_df['是否换仓']=='是').sum()}</div></div>
        <div class="card"><div class="label">熔断事件</div><div class="value">{len(cb_2024)}</div></div>
    </div>

    <h2>月度收益</h2>
    <table>
        <tr><th>月份</th><th>收益</th><th>换仓次数</th><th>交易日</th></tr>
        {monthly_rows}
    </table>

    <h2>持仓占比</h2>
    <div class="holding">{holding_bars}</div>

    <h2>换仓明细</h2>
    <div class="scroll">
    <table>
        <tr><th>日期</th><th>星期</th><th>换仓</th><th>信号标的</th><th>决策bf</th><th>当日收益</th><th>V14净值</th><th>V8回撤</th></tr>
        {change_rows}
    </table>
    </div>

    <h2>每日完整明细</h2>
    <div class="scroll">
    <table>
        <tr><th>日期</th><th>星期</th><th>实际持仓</th><th>换仓</th><th>信号标的</th><th>决策bf</th><th>避险资产</th><th>V14日收益</th><th>V14净值</th><th>V8回撤</th><th>熔断</th></tr>
        {daily_rows}
    </table>
    </div>
</div>
</body>
</html>"""

out_html = os.path.join(BASE_DIR, 'v14_2024_detail.html')
with open(out_html, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"HTML已导出: {out_html}")
