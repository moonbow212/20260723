# -*- coding: utf-8 -*-
"""分析2024年历史最高点 vs 近1年最高点的持仓差异"""
import pandas as pd
import numpy as np
import os

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
        continue
    d = pd.read_csv(csv_path, parse_dates=['date'])
    d = d[['date', 'open', 'close']].rename(columns={'open': f'open_{i}', 'close': f'close_{i}'})
    d = d.sort_values('date').reset_index(drop=True)
    if i != BOND:
        d[f'ma{MA_PERIOD}_{i}'] = d[f'close_{i}'].rolling(MA_PERIOD).mean()
        d[f'bf{MA_PERIOD}_{i}'] = d[f'close_{i}'] / d[f'ma{MA_PERIOD}_{i}'] - 1
        d[f'ratio{MA_PERIOD}_{i}'] = d[f'close_{i}'] / d[f'ma{MA_PERIOD}_{i}']
    dfs[i] = d

last_date = dfs[BOND]['date'].max()
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

# 收益
for i in all_ids:
    df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
last_idx = df.index[-1]
for i in all_ids:
    df[f'ret_{i}'] = np.nan
    mask = df[f'open_{i}_next'].notna() & df[f'open_{i}'].notna()
    df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
    if pd.notna(df.loc[last_idx, f'open_{i}']) and pd.notna(df.loc[last_idx, f'close_{i}']):
        df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

# ===== V8基线 =====
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

# ===== 回撤计算 =====
df['dd_alltime'] = df['raw_strat_nav'] / df['raw_strat_nav'].cummax() - 1
df['peak_1y'] = df['raw_strat_nav'].rolling(252, min_periods=1).max()
df['dd_1y'] = df['raw_strat_nav'] / df['peak_1y'] - 1

# ===== 应用熔断 =====
def apply_circuit_breaker(df, dd_col):
    raw_pos = df['raw_position'].values
    dd = df[dd_col].values
    safe_havens = df['safe_haven'].values
    n = len(df)
    in_cb = False
    final_position = []
    cb_count = 0
    cb_states = []
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
        cb_states.append(in_cb)
    return np.array(final_position), cb_count, cb_states

pos_alltime, cb_count_at, cb_states_at = apply_circuit_breaker(df, 'dd_alltime')
pos_1y, cb_count_1y, cb_states_1y = apply_circuit_breaker(df, 'dd_1y')

df['pos_alltime'] = pos_alltime
df['pos_1y'] = pos_1y
df['cb_alltime'] = cb_states_at
df['cb_1y'] = cb_states_1y

# ===== 2024年分析 =====
df['year'] = df['date'].dt.year
sub_2024 = df[df['year'] == 2024].copy()

print(f"\n=== 2024年收益 ===")
ret_at = (1 + df[df['year']==2024]['raw_strat_ret']).prod() - 1  # V8
# Compute V14 returns for each version
def compute_v14_ret(df, pos_col):
    n = len(df)
    pos = df[pos_col].values
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

df['ret_alltime'] = compute_v14_ret(df, 'pos_alltime')
df['ret_1y'] = compute_v14_ret(df, 'pos_1y')

year_ret_at = (1 + df[df['year']==2024]['ret_alltime']).prod() - 1
year_ret_1y = (1 + df[df['year']==2024]['ret_1y']).prod() - 1
print(f"历史最高点版: {year_ret_at*100:.2f}%")
print(f"近1年最高点版: {year_ret_1y*100:.2f}%")
print(f"差异: {(year_ret_1y - year_ret_at)*100:.2f}%")

# ===== 找差异日 =====
print(f"\n=== 2024年持仓差异日 ===")
print(f"{'日期':<12} {'V8净值':>10} {'历史峰':>10} {'1年峰':>10} {'历史DD':>8} {'1年DD':>8} {'历史CB':>6} {'1年CB':>6} {'历史持仓':>12} {'1年持仓':>12}")

diff_count = 0
for idx, row in sub_2024.iterrows():
    i = idx  # This is the index in the original df
    p_at = int(df.loc[i, 'pos_alltime'])
    p_1y = int(df.loc[i, 'pos_1y'])
    cb_at = df.loc[i, 'cb_alltime']
    cb_1y = df.loc[i, 'cb_1y']
    
    if p_at != p_1y or cb_at != cb_1y:
        diff_count += 1
        date_str = row['date'].strftime('%Y-%m-%d')
        v8 = df.loc[i, 'raw_strat_nav']
        peak_at = df.loc[i, 'raw_strat_nav'] if pd.isna(df.loc[i, 'raw_strat_nav']) else df['raw_strat_nav'].iloc[:i+1].max()
        peak_1y = df.loc[i, 'peak_1y']
        dd_at = df.loc[i, 'dd_alltime']
        dd_1y = df.loc[i, 'dd_1y']
        name_at = names.get(p_at, str(p_at))
        name_1y = names.get(p_1y, str(p_1y))
        print(f"{date_str:<12} {v8:>10.2f} {peak_at:>10.2f} {peak_1y:>10.2f} {dd_at*100:>7.2f}% {dd_1y*100:>7.2f}% {'ON' if cb_at else 'OFF':>6} {'ON' if cb_1y else 'OFF':>6} {name_at:>12} {name_1y:>12}")

