# -*- coding: utf-8 -*-
"""
MA20轮动策略 10%/8%阈值 vs 5%/4%阈值 多时段对比
在V14(8股+国债)基础上，把熔断阈值从5%/4%改为10%/8%，跑近1/3/5/10/20年。
复用v14_periods.py的数据构建逻辑。
"""
import pandas as pd
import numpy as np
import json
import os
from functools import reduce

FEE = 0.0002

# ============ 1. 读取数据 ============
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

last_date = pd.Timestamp('2026-07-17')
print(f"数据截止: {last_date.date()}")

STOCK_20Y = [1, 3, 4, 6]
STOCK_10Y = [1, 2, 3, 4, 5, 6, 7]
STOCK_RECENT = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9

periods_config = {
    '近20年': (STOCK_20Y, last_date - pd.DateOffset(years=20)),
    '近10年': (STOCK_10Y, last_date - pd.DateOffset(years=10)),
    '近5年': (STOCK_RECENT, last_date - pd.DateOffset(years=5)),
    '近3年': (STOCK_RECENT, last_date - pd.DateOffset(years=3)),
    '近1年': (STOCK_RECENT, last_date - pd.DateOffset(years=1)),
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
    df['signal'] = df.apply(get_signal, axis=1)

    for i in all_ids:
        df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
    last_idx = df.index[-1]
    for i in all_ids:
        df[f'ret_{i}'] = np.nan
        mask = df[f'open_{i}_next'].notna() & df[f'open_{i}'].notna()
        df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
        if pd.notna(df.loc[last_idx, f'open_{i}']) and pd.notna(df.loc[last_idx, f'close_{i}']):
            df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1
        df[f'ret_{i}'] = df[f'ret_{i}'].fillna(0)

    df['raw_position'] = df['signal'].shift(1)
    df.loc[df.index[0], 'raw_position'] = 0
    df['prev_raw_pos'] = df['raw_position'].shift(1)
    df.loc[df.index[0], 'prev_raw_pos'] = df.loc[df.index[0], 'raw_position']

    def get_ret(row):
        pos = int(row['raw_position'])
        gross = row[f'ret_{pos}'] if pos in all_ids else 0.0
        prev = int(row['prev_raw_pos'])
        cost = 0.0
        if prev != pos:
            if prev in all_ids: cost += FEE
            if pos in all_ids: cost += FEE
        return (1 + gross) * (1 - cost) - 1
    df['raw_ret'] = df.apply(get_ret, axis=1)
    df['raw_nav'] = (1 + df['raw_ret']).cumprod()
    df['cummax'] = df['raw_nav'].cummax()
    df['raw_dd'] = df['raw_nav'] / df['cummax'] - 1

    for i in all_ids:
        df[f'bh_{i}'] = (1 + df[f'ret_{i}']).cumprod()
    return df, all_ids

# ============ 2. 应用熔断 ============
def apply_circuit_breaker(df, dd_trigger, dd_release, bond_id):
    n = len(df)
    raw_pos = df['raw_position'].fillna(0).astype(int).values
    raw_dd = df['raw_dd'].values
    dates = df['date'].values
    in_cb = False
    final_position = np.zeros(n, dtype=int)
    cb_events = []
    for i in range(n):
        sig = int(raw_pos[i])
        dd = raw_dd[i]
        if not in_cb:
            if dd < -dd_trigger and sig != bond_id:
                in_cb = True
                cb_events.append({'date': str(dates[i])[:10], 'event':'TRIGGER', 'dd': float(dd)})
                final_position[i] = bond_id
            else:
                final_position[i] = sig
        else:
            if dd > -dd_release:
                in_cb = False
                cb_events.append({'date': str(dates[i])[:10], 'event':'RELEASE', 'dd': float(dd)})
                final_position[i] = sig
            else:
                final_position[i] = bond_id
    return final_position, cb_events

def compute_metrics(df, pos, all_ids, bond_id):
    n = len(df)
    prev_pos = np.concatenate([[pos[0]], pos[:-1]])
    rets = np.zeros(n)
    costs = np.zeros(n)
    for i in range(n):
        p = int(pos[i])
        gross = df[f'ret_{p}'].iloc[i] if p in all_ids else 0.0
        cost = 0.0
        if int(prev_pos[i]) != p:
            if int(prev_pos[i]) in all_ids: cost += FEE
            if p in all_ids: cost += FEE
        costs[i] = cost
        rets[i] = (1 + gross) * (1 - cost) - 1
    nav = (1 + rets).cumprod()
    switches = int(np.sum(np.diff(pos) != 0))
    cb_days = int(np.sum(pos == bond_id))
    cb_pct = cb_days / n
    total = nav[-1] - 1
    ann_ret = (1 + total) ** (252 / n) - 1
    mdd_val = ((nav - np.maximum.accumulate(nav)) / np.maximum.accumulate(nav)).min()
    std = rets.std()
    sharpe = np.sqrt(252) * rets.mean() / std if std > 0 else 0
    return {
        'total': float(total), 'ann': float(ann_ret), 'mdd': float(mdd_val),
        'sharpe': float(sharpe), 'switches': switches, 'cb_days': cb_days,
        'cb_pct': float(cb_pct), 'total_fee': float(costs.sum()),
        'ann_vol': float(std * np.sqrt(252)),
    }

# ============ 3. 跑两个阈值 ============
# 阈值配置
thresholds = {
    '10_8': (0.10, 0.08),  # 新测试
    '5_4':  (0.05, 0.04),  # V14最佳，对照
}

results = {}
for pname, (stocks, sd) in periods_config.items():
    df, all_ids = build_period_data(stocks, BOND, sd, last_date)
    print(f"{pname}: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)}天, {len(stocks)}股+债")

    # V8基线
    pos_v8 = df['raw_position'].values
    m_v8 = compute_metrics(df, pos_v8, all_ids, BOND)

    bh = {i: float(df[f'bh_{i}'].iloc[-1] - 1) for i in all_ids}

    period_res = {'n_days': len(df), 'start': df['date'].iloc[0].strftime('%Y-%m-%d'),
                  'end': df['date'].iloc[-1].strftime('%Y-%m-%d'),
                  'stock_names': [names[i] for i in stocks], 'v8': m_v8, 'bh': bh}

    for tname, (trig, rel) in thresholds.items():
        pos, cb_events = apply_circuit_breaker(df, trig, rel, BOND)
        m = compute_metrics(df, pos, all_ids, BOND)

        # 持仓占比
        n = len(df)
        hold = {}
        for a in all_ids + [0]:
            cnt = int(np.sum(pos == a))
            if cnt > 0:
                hold[names.get(a,'空仓')] = {'days': cnt, 'pct': round(cnt/n*100, 2)}

        period_res[tname] = m
        period_res[f'hold_{tname}'] = hold
        period_res[f'cb_count_{tname}'] = len(cb_events)
        print(f"  {tname} ({trig*100:.0f}%/{rel*100:.0f}%): 总收益{m['total']*100:.2f}%, 年化{m['ann']*100:.2f}%, 回撤{m['mdd']*100:.2f}%, 夏普{m['sharpe']:.2f}, 熔断{m['cb_pct']*100:.1f}%, 切换{m['switches']}次")

    results[pname] = period_res

# ============ 4. 打印对比 ============
print("\n" + "=" * 130)
print(f"10%/8% vs 5%/4% vs V8基线 多时段对比")
print("=" * 130)
print(f"{'时段':>6s} | {'策略':>12s} | {'总收益':>12s} | {'年化':>10s} | {'最大回撤':>10s} | {'夏普':>6s} | {'切换次':>6s} | {'熔断天%':>8s} | {'手续费':>8s}")
print("-" * 130)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    for label, key in [('10%/8%(新)', '10_8'), ('5%/4%(V14)', '5_4'), ('V8基线', 'v8')]:
        m = r[key]
        print(f"{pname:>6s} | {label:>12s} | {m['total']*100:>11.2f}% | {m['ann']*100:>9.2f}% | {m['mdd']*100:>9.2f}% | {m['sharpe']:>6.2f} | {m['switches']:>6d} | {m['cb_pct']*100:>7.1f}% | {m['total_fee']*100:>7.2f}%")
    print()

# 10%/8% vs 5%/4% 提升幅度
print("=" * 130)
print("10%/8% 相比 5%/4% 的变化")
print("=" * 130)
print(f"{'时段':>6s} | {'10/8总收益':>12s} | {'5/4总收益':>12s} | {'收益差':>12s} | {'10/8年化':>10s} | {'5/4年化':>10s} | {'年化差':>10s} | {'10/8回撤':>10s} | {'5/4回撤':>10s}")
print("-" * 130)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    m108, m54 = r['10_8'], r['5_4']
    print(f"{pname:>6s} | {m108['total']*100:>11.2f}% | {m54['total']*100:>11.2f}% | {(m108['total']-m54['total'])*100:>+11.2f}% | {m108['ann']*100:>9.2f}% | {m54['ann']*100:>9.2f}% | {(m108['ann']-m54['ann'])*100:>+9.2f}% | {m108['mdd']*100:>9.2f}% | {m54['mdd']*100:>9.2f}%")

# 持仓占比对比
print("\n" + "=" * 130)
print("10%/8% 持仓占比")
print("=" * 130)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    print(f"\n{pname}:")
    hold = r['hold_10_8']
    for name, d in sorted(hold.items(), key=lambda x: -x[1]['pct']):
        print(f"  {name:12s}: {d['days']:>5d}天 ({d['pct']:>5.1f}%)")

# ============ 5. 导出JSON ============
def clean(o):
    if isinstance(o, (np.floating, np.integer)): return float(o)
    if isinstance(o, np.ndarray): return o.tolist()
    return o

output = {
    'config': {'fee': FEE},
    'thresholds': {'10_8': {'trigger': 0.10, 'release': 0.08},
                   '5_4': {'trigger': 0.05, 'release': 0.04}},
    'names': names, 'bond_id': BOND,
    'results': {k: {
        'n_days': v['n_days'], 'start': v['start'], 'end': v['end'],
        'stock_names': v['stock_names'],
        'v8': {kk: clean(vv) for kk, vv in v['v8'].items()},
        'bh': v['bh'],
        '10_8': {kk: clean(vv) for kk, vv in v['10_8'].items()},
        '5_4': {kk: clean(vv) for kk, vv in v['5_4'].items()},
        'hold_10_8': v['hold_10_8'],
        'hold_5_4': v['hold_5_4'],
        'cb_count_10_8': v['cb_count_10_8'],
        'cb_count_5_4': v['cb_count_5_4'],
    } for k, v in results.items()},
}

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/threshold_10_8_vs_5_4.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)
print("\n数据已导出到 threshold_10_8_vs_5_4.json")
