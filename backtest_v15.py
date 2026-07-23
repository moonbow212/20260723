# -*- coding: utf-8 -*-
"""
MA20轮动策略 V15 —— 加入3个海外指数 (日经225/越南胡志明/英国富时100)
在V14(5%/4%阈值)基础上扩展候选池：
  原标的: 上证50/创业板50/纳指100/沪深300/中证500/中证1000/标普500/科创50 + 国债
  新增:   日经225(ID=10) / 越南胡志明(ID=11) / 英国富时100(ID=12)

海外指数交易日历与A股不同，处理方式：
  - 每个海外指数独立按自己日历算MA20/bf
  - left join到原inner join的主表，缺失日bf=NaN不参与选股
  - 收益按主日历算 open.shift(-1)/open-1，缺失日ret=0
  - 富时100只到2026-04-17，之后自动排除
"""

import pandas as pd
import numpy as np
import json
import os
from functools import reduce

FEE = 0.0002
DD_TRIGGER = 0.05
DD_RELEASE = 0.04

# ============ 1. 读取原9个标的数据 (同V14) ============
def find_file(name):
    for p in [f'C:/Users/wbl/Desktop/同花顺历史数据/{name}.xlsx',
              f'C:/Users/wbl/Desktop/{name}.xlsx']:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"未找到 {name}.xlsx")

orig_files = {
    1: find_file('上证50'), 2: find_file('创业板50'), 3: find_file('纳斯达克100'),
    4: find_file('沪深300'), 5: find_file('中证500'), 6: find_file('中证1000'),
    7: find_file('标普500'), 8: find_file('科创50'), 9: find_file('国债'),
}
names = {0:'空仓',1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',
         7:'标普500',8:'科创50',9:'国债',10:'日经225',11:'越南胡志明',12:'英国富时100'}

dfs = {}
for i, path in orig_files.items():
    d = pd.read_csv(path, sep='\t', encoding='gbk')
    d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
    d = d[['date','开盘','收盘']].rename(columns={'开盘':f'open_{i}','收盘':f'close_{i}'})
    for c in [f'open_{i}',f'close_{i}']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    dfs[i] = d.dropna()

# ============ 2. 读取3个新海外指数 (UTF-8 CSV, 价格含千分位逗号) ============
overseas_files = {
    10: 'C:/Users/wbl/Desktop/日经225指数历史数据 (4).csv',
    11: 'C:/Users/wbl/Desktop/越南胡志明指数历史数据.csv',
    12: 'C:/Users/wbl/Desktop/英国富时100指数历史数据.csv',
}

for i, path in overseas_files.items():
    d = pd.read_csv(path, encoding='utf-8')
    d['date'] = pd.to_datetime(d['日期'])
    # 清洗千分位逗号
    for c in ['收盘','开盘']:
        d[c] = d[c].astype(str).str.replace(',','')
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d[['date','开盘','收盘']].rename(columns={'开盘':f'open_{i}','收盘':f'close_{i}'})
    d = d.dropna().sort_values('date').reset_index(drop=True)
    # 按自己日历算MA20/bf
    d[f'ma20_{i}'] = d[f'close_{i}'].rolling(20).mean()
    d[f'bf_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}'] - 1
    d[f'ratio_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}']
    dfs[i] = d.dropna(subset=[f'ma20_{i}']).reset_index(drop=True)
    print(f"  {names[i]}: {d['date'].min().date()} ~ {d['date'].max().date()}, {len(d)}行")

# 固定last_date为2026-07-17, 保证与V14严格可比(原国债数据最新日)
last_date = pd.Timestamp('2026-07-17')
print(f"主日历最新日期(固定): {last_date.date()}")

# ============ 3. 时段配置 ============
STOCK_20Y_ORIG = [1, 3, 4, 6]
STOCK_10Y_ORIG = [1, 2, 3, 4, 5, 6, 7]
STOCK_RECENT_ORIG = [1, 2, 3, 4, 5, 6, 7, 8]
OVERSEAS = [10, 11, 12]
BOND = 9

# V15: 原标的 + 海外3指数
STOCK_20Y_V15 = STOCK_20Y_ORIG + OVERSEAS
STOCK_10Y_V15 = STOCK_10Y_ORIG + OVERSEAS
STOCK_RECENT_V15 = STOCK_RECENT_ORIG + OVERSEAS

