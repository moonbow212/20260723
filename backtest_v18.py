# -*- coding: utf-8 -*-
"""
MA20轮动策略 V18 —— 14个行业/海外指数 + 国债，5%/4%阈值，多时段回测
候选池：纳斯达克100、标普500、中证酒、中证环保、中证能源、中证消费、中证医药、
        中证金融、中证信息、中证体育、中证新能、中证军工、中证传媒、中证银行 + 国债

时段标的配置：
  - 近20年: 纳斯达克100、中证酒、中证军工、中证银行 + 国债 (4股+债, 2006-07起全程可用)
  - 近10/5/3/1年: 全部14股 + 国债
"""

import pandas as pd
import numpy as np
import json
import os
from functools import reduce

FEE = 0.0002
DD_TRIGGER = 0.05
DD_RELEASE = 0.04

# ============ 1. 读取数据 ============
def find_file(name):
    for p in [f'C:/Users/wbl/Desktop/同花顺历史数据/{name}.xlsx',
              f'C:/Users/wbl/Desktop/{name}.xlsx']:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"未找到 {name}.xlsx")

# 编号: 1=纳斯达克100, 2=标普500, 3=中证酒, 4=中证环保, 5=中证能源, 6=中证消费,
#       7=中证医药, 8=中证金融, 9=中证信息, 10=中证体育, 11=中证新能, 12=中证军工,
#       13=中证传媒, 14=中证银行, 15=国债
idx_files = {
    1: '纳斯达克100',
    2: '标普500',
    3: '中证酒',
    4: '中证环保',
    5: '中证能源',
    6: '中证消费',
    7: '中证医药',
    8: '中证金融',
    9: '中证信息',
    10: '中证体育',
    11: '中证新能',
    12: '中证军工',
    13: '中证传媒',
    14: '中证银行',
    15: '国债',
}
names = {1:'纳斯达克100',2:'标普500',3:'中证酒',4:'中证环保',5:'中证能源',6:'中证消费',
         7:'中证医药',8:'中证金融',9:'中证信息',10:'中证体育',11:'中证新能',12:'中证军工',
         13:'中证传媒',14:'中证银行',15:'国债'}

files = {i: find_file(nm) for i, nm in idx_files.items()}

dfs = {}
for i, path in files.items():
    d = pd.read_csv(path, sep='\t', encoding='gbk')
    d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
    d = d[['date','开盘','收盘']].rename(columns={'开盘':f'open_{i}','收盘':f'close_{i}'})
    for c in [f'open_{i}',f'close_{i}']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    dfs[i] = d.dropna()

last_date = pd.Timestamp('2026-07-17')  # 固定截止日期，与V14严格可比
print(f"截止日期: {last_date.date()}")

# ============ 2. 时段配置 ============
# 近20年: 仅4个全程可用的指数 + 国债
STOCK_20Y = [1, 3, 12, 14]  # 纳斯达克100、中证酒、中证军工、中证银行
# 近10/5/3/1年: 全部14个指数
STOCK_FULL = [1,2,3,4,5,6,7,8,9,10,11,12,13,14]
BOND = 15

periods_config = {
    '近20年': (STOCK_20Y, last_date - pd.DateOffset(years=20)),
    '近10年': (STOCK_FULL, last_date - pd.DateOffset(years=10)),
    '近5年':  (STOCK_FULL, last_date - pd.DateOffset(years=5)),
    '近3年':  (STOCK_FULL, last_date - pd.DateOffset(years=3)),
    '近1年':  (STOCK_FULL, last_date - pd.DateOffset(years=1)),
}

# ============ 3. 构建时段基础数据 ============
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

    for i in all_ids:
        df[f'bh_{i}_nav'] = (1 + df[f'ret_{i}']).cumprod()

    return df, all_ids

print("\n构建基础数据...")
period_data = {}
for pname, (stocks, sd) in periods_config.items():
    df, all_ids = build_period_data(stocks, BOND, sd, last_date)
    period_data[pname] = {'df': df, 'all_ids': all_ids, 'stock_ids': stocks}
    print(f"  {pname}: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)}天, {len(stocks)}股+国债")

# ============ 4. 应用5%/4%熔断 ============
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
                cb_events.append({'date': str(dates[i])[:10], 'event':'TRIGGER',
                                  'dd': float(dd), 'from': sig, 'to': bond_id})
                final_position.append(bond_id)
            else:
                final_position.append(sig)
        else:
            if dd > -dd_release:
                in_cb = False
                cb_events.append({'date': str(dates[i])[:10], 'event':'RELEASE',
                                  'dd': float(dd), 'from': bond_id, 'to': sig})
                final_position.append(sig)
            else:
                final_position.append(bond_id)
    return np.array(final_position), cb_events

