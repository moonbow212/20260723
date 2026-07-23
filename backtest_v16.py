# -*- coding: utf-8 -*-
"""
MA20轮动策略 V16 —— V14(5%/4%阈值) + 中证2000 多时段回测

在 V14 基础上加入中证2000指数（小盘股，比中证1000更小盘）。
中证2000从2013-12-31起，近20年(2006-07起)前7年缺失 → left join，缺失日bf=NaN不参与选股。
近10/5/3/1年中证2000全程可用 → inner join。

时段标的配置：
  - 近20年: 上证50、纳指100、沪深300、中证1000 + 中证2000(2014起) + 国债
  - 近10年: 上证50、创业板50、纳指100、沪深300、中证500、中证1000、标普500、中证2000 + 国债 (8股+债)
  - 近5/3/1年: 上述8股 + 科创50 + 中证2000 + 国债 (9股+债)
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

files = {
    1: find_file('上证50'),
    2: find_file('创业板50'),
    3: find_file('纳斯达克100'),
    4: find_file('沪深300'),
    5: find_file('中证500'),
    6: find_file('中证1000'),
    7: find_file('标普500'),
    8: find_file('科创50'),
    9: find_file('国债'),
    13: find_file('中证2000'),
}
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',
         7:'标普500',8:'科创50',9:'国债',13:'中证2000'}

dfs = {}
for i, path in files.items():
    d = pd.read_csv(path, sep='\t', encoding='gbk')
    d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
    d = d[['date','开盘','收盘']].rename(columns={'开盘':f'open_{i}','收盘':f'close_{i}'})
    for c in [f'open_{i}',f'close_{i}']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    dfs[i] = d.dropna()

# 固定last_date为2026-07-17，与V14严格可比
last_date = pd.Timestamp('2026-07-17')
print(f"数据截止日期(固定): {last_date.date()}")

# ============ 2. 时段配置 ============
# 中证2000(13): 近20年用left join(2013年底起)，近10/5/3/1年全程可用
STOCK_20Y = [1, 3, 4, 6]                 # 近20年全程可用股票
PARTIAL_20Y = [13]                       # 近20年部分时段可用(中证2000)
STOCK_10Y = [1, 2, 3, 4, 5, 6, 7, 13]    # 近10年: 8股(含中证2000)
STOCK_RECENT = [1, 2, 3, 4, 5, 6, 7, 8, 13]  # 近5/3/1年: 9股(含中证2000)
BOND = 9

periods_config = {
    '近20年': {'full': STOCK_20Y, 'partial': PARTIAL_20Y, 'start': last_date - pd.DateOffset(years=20)},
    '近10年': {'full': STOCK_10Y, 'partial': [], 'start': last_date - pd.DateOffset(years=10)},
    '近5年':  {'full': STOCK_RECENT, 'partial': [], 'start': last_date - pd.DateOffset(years=5)},
    '近3年':  {'full': STOCK_RECENT, 'partial': [], 'start': last_date - pd.DateOffset(years=3)},
    '近1年':  {'full': STOCK_RECENT, 'partial': [], 'start': last_date - pd.DateOffset(years=1)},
}

# ============ 3. 构建时段基础数据 ============
def build_period_data(full_ids, partial_ids, bond_id, start_date, end_date):
    """full_ids: 全程可用标的(inner join); partial_ids: 部分时段标的(left join, 缺失日NaN)"""
    all_stock_ids = full_ids + partial_ids
    all_ids = all_stock_ids + [bond_id]

    # 全程标的 inner join
    df = reduce(lambda a,b: pd.merge(a,b,on='date',how='inner'), [dfs[i] for i in full_ids + [bond_id]])
    # 部分标的 left join
    for i in partial_ids:
        df = pd.merge(df, dfs[i], on='date', how='left')
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)

    for i in all_stock_ids:
        df[f'ma20_{i}'] = df[f'close_{i}'].rolling(20).mean()
        df[f'bf_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}'] - 1
        df[f'ratio_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}']
    # 只要求全程标的的ma20有效
    df = df.dropna(subset=[f'ma20_{i}' for i in full_ids]).reset_index(drop=True)

    def get_signal(row):
        # 收集有效(非NaN)的标的
        valid = [(i, row[f'ratio_{i}'], row[f'bf_{i}']) for i in all_stock_ids if pd.notna(row[f'ratio_{i}'])]
        if not valid:
            return bond_id
        if all(r < 1 for _, r, _ in valid):
            return bond_id
        bfs = {i: bf for i, _, bf in valid}
        return max(bfs, key=bfs.get)
    df['raw_signal'] = df.apply(get_signal, axis=1)

    # 计算各标的收益（T日open→T+1日open）
    for i in all_ids:
        df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
    last_idx = df.index[-1]
    for i in all_ids:
        df[f'ret_{i}'] = np.nan
        mask = df[f'open_{i}_next'].notna()
        df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
        # 最后一日用close/open
        if pd.notna(df.loc[last_idx, f'open_{i}']) and pd.notna(df.loc[last_idx, f'close_{i}']):
            df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

    df['raw_position'] = df['raw_signal'].shift(1)
    df.loc[df.index[0], 'raw_position'] = 0
    df['raw_prev_position'] = df['raw_position'].shift(1)
    df.loc[df.index[0], 'raw_prev_position'] = df.loc[df.index[0], 'raw_position']

    def get_raw_strat_ret(row):
        pos = int(row['raw_position'])
        if pos in all_ids and pd.notna(row[f'ret_{pos}']):
            gross = row[f'ret_{pos}']
        else:
            gross = 0.0
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

    return df, all_ids, all_stock_ids

print("\n构建基础数据...")
period_data = {}
for pname, cfg in periods_config.items():
    df, all_ids, all_stock_ids = build_period_data(cfg['full'], cfg['partial'], BOND, cfg['start'], last_date)
    period_data[pname] = {'df': df, 'all_ids': all_ids, 'stock_ids': all_stock_ids}
    stock_desc = [names[i] for i in cfg['full']]
    if cfg['partial']:
        stock_desc += [f'{names[i]}(部分)' for i in cfg['partial']]
    print(f"  {pname}: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)}天, 股票={stock_desc}")

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
        if p in all_ids and pd.notna(df[f'ret_{p}'].iloc[i]):
            gross = df[f'ret_{p}'].iloc[i]
        else:
            gross = 0.0
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
    for i in all_ids:
        days = int(np.sum(pos == i))
        if days > 0:
            holding[int(i)] = {'days': days, 'pct': round(days/n*100, 2)}

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

# ============ 5. 跑V16 + V8基线 + 买入持有 ============
results = {}
for pname, pdat in period_data.items():
    df = pdat['df']
    all_ids = pdat['all_ids']
    stock_ids = pdat['stock_ids']
    bond_id = BOND
    n = len(df)

    # V16 (5%/4% + 中证2000)
    pos_v16, cb_events = apply_circuit_breaker(df, all_ids, bond_id, DD_TRIGGER, DD_RELEASE)
    m_v16 = compute_metrics(df, all_ids, bond_id, pos_v16, cb_events)

    # V8基线(含中证2000)
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
        'v16': m_v16,
        'v8': m_v8,
        'bh': bh,
    }

# ============ 6. 读取V14结果做对比 ============
v14_path = 'C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_periods_data.json'
v14_data = None
if os.path.exists(v14_path):
    with open(v14_path, 'r', encoding='utf-8') as f:
        v14_data = json.load(f)
    print("\n已加载V14数据用于对比")
else:
    print("\n警告: 未找到V14数据，将只输出V16结果")

# ============ 7. 打印结果 ============
print("\n" + "=" * 120)
print(f"MA20轮动策略 V16 (V14 5%/4% + 中证2000) —— 多时段收益对比")
print("=" * 120)

print(f"\n{'时段':>6s} | {'起止':>24s} | {'天数':>5s} | {'标的池'}")
print("-" * 120)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    print(f"{pname:>6s} | {r['start']}~{r['end']} | {r['n_days']:>5d} | {len(r['stock_ids'])}股+国债 ({'+'.join(r['stock_names'])})")

print("\n" + "=" * 120)
print(f"{'时段':>6s} | {'策略':>12s} | {'总收益':>10s} | {'年化':>8s} | {'最大回撤':>9s} | {'夏普':>6s} | {'切换次':>6s} | {'熔断天%':>8s} | {'手续费':>7s}")
print("-" * 120)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    for label, m in [('V16(+中证2000)', r['v16']), ('V8基线', r['v8'])]:
        print(f"{pname:>6s} | {label:>12s} | {m['total']*100:>9.2f}% | {m['ann']*100:>7.2f}% | {m['mdd']*100:>8.2f}% | {m['sharpe']:>6.2f} | {m['switches']:>6d} | {m['cb_pct']*100:>7.1f}% | {m['total_fee']*100:>6.2f}%")
    if v14_data and pname in v14_data['results']:
        m14 = v14_data['results'][pname]['v14']
        print(f"{pname:>6s} | {'V14(对比)':>12s} | {m14['total']*100:>9.2f}% | {m14['ann']*100:>7.2f}% | {m14['mdd']*100:>8.2f}% | {m14['sharpe']:>6.2f} | {m14['switches']:>6d} | {m14['cb_pct']*100:>7.1f}% | {m14['total_fee']*100:>6.2f}%")
    print()

# 中证2000持仓占比
print("=" * 120)
print("中证2000在各时段的持仓占比")
print("=" * 120)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    h = r['v16']['holding']
    if 13 in h:
        print(f"  {pname}: V16持中证2000 {h[13]['pct']:.2f}% ({h[13]['days']}天)")
    else:
        print(f"  {pname}: V16未持有中证2000")

# ============ 8. 导出JSON ============
def clean(o):
    if isinstance(o, (np.floating, np.integer)): return float(o)
    if isinstance(o, np.ndarray): return o.tolist()
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(x) for x in o]
    return o

output = {
    'config': {
        'dd_trigger': DD_TRIGGER,
        'dd_release': DD_RELEASE,
        'fee': FEE,
        'desc': 'V14(5%/4%) + 中证2000',
    },
    'names': {str(k): v for k, v in names.items()},
    'bond_id': BOND,
    'results': {k: {
        'n_days': v['n_days'],
        'start': v['start'],
        'end': v['end'],
        'stock_ids': v['stock_ids'],
        'stock_names': v['stock_names'],
        'v16': clean(v['v16']),
        'v8': clean(v['v8']),
        'bh': v['bh'],
    } for k, v in results.items()},
    'v14': v14_data['results'] if v14_data else None,
}

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v16_periods_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)
print("\n数据已导出到 v16_periods_data.json")