print(f"\n总差异天数: {diff_count}")

# ===== CB状态变化 =====
print(f"\n=== 2024年熔断状态变化 ===")
print(f"--- 历史最高点版 ---")
prev_cb = df[df['year']==2024].iloc[0]['cb_alltime'] if len(df[df['year']==2024]) > 0 else False
# Get the CB state just before 2024 starts
idx_2024_start = df[df['year']==2024].index[0]
prev_cb = df.loc[idx_2024_start - 1, 'cb_alltime'] if idx_2024_start > 0 else False
for i in df[df['year']==2024].index:
    if df.loc[i, 'cb_alltime'] != prev_cb:
        date_str = df.loc[i, 'date'].strftime('%Y-%m-%d')
        v8 = df.loc[i, 'raw_strat_nav']
        dd = df.loc[i, 'dd_alltime']
        peak = df['raw_strat_nav'].iloc[:i+1].max()
        action = "触发熔断→避险" if df.loc[i, 'cb_alltime'] else "解除熔断→选股"
        pos = names.get(int(df.loc[i, 'pos_alltime']), '?')
        print(f"  {date_str}: {action} (V8={v8:.2f}, 历史峰={peak:.2f}, DD={dd*100:.2f}%, 持仓={pos})")
        prev_cb = df.loc[i, 'cb_alltime']

print(f"--- 近1年最高点版 ---")
prev_cb = df.loc[idx_2024_start - 1, 'cb_1y'] if idx_2024_start > 0 else False
for i in df[df['year']==2024].index:
    if df.loc[i, 'cb_1y'] != prev_cb:
        date_str = df.loc[i, 'date'].strftime('%Y-%m-%d')
        v8 = df.loc[i, 'raw_strat_nav']
        dd = df.loc[i, 'dd_1y']
        peak = df.loc[i, 'peak_1y']
        action = "触发熔断→避险" if df.loc[i, 'cb_1y'] else "解除熔断→选股"
        pos = names.get(int(df.loc[i, 'pos_1y']), '?')
        print(f"  {date_str}: {action} (V8={v8:.2f}, 1年峰={peak:.2f}, DD={dd*100:.2f}%, 持仓={pos})")
        prev_cb = df.loc[i, 'cb_1y']

# ===== 持仓占比 =====
print(f"\n=== 2024年持仓占比 ===")
from collections import Counter
for version_name, col in [("历史最高点", "pos_alltime"), ("近1年最高点", "pos_1y")]:
    pos_list = [int(df.loc[i, col]) for i in df[df['year']==2024].index]
    cnt = Counter(pos_list)
    total = len(pos_list)
    print(f"\n{version_name}版:")
    for pid, count in cnt.most_common():
        pct = count / total * 100
        print(f"  {names.get(pid, str(pid))}: {count}天 ({pct:.1f}%)")

# ===== 2023年底的情况（解释2024年初差异） =====
print(f"\n=== 2023年底V8净值与回撤 ===")
sub_2023 = df[df['year']==2023]
for i in sub_2023.index[-5:]:
    date_str = df.loc[i, 'date'].strftime('%Y-%m-%d')
    v8 = df.loc[i, 'raw_strat_nav']
    peak_at = df['raw_strat_nav'].iloc[:i+1].max()
    peak_1y = df.loc[i, 'peak_1y']
    dd_at = df.loc[i, 'dd_alltime']
    dd_1y = df.loc[i, 'dd_1y']
    cb_at = df.loc[i, 'cb_alltime']
    cb_1y = df.loc[i, 'cb_1y']
    pos_at = names.get(int(df.loc[i, 'pos_alltime']), '?')
    pos_1y = names.get(int(df.loc[i, 'pos_1y']), '?')
    print(f"  {date_str}: V8={v8:.2f} 历史峰={peak_at:.2f}(DD={dd_at*100:.2f}%) 1年峰={peak_1y:.2f}(DD={dd_1y*100:.2f}%) CB:{'ON' if cb_at else 'OFF'}/{'ON' if cb_1y else 'OFF'} 持仓:{pos_at}/{pos_1y}")