def compute_metrics(df, all_ids, bond_id, final_pos, cb_events):
    n = len(df)
    pos = final_pos
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
    total_fee = float(costs.sum())
    ann_vol = std * np.sqrt(252)

    # 持仓占比
    holding = {}
    for a in all_ids:
        cnt = int(np.sum(pos == a))
        if cnt > 0:
            holding[names[a]] = {'days': cnt, 'pct': round(cnt / n * 100, 2)}

    return {
        'total': float(total),
        'ann': float(ann_ret),
        'mdd': float(mdd_val),
        'sharpe': float(sharpe),
        'switches': switches,
        'cb_days': cb_days,
        'cb_pct': float(cb_pct),
        'total_fee': total_fee,
        'cb_events': cb_events,
        'ann_vol': float(ann_vol),
        'nav_final': float(nav[-1]),
        'holding': holding,
    }

# ============ 5. 跑V18(5%/4%) + V8基线 + 买入持有 ============
results = {}
for pname, pdat in period_data.items():
    df = pdat['df']
    all_ids = pdat['all_ids']
    stock_ids = pdat['stock_ids']
    bond_id = BOND
    n = len(df)

    # V18 (5%/4%)
    pos_v18, cb_events = apply_circuit_breaker(df, all_ids, bond_id, DD_TRIGGER, DD_RELEASE)
    m_v18 = compute_metrics(df, all_ids, bond_id, pos_v18, cb_events)

    # V8基线 (无熔断)
    pos_v8 = df['raw_position'].values
    m_v8 = compute_metrics(df, all_ids, bond_id, pos_v8, [])

    # 买入持有各标的
    bh = {i: float(df[f'bh_{i}_nav'].iloc[-1] - 1) for i in all_ids}

    results[pname] = {
        'n_days': n,
        'start': df['date'].iloc[0].strftime('%Y-%m-%d'),
        'end': df['date'].iloc[-1].strftime('%Y-%m-%d'),
        'stock_ids': stock_ids,
        'stock_names': [names[i] for i in stock_ids],
        'v18': m_v18,
        'v8': m_v8,
        'bh': bh,
    }

# ============ 6. 打印结果 ============
print("\n" + "=" * 120)
print(f"MA20轮动策略 V18 (14行业指数+国债, 5%/4%阈值) —— 多时段收益对比")
print("=" * 120)

print(f"\n{'时段':>6s} | {'起止':>24s} | {'天数':>5s} | {'标的':>10s}")
print("-" * 120)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    print(f"{pname:>6s} | {r['start']}~{r['end']} | {r['n_days']:>5d} | {len(r['stock_ids'])}股+国债")

print("\n" + "=" * 120)
print(f"{'时段':>6s} | {'策略':>10s} | {'总收益':>12s} | {'年化':>8s} | {'最大回撤':>9s} | {'夏普':>6s} | {'年化波动':>8s} | {'切换次':>6s} | {'熔断天%':>8s} | {'手续费':>7s} | {'事件':>4s}")
print("-" * 120)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    for label, m in [('V18(5/4)', r['v18']), ('V8基线', r['v8'])]:
        print(f"{pname:>6s} | {label:>10s} | {m['total']*100:>11.2f}% | {m['ann']*100:>7.2f}% | {m['mdd']*100:>8.2f}% | {m['sharpe']:>6.2f} | {m['ann_vol']*100:>7.2f}% | {m['switches']:>6d} | {m['cb_pct']*100:>7.1f}% | {m['total_fee']*100:>6.2f}% | {len(m['cb_events']):>4d}")
    print()

# 持仓占比
print("=" * 120)
print("V18 持仓占比")
print("=" * 120)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    print(f"\n{pname}:")
    holding = r['v18']['holding']
    for nm, info in sorted(holding.items(), key=lambda x: -x[1]['pct']):
        print(f"  {nm:12s}: {info['days']:>5d}天 ({info['pct']:>5.1f}%)")

# 买入持有对比
print("\n" + "=" * 120)
print("买入持有各标的收益对比")
print("=" * 120)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    print(f"\n{pname}:")
    for i in r['stock_ids'] + [BOND]:
        if i in r['bh']:
            print(f"  {names[i]:12s}: {r['bh'][i]*100:>10.2f}%")

# ============ 7. 导出JSON ============
def clean(o):
    if isinstance(o, (np.floating, np.integer)): return float(o)
    if isinstance(o, np.ndarray): return o.tolist()
    return o

output = {
    'config': {
        'dd_trigger': DD_TRIGGER,
        'dd_release': DD_RELEASE,
        'fee': FEE,
        'pool_desc': '14个行业/海外指数+国债',
    },
    'names': {str(k): v for k, v in names.items()},
    'bond_id': BOND,
    'results': {k: {
        'n_days': v['n_days'],
        'start': v['start'],
        'end': v['end'],
        'stock_ids': v['stock_ids'],
        'stock_names': v['stock_names'],
        'v18': {kk: clean(vv) for kk, vv in v['v18'].items()},
        'v8': {kk: clean(vv) for kk, vv in v['v8'].items()},
        'bh': {str(kk): vv for kk, vv in v['bh'].items()},
    } for k, v in results.items()},
}

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v18_periods_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)
print("\n数据已导出到 v18_periods_data.json")