# V14: 仅原标的 (用于对比)
periods_config = {
    '近20年': (STOCK_20Y_V15, STOCK_20Y_ORIG, last_date - pd.DateOffset(years=20)),
    '近10年': (STOCK_10Y_V15, STOCK_10Y_ORIG, last_date - pd.DateOffset(years=10)),
    '近5年':  (STOCK_RECENT_V15, STOCK_RECENT_ORIG, last_date - pd.DateOffset(years=5)),
    '近3年':  (STOCK_RECENT_V15, STOCK_RECENT_ORIG, last_date - pd.DateOffset(years=3)),
    '近1年':  (STOCK_RECENT_V15, STOCK_RECENT_ORIG, last_date - pd.DateOffset(years=1)),
}

# ============ 4. 构建时段基础数据 ============
def build_period_data(stock_ids_v15, stock_ids_v14, bond_id, start_date, end_date):
    """构建V15数据：原标的inner join + 海外指数left join"""
    overseas_ids = [i for i in stock_ids_v15 if i not in stock_ids_v14]
    orig_ids = stock_ids_v14 + [bond_id]

    # 原标的inner join (同V14)
    df = reduce(lambda a,b: pd.merge(a,b,on='date',how='inner'), [dfs[i] for i in orig_ids])
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)

    # 原标的算ma20/bf (同V14, 按主日历)
    for i in stock_ids_v14:
        df[f'ma20_{i}'] = df[f'close_{i}'].rolling(20).mean()
        df[f'bf_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}'] - 1
        df[f'ratio_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}']
    df = df.dropna(subset=[f'ma20_{i}' for i in stock_ids_v14]).reset_index(drop=True)

    # 海外指数left join (按自己日历已算好ma20/bf)
    for i in overseas_ids:
        sub = dfs[i][['date', f'open_{i}', f'close_{i}', f'ma20_{i}', f'bf_{i}', f'ratio_{i}']].copy()
        df = pd.merge(df, sub, on='date', how='left')

    all_ids_v15 = stock_ids_v15 + [bond_id]

    # 选股: V15 (含海外, NaN跳过) 和 V14 (仅原标的)
    def get_signal_v15(row):
        bfs = {}
        for i in stock_ids_v15:
            v = row.get(f'bf_{i}', np.nan)
            if pd.notna(v):
                bfs[i] = v
        if len(bfs) == 0:
            return bond_id
        if all(v < 0 for v in bfs.values()):
            return bond_id
        return max(bfs, key=bfs.get)

    def get_signal_v14(row):
        ratios = [row[f'ratio_{i}'] for i in stock_ids_v14]
        if all(r < 1 for r in ratios):
            return bond_id
        bfs = {i: row[f'bf_{i}'] for i in stock_ids_v14}
        return max(bfs, key=bfs.get)

    df['signal_v15'] = df.apply(get_signal_v15, axis=1)
    df['signal_v14'] = df.apply(get_signal_v14, axis=1)

    # 收益: 所有标的按主日历算 open.shift(-1)/open-1
    for i in all_ids_v15:
        df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
    last_idx = df.index[-1]
    for i in all_ids_v15:
        df[f'ret_{i}'] = np.nan
        mask = df[f'open_{i}_next'].notna() & df[f'open_{i}'].notna()
        df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
        # 最后一行用close/open
        if pd.notna(df.loc[last_idx, f'open_{i}']) and pd.notna(df.loc[last_idx, f'close_{i}']):
            df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1
        # 海外指数缺失日ret=0
        df[f'ret_{i}'] = df[f'ret_{i}'].fillna(0)

    # V15持仓
    df['pos_v15'] = df['signal_v15'].shift(1)
    df.loc[df.index[0], 'pos_v15'] = 0
    df['prev_pos_v15'] = df['pos_v15'].shift(1)
    df.loc[df.index[0], 'prev_pos_v15'] = df.loc[df.index[0], 'pos_v15']

    # V14持仓
    df['pos_v14'] = df['signal_v14'].shift(1)
    df.loc[df.index[0], 'pos_v14'] = 0
    df['prev_pos_v14'] = df['pos_v14'].shift(1)
    df.loc[df.index[0], 'prev_pos_v14'] = df.loc[df.index[0], 'pos_v14']

    def get_ret(row, pos_col, prev_col, ids):
        pos = int(row[pos_col])
        gross = row[f'ret_{pos}'] if pos in ids else 0.0
        prev = int(row[prev_col])
        cost = 0.0
        if prev != pos:
            if prev in ids: cost += FEE
            if pos in ids: cost += FEE
        return (1 + gross) * (1 - cost) - 1

    df['ret_v15'] = df.apply(get_ret, axis=1, args=('pos_v15','prev_pos_v15',all_ids_v15))
    df['ret_v14'] = df.apply(get_ret, axis=1, args=('pos_v14','prev_pos_v14',all_ids_v15))
    df['nav_v15'] = (1 + df['ret_v15']).cumprod()
    df['nav_v14'] = (1 + df['ret_v14']).cumprod()

    # V8基线(=V14原始信号)的cummax和回撤 (用于熔断判断)
    df['cummax_v8'] = df['nav_v14'].cummax()
    df['dd_v8'] = df['nav_v14'] / df['cummax_v8'] - 1

    # 买入持有
    for i in all_ids_v15:
        df[f'bh_{i}'] = (1 + df[f'ret_{i}']).cumprod()

    return df, all_ids_v15, stock_ids_v15

