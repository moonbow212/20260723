# -*- coding: utf-8 -*-
"""V14(5%/4%)近5年逐年持仓占比及年化收益统计
标的池: 上证50、创业板50、纳斯达克100、沪深300、中证500、中证1000、标普500、科创50 + 国债 (近5年全程可用)
"""
import pandas as pd
import numpy as np
import json
import os
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

# 近5年8股+国债
files = {
    1: find_file('上证50'), 2: find_file('创业板50'),
    3: find_file('纳斯达克100'), 4: find_file('沪深300'),
    5: find_file('中证500'), 6: find_file('中证1000'),
    7: find_file('标普500'), 8: find_file('科创50'),
    9: find_file('国债'),
}
names = {1:'上证50', 2:'创业板50', 3:'纳斯达克100', 4:'沪深300',
         5:'中证500', 6:'中证1000', 7:'标普500', 8:'科创50', 9:'国债'}

dfs = {}
for i, path in files.items():
    d = pd.read_csv(path, sep='\t', encoding='gbk')
    d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
    d = d[['date','开盘','收盘']].rename(columns={'开盘':f'open_{i}','收盘':f'close_{i}'})
    for c in [f'open_{i}',f'close_{i}']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    dfs[i] = d.dropna()

last_date = dfs[9]['date'].max()
start_date = last_date - pd.DateOffset(years=5)
print(f"近5年: {start_date.date()} ~ {last_date.date()}")

STOCK = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9
all_ids = STOCK + [BOND]

# 构建完整数据
df = reduce(lambda a,b: pd.merge(a,b,on='date',how='inner'), [dfs[i] for i in all_ids])
df = df.sort_values('date').reset_index(drop=True)
df = df[(df['date'] >= start_date) & (df['date'] <= last_date)].reset_index(drop=True)

for i in STOCK:
    df[f'ma20_{i}'] = df[f'close_{i}'].rolling(20).mean()
    df[f'bf_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}'] - 1
    df[f'ratio_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}']
df = df.dropna(subset=[f'ma20_{i}' for i in STOCK]).reset_index(drop=True)

def get_signal(row):
    ratios = [row[f'ratio_{i}'] for i in STOCK]
    if all(r < 1 for r in ratios):
        return BOND
    bfs = {i: row[f'bf_{i}'] for i in STOCK}
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

# 应用熔断
raw_pos = df['raw_position'].values
raw_dd = df['raw_dd'].values
dates = df['date'].values
n = len(df)
in_cb = False
final_position = []
for i in range(n):
    sig = int(raw_pos[i])
    dd = raw_dd[i]
    if not in_cb:
        if dd < -DD_TRIGGER and sig != BOND:
            in_cb = True
            final_position.append(BOND)
        else:
            final_position.append(sig)
    else:
        if dd > -DD_RELEASE:
            in_cb = False
            final_position.append(sig)
        else:
            final_position.append(BOND)
pos_v14 = np.array(final_position)

# 计算V14逐日收益
prev_pos = np.concatenate([[pos_v14[0]], pos_v14[:-1]])
v14_rets = np.zeros(n)
for i in range(n):
    p = int(pos_v14[i])
    gross = df[f'ret_{p}'].iloc[i] if p in all_ids else 0.0
    cost = 0.0
    if int(prev_pos[i]) != p:
        if int(prev_pos[i]) in all_ids: cost += FEE
        if p in all_ids: cost += FEE
    v14_rets[i] = (1 + gross) * (1 - cost) - 1

df['v14_pos'] = pos_v14
df['v14_ret'] = v14_rets
df['v14_nav'] = (1 + df['v14_ret']).cumprod()
df['v8_nav'] = df['raw_strat_nav']
df['year'] = df['date'].dt.year

# 按年统计
all_names = {0:'空仓', 1:'上证50', 2:'创业板50', 3:'纳斯达克100', 4:'沪深300',
             5:'中证500', 6:'中证1000', 7:'标普500', 8:'科创50', 9:'国债'}
display_order = [1,2,3,4,5,6,7,8,9]
years = sorted(df['year'].unique())

