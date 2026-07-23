# -*- coding: utf-8 -*-
"""统计V14(5%/4%)近1/3/5/10/20年各资产持仓天数占比"""
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

files = {
    1: find_file('上证50'), 2: find_file('创业板50'), 3: find_file('纳斯达克100'),
    4: find_file('沪深300'), 5: find_file('中证500'), 6: find_file('中证1000'),
    7: find_file('标普500'), 8: find_file('科创50'), 9: find_file('国债'),
}
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}

dfs = {}
for i, path in files.items():
    d = pd.read_csv(path, sep='\t', encoding='gbk')
    d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
    d = d[['date','开盘','收盘']].rename(columns={'开盘':f'open_{i}','收盘':f'close_{i}'})
    for c in [f'open_{i}',f'close_{i}']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    dfs[i] = d.dropna()

last_date = dfs[9]['date'].max()

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

def apply_circuit_breaker(df, all_ids, bond_id, dd_trigger, dd_release):
    raw_pos = df['raw_position'].values
    raw_dd = df['raw_dd'].values
    dates = df['date'].values
    n = len(df)
    in_cb = False
    final_position = []
    cb_events = []
    for i in range(n):
        sig = int(raw_pos[i])
        dd = raw_dd[i]
        if not in_cb:
            if dd < -dd_trigger and sig != bond_id:
                in_cb = True
                cb_events.append({'date': str(dates[i])[:10], 'event':'TRIGGER', 'dd': float(dd), 'from': sig, 'to': bond_id})
                final_position.append(bond_id)
            else:
                final_position.append(sig)
        else:
            if dd > -dd_release:
                in_cb = False
                cb_events.append({'date': str(dates[i])[:10], 'event':'RELEASE', 'dd': float(dd), 'from': bond_id, 'to': sig})
                final_position.append(sig)
            else:
                final_position.append(bond_id)
    return np.array(final_position), cb_events

print("构建数据并统计持仓占比...\n")
all_results = {}
period_order = ['近20年','近10年','近5年','近3年','近1年']

for pname in period_order:
    stocks, sd = periods_config[pname]
    df, all_ids = build_period_data(stocks, BOND, sd, last_date)
    n = len(df)
    
    # V14持仓
    pos_v14, cb_events = apply_circuit_breaker(df, all_ids, BOND, DD_TRIGGER, DD_RELEASE)
    # V8持仓
    pos_v8 = df['raw_position'].values.astype(int)
    
    # 统计V14各资产持仓天数
    v14_counts = {}
    v8_counts = {}
    for i in all_ids:
        v14_counts[i] = int(np.sum(pos_v14 == i))
        v8_counts[i] = int(np.sum(pos_v8 == i))
    # 空仓(pos=0)
    v14_counts[0] = int(np.sum(pos_v14 == 0))
    v8_counts[0] = int(np.sum(pos_v8 == 0))
    
    all_names = {0:'空仓', **names}
    all_ids_with_0 = [0] + all_ids
    
    print(f"=== {pname} ({df['date'].iloc[0].date()}~{df['date'].iloc[-1].date()}, {n}天) ===")
    print(f"  标的池: {[names[i] for i in stocks]} + 国债")
    print(f"  {'资产':<12s} | {'V14天数':>7s} {'V14占比':>8s} | {'V8天数':>7s} {'V8占比':>8s}")
    print(f"  {'-'*55}")
    # 按V14占比降序
    sorted_ids = sorted(all_ids_with_0, key=lambda x: -v14_counts[x])
    for i in sorted_ids:
        v14d = v14_counts[i]
        v8d = v8_counts[i]
        if v14d == 0 and v8d == 0:
            continue
        nm = all_names[i]
        print(f"  {nm:<12s} | {v14d:>7d} {v14d/n*100:>7.2f}% | {v8d:>7d} {v8d/n*100:>7.2f}%")
    print()
    
    all_results[pname] = {
        'n_days': n,
        'start': df['date'].iloc[0].strftime('%Y-%m-%d'),
        'end': df['date'].iloc[-1].strftime('%Y-%m-%d'),
        'stock_ids': stocks,
        'stock_names': [names[i] for i in stocks],
        'v14_counts': {all_names[i]: v14_counts[i] for i in all_ids_with_0 if v14_counts[i] > 0},
        'v8_counts': {all_names[i]: v8_counts[i] for i in all_ids_with_0 if v8_counts[i] > 0},
        'v14_cb_days': v14_counts.get(BOND, 0),
        'v14_cb_pct': v14_counts.get(BOND, 0) / n,
        'v8_cb_days': v8_counts.get(BOND, 0),
        'v8_cb_pct': v8_counts.get(BOND, 0) / n,
        'v14_switches': int(np.sum(np.diff(pos_v14) != 0)),
        'v8_switches': int(np.sum(np.diff(pos_v8) != 0)),
    }

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_holding_pct.json', 'w', encoding='utf-8') as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)
print("数据已保存到 v14_holding_pct.json")