print("\n构建基础数据...")
period_data = {}
for pname, (stocks_v15, stocks_v14, sd) in periods_config.items():
    df, all_ids, stocks_v15 = build_period_data(stocks_v15, stocks_v14, BOND, sd, last_date)
    period_data[pname] = {'df': df, 'all_ids': all_ids, 'stock_ids_v15': stocks_v15, 'stock_ids_v14': stocks_v14}
    print(f"  {pname}: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)}天, V15={len(stocks_v15)}股+债, V14={len(stocks_v14)}股+债")

# ============ 5. 应用5%/4%熔断 ============
def apply_circuit_breaker(df, nav_col, dd_col, signal_col, bond_id, dd_trigger, dd_release):
    """对给定净值序列应用熔断"""
    n = len(df)
    raw_pos = df[signal_col].shift(1).fillna(0).astype(int).values
    raw_dd = df[dd_col].values
    dates = df['date'].values

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
        'ann_vol': float(std * np.sqrt(252)), 'nav_final': float(nav[-1]),
    }

# ============ 6. 跑V15/V14/V8 ============
results = {}
for pname, pdat in period_data.items():
    df = pdat['df']
    all_ids = pdat['all_ids']
    stocks_v15 = pdat['stock_ids_v15']
    stocks_v14 = pdat['stock_ids_v14']

    # V15: 对V15净值序列应用熔断 (基于V15原始信号的净值回撤)
    # 注意: V15的熔断基准应该是V15原始信号(无熔断)的净值回撤
    # 但为保持与V14方法论一致,我们用各自原始信号的净值回撤
    df_v15_raw_nav = (1 + df['ret_v15']).cumprod()
    df['cummax_v15_raw'] = df_v15_raw_nav.cummax()
    df['dd_v15_raw'] = df_v15_raw_nav / df['cummax_v15_raw'] - 1

    pos_v15, cb_v15 = apply_circuit_breaker(df, 'nav_v15', 'dd_v15_raw', 'signal_v15', BOND, DD_TRIGGER, DD_RELEASE)
    m_v15 = compute_metrics(df, pos_v15, all_ids, BOND)

    # V14: 对V14净值序列应用熔断 (基于V14原始信号的净值回撤)
    pos_v14, cb_v14 = apply_circuit_breaker(df, 'nav_v14', 'dd_v8', 'signal_v14', BOND, DD_TRIGGER, DD_RELEASE)
    m_v14 = compute_metrics(df, pos_v14, all_ids, BOND)

    # V8基线(=V14原始信号,无熔断)
    pos_v8 = df['pos_v14'].values
    m_v8 = compute_metrics(df, pos_v8, all_ids, BOND)

    # 买入持有
    bh = {i: float(df[f'bh_{i}'].iloc[-1] - 1) for i in all_ids}

    # 持仓占比
    n = len(df)
    hold_v15 = {}
    for a in all_ids + [0]:
        cnt = int(np.sum(pos_v15 == a))
        if cnt > 0:
            hold_v15[names[a]] = {'days': cnt, 'pct': round(cnt/n*100, 2)}

    results[pname] = {
        'n_days': len(df), 'start': df['date'].iloc[0].strftime('%Y-%m-%d'),
        'end': df['date'].iloc[-1].strftime('%Y-%m-%d'),
        'stock_ids_v15': stocks_v15, 'stock_ids_v14': stocks_v14,
        'v15': m_v15, 'v14': m_v14, 'v8': m_v8, 'bh': bh,
        'hold_v15': hold_v15,
        'cb_v15_count': len(cb_v15), 'cb_v14_count': len(cb_v14),
    }