print("\n" + "="*170)
print(f"{'年份':>6s} | {'天数':>4s} | {'V14收益':>8s} | {'V8收益':>8s} | {'超额':>8s} | {'V14回撤':>8s} | ", end='')
for a in display_order:
    print(f"{all_names[a]:>10s}", end=' ')
print()
print("-"*170)

yearly_data = []
for y in years:
    sub = df[df['year'] == y]
    ny = len(sub)
    v14_year_ret = (1 + sub['v14_ret']).prod() - 1
    v8_year_ret = (1 + sub['raw_strat_ret']).prod() - 1
    excess = v14_year_ret - v8_year_ret
    v14_year_nav = (1 + sub['v14_ret']).cumprod()
    v14_year_mdd = ((v14_year_nav - v14_year_nav.cummax()) / v14_year_nav.cummax()).min()
    
    pos_counts = {}
    for a in all_ids + [0]:
        cnt = int((sub['v14_pos'] == a).sum())
        if cnt > 0:
            pos_counts[all_names[a]] = {'days': cnt, 'pct': round(cnt/ny*100, 2)}
    
    print(f"{y:>6d} | {ny:>4d} | {v14_year_ret*100:>7.2f}% | {v8_year_ret*100:>7.2f}% | {excess*100:>+7.2f}% | {v14_year_mdd*100:>7.2f}% | ", end='')
    for a in display_order:
        cnt = int((sub['v14_pos'] == a).sum())
        if cnt > 0:
            print(f"{cnt/ny*100:>9.1f}%", end=' ')
        else:
            print(f"{'--':>10s}", end=' ')
    print()
    
    yearly_data.append({
        'year': int(y),
        'n_days': int(ny),
        'start': sub['date'].iloc[0].strftime('%Y-%m-%d'),
        'end': sub['date'].iloc[-1].strftime('%Y-%m-%d'),
        'v14_ret': round(float(v14_year_ret), 6),
        'v8_ret': round(float(v8_year_ret), 6),
        'excess': round(float(excess), 6),
        'v14_mdd': round(float(v14_year_mdd), 6),
        'holding': pos_counts,
        'v14_cb_days': int((sub['v14_pos'] == BOND).sum()),
        'v14_cb_pct': round(float((sub['v14_pos'] == BOND).sum() / ny), 6),
        'v14_switches': int(np.sum(np.diff(sub['v14_pos'].values) != 0)),
    })

# 整体统计
total_v14 = df['v14_nav'].iloc[-1] - 1
total_v8 = df['v8_nav'].iloc[-1] - 1
print("\n" + "="*170)
print(f"近5年整体: V14 {total_v14*100:.2f}%, V8 {total_v8*100:.2f}%, 超额 {(total_v14-total_v8)*100:+.2f}%")
print(f"V14年化: {(1+total_v14)**(1/5)-1:.4f}, V8年化: {(1+total_v8)**(1/5)-1:.4f}")

# 各资产5年总占比
print("\n各资产近5年总持仓占比:")
for a in all_ids + [0]:
    cnt = int((df['v14_pos'] == a).sum())
    if cnt > 0:
        print(f"  {all_names[a]:<12s}: {cnt:>5d}天 ({cnt/n*100:>6.2f}%)")

output = {
    'period': '近5年',
    'start': df['date'].iloc[0].strftime('%Y-%m-%d'),
    'end': df['date'].iloc[-1].strftime('%Y-%m-%d'),
    'n_days': int(n),
    'stock_pool': [names[i] for i in STOCK],
    'total_v14': float(total_v14),
    'total_v8': float(total_v8),
    'ann_v14': float((1+total_v14)**(1/5)-1),
    'ann_v8': float((1+total_v8)**(1/5)-1),
    'yearly': yearly_data,
    'overall_holding': {all_names[a]: {'days': int((df['v14_pos']==a).sum()), 'pct': round(float((df['v14_pos']==a).sum()/n*100), 2)} for a in all_ids+[0] if int((df['v14_pos']==a).sum())>0},
}

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_yearly_5y.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print("\n数据已保存到 v14_yearly_5y.json")