# ============ 7. 打印结果 ============
print("\n" + "=" * 120)
print(f"MA20轮动策略 V15 (加入日经225/越南胡志明/英国富时100) vs V14 vs V8 —— 5%/4%阈值多时段对比")
print("=" * 120)

print(f"\n{'时段':>6s} | {'起止':>24s} | {'天数':>5s} | {'V15标的':>8s} | {'V14标的':>8s}")
print("-" * 120)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    print(f"{pname:>6s} | {r['start']}~{r['end']} | {r['n_days']:>5d} | {len(r['stock_ids_v15'])}股+债 | {len(r['stock_ids_v14'])}股+债")

print("\n" + "=" * 120)
print(f"{'时段':>6s} | {'策略':>10s} | {'总收益':>11s} | {'年化':>9s} | {'最大回撤':>9s} | {'夏普':>6s} | {'切换次':>6s} | {'熔断天%':>8s} | {'手续费':>7s}")
print("-" * 120)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    for label, m in [('V15(新增)', r['v15']), ('V14(原)', r['v14']), ('V8基线', r['v8'])]:
        print(f"{pname:>6s} | {label:>10s} | {m['total']*100:>10.2f}% | {m['ann']*100:>8.2f}% | {m['mdd']*100:>8.2f}% | {m['sharpe']:>6.2f} | {m['switches']:>6d} | {m['cb_pct']*100:>7.1f}% | {m['total_fee']*100:>6.2f}%")
    print()

# V15 vs V14 提升幅度
print("=" * 120)
print("V15相比V14的提升")
print("=" * 120)
print(f"{'时段':>6s} | {'V15总收益':>10s} | {'V14总收益':>10s} | {'收益差':>10s} | {'V15回撤':>9s} | {'V14回撤':>9s} | {'回撤差':>9s} | {'V15夏普':>8s} | {'V14夏普':>8s}")
print("-" * 120)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    v15, v14 = r['v15'], r['v14']
    print(f"{pname:>6s} | {v15['total']*100:>9.2f}% | {v14['total']*100:>9.2f}% | {(v15['total']-v14['total'])*100:>+9.2f}% | {v15['mdd']*100:>8.2f}% | {v14['mdd']*100:>8.2f}% | {(v15['mdd']-v14['mdd'])*100:>+8.2f}% | {v15['sharpe']:>8.2f} | {v14['sharpe']:>8.2f}")

# 持仓占比
print("\n" + "=" * 120)
print("V15各标的持仓占比")
print("=" * 120)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results[pname]
    print(f"\n{pname}:")
    hold = r['hold_v15']
    for name, d in sorted(hold.items(), key=lambda x: -x[1]['pct']):
        print(f"  {name:12s}: {d['days']:>5d}天 ({d['pct']:>5.1f}%)")

# ============ 8. 导出JSON ============
def clean(o):
    if isinstance(o, (np.floating, np.integer)): return float(o)
    if isinstance(o, np.ndarray): return o.tolist()
    return o

output = {
    'config': {'dd_trigger': DD_TRIGGER, 'dd_release': DD_RELEASE, 'fee': FEE},
    'names': names, 'bond_id': BOND,
    'overseas_names': [names[i] for i in OVERSEAS],
    'results': {k: {
        'n_days': v['n_days'], 'start': v['start'], 'end': v['end'],
        'stock_ids_v15': v['stock_ids_v15'], 'stock_ids_v14': v['stock_ids_v14'],
        'v15': {kk: clean(vv) for kk, vv in v['v15'].items()},
        'v14': {kk: clean(vv) for kk, vv in v['v14'].items()},
        'v8': {kk: clean(vv) for kk, vv in v['v8'].items()},
        'bh': v['bh'], 'hold_v15': v['hold_v15'],
        'cb_v15_count': v['cb_v15_count'], 'cb_v14_count': v['cb_v14_count'],
    } for k, v in results.items()},
}

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v15_periods_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)
print("\n数据已导出到 v15_periods_data.json")
