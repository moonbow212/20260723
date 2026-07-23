# -*- coding: utf-8 -*-
"""
MA20轮动策略回测 V14 —— 熔断阈值敏感性分析
在V8基础上，测试多组 (DD_TRIGGER, DD_RELEASE) 阈值的策略效果

策略规则：
  1. 原始信号 = V8的MA20轮动（bf最高买/全负买国债）
  2. 熔断机制：策略净值从cummax回撤 > DD_TRIGGER → 强制转国债
  3. 熔断解除：净值回到cummax的(1-DD_RELEASE)以上 → 恢复raw_signal
  4. 次日开盘价执行 | 每次买卖收万分之二手续费
  5. 熔断切换也按正常手续费收

测试网格：
  - 触发阈值: 5%/6%/8%/10%/12%/15%/20%
  - 解除阈值: 2%/3%/4%/5%/7%（必须 <= 触发阈值）
  - 一次性熔断（触发后永不解除）
  - 无熔断（V8基线）
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
    1: find_file('上证50'),
    2: find_file('创业板50'),
    3: find_file('纳斯达克100'),
    4: find_file('沪深300'),
    5: find_file('中证500'),
    6: find_file('中证1000'),
    7: find_file('标普500'),
    8: find_file('科创50'),
    9: find_file('国债'),
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

# ============ 2. 计算各时段的基础数据（不含熔断）============
last_date = dfs[9]['date'].max()
print(f"数据最新日期: {last_date.date()}")

STOCK_10Y = [1,2,3,4,5,6,7]
STOCK_RECENT = [1,2,3,4,5,6,7,8]
BOND = 9

periods_config = {
    '近10年': (STOCK_10Y, last_date - pd.DateOffset(years=10)),
    '近5年': (STOCK_RECENT, last_date - pd.DateOffset(years=5)),
    '近3年': (STOCK_RECENT, last_date - pd.DateOffset(years=3)),
    '近1年': (STOCK_RECENT, last_date - pd.DateOffset(years=1)),
}

def build_period_data(stock_ids, bond_id, start_date, end_date):
    """构建某时段的合并数据 + 计算raw_nav/raw_dd/次日收益"""
    all_ids = stock_ids + [bond_id]
    df = reduce(lambda a,b: pd.merge(a,b,on='date',how='inner'), [dfs[i] for i in all_ids])
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)

    # MA20和买入因子
    for i in stock_ids:
        df[f'ma20_{i}'] = df[f'close_{i}'].rolling(20).mean()
        df[f'bf_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}'] - 1
        df[f'ratio_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}']
    df = df.dropna(subset=[f'ma20_{i}' for i in stock_ids]).reset_index(drop=True)

    # 原始信号
    def get_signal(row):
        ratios = [row[f'ratio_{i}'] for i in stock_ids]
        if all(r < 1 for r in ratios):
            return bond_id
        bfs = {i: row[f'bf_{i}'] for i in stock_ids}
        return max(bfs, key=bfs.get)
    df['raw_signal'] = df.apply(get_signal, axis=1)

    # 次日开盘收益
    for i in all_ids:
        df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
    last_idx = df.index[-1]
    for i in all_ids:
        df[f'ret_{i}'] = np.nan
        mask = df[f'open_{i}_next'].notna()
        df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
        df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

    # raw_position（次日开盘执行）
    df['raw_position'] = df['raw_signal'].shift(1)
    df.loc[df.index[0], 'raw_position'] = 0

    # raw_strat_ret / raw_strat_nav
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

    # cummax / drawdown
    df['raw_cummax'] = df['raw_strat_nav'].cummax()
    df['raw_dd'] = df['raw_strat_nav'] / df['raw_cummax'] - 1

    # 买入持有净值
    for i in all_ids:
        df[f'bh_{i}_nav'] = (1 + df[f'ret_{i}']).cumprod()

    return df, all_ids

print("\n构建基础数据...")
period_data = {}
for name, (stocks, sd) in periods_config.items():
    df, all_ids = build_period_data(stocks, BOND, sd, last_date)
    period_data[name] = {'df': df, 'all_ids': all_ids, 'stock_ids': stocks}
    print(f"  {name}: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)}天")

# ============ 3. 在raw_nav基础上应用熔断 ============
def apply_circuit_breaker(df, all_ids, bond_id, dd_trigger, dd_release=None):
    """
    应用熔断规则
    dd_trigger: 触发阈值（如0.10表示回撤-10%触发）
    dd_release: 解除阈值（如0.05表示回撤>-5%解除），None表示永不解除
    返回: position序列、strat_nav序列、cb_days、cb_events
    """
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
            if dd_release is None:
                # 永不解除
                final_position.append(bond_id)
            elif dd > -dd_release:
                in_cb = False
                cb_events.append({'date': str(dates[i])[:10], 'event':'RELEASE',
                                  'dd': float(dd), 'from': bond_id, 'to': sig})
                final_position.append(sig)
            else:
                final_position.append(bond_id)
    return np.array(final_position), cb_events

def compute_metrics(df, all_ids, bond_id, final_pos, cb_events):
    """根据position序列计算策略指标"""
    n = len(df)
    pos = final_pos
    prev_pos = np.concatenate([[pos[0]], pos[:-1]])

    # 每日收益
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

    return {
        'total': total,
        'ann': ann_ret,
        'mdd': mdd_val,
        'sharpe': sharpe,
        'switches': switches,
        'cb_days': cb_days,
        'cb_pct': cb_pct,
        'total_fee': total_fee,
        'cb_events': cb_events,
        'nav': [round(x, 4) for x in nav.tolist()],
        'position_seq': [int(p) for p in pos],
    }

# ============ 4. 定义测试网格 ============
# 触发阈值 × 解除阈值
triggers = [0.05, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
releases = [0.02, 0.03, 0.04, 0.05, 0.07]

# 一次性熔断（触发后永不解除）
oneway_triggers = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]

# 构建所有组合
combos = []
# 常规组合
for t in triggers:
    for r in releases:
        if r < t:  # 解除阈值必须小于触发阈值
            combos.append({'label': f'{t*100:.0f}%/{r*100:.0f}%', 'trigger': t, 'release': r, 'type': 'normal'})
# 一次性熔断
for t in oneway_triggers:
    combos.append({'label': f'{t*100:.0f}%/永不', 'trigger': t, 'release': None, 'type': 'oneway'})
# 基线（无熔断）
combos.append({'label': 'V8基线(无熔断)', 'trigger': None, 'release': None, 'type': 'none'})

print(f"\n共 {len(combos)} 个组合待测试")

# ============ 5. 运行所有组合 ============
def mdd(s):
    s = s.dropna()
    if len(s) == 0: return 0
    return ((s - s.cummax()) / s.cummax()).min()

results = {}
for pname, pdat in period_data.items():
    df = pdat['df']
    all_ids = pdat['all_ids']
    stock_ids = pdat['stock_ids']
    bond_id = BOND

    # raw nav
    raw_total = df['raw_strat_nav'].iloc[-1] - 1
    raw_mdd_v = mdd(df['raw_strat_nav'])
    n = len(df)
    bh_totals = {i: df[f'bh_{i}_nav'].iloc[-1] - 1 for i in all_ids}

    period_results = []
    for combo in combos:
        if combo['type'] == 'none':
            # V8基线 = raw策略
            pos_arr = df['raw_position'].values
            cb_events = []
            cb_days = 0
            cb_pct = 0
            switches = int(np.sum(np.diff(pos_arr) != 0))
            # 重新计算完整指标
            m = compute_metrics(df, all_ids, bond_id, pos_arr, [])
        else:
            pos_arr, cb_events = apply_circuit_breaker(df, all_ids, bond_id,
                                                       combo['trigger'], combo['release'])
            m = compute_metrics(df, all_ids, bond_id, pos_arr, cb_events)

        period_results.append({
            'label': combo['label'],
            'trigger': combo['trigger'],
            'release': combo['release'],
            'type': combo['type'],
            **m,
        })

    results[pname] = {
        'n_days': n,
        'stock_ids': stock_ids,
        'raw_total': raw_total,
        'raw_mdd': raw_mdd_v,
        'bh_totals': bh_totals,
        'combos': period_results,
        'nav_dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
    }

# ============ 6. 打印对比表 ============
print("\n" + "=" * 110)
print("MA20轮动 V14 —— 熔断阈值敏感性分析")
print("=" * 110)

for pname in ['近10年', '近5年', '近3年', '近1年']:
    r = results[pname]
    n = r['n_days']
    print(f"\n{'─'*105}")
    print(f"  {pname}  ({n}天, V8基线 总收益{r['raw_total']:.2%} 回撤{r['raw_mdd']:.2%})")
    print(f"{'─'*105}")
    print(f"  {'阈值':>10s} | {'总收益':>8s} | {'年化':>7s} | {'最大回撤':>8s} | {'夏普':>5s} | {'开关次':>6s} | {'熔断天%':>7s} | {'手续费':>6s} | {'事件':>4s}")
    print(f"  {'-'*10}-+-{'-'*8}-+-{'-'*7}-+-{'-'*8}-+-{'-'*5}-+-{'-'*6}-+-{'-'*7}-+-{'-'*6}-+-{'-'*4}")

    # 按总收益降序
    sorted_combos = sorted(r['combos'], key=lambda x: -x['total'])
    for c in sorted_combos:
        mdd_disp = f"{c['mdd']*100:.2f}%"
        if c['label'] == 'V8基线(无熔断)':
            label = 'V8基线'
        else:
            label = c['label']
        print(f"  {label:>10s} | {c['total']*100:>7.2f}% | {c['ann']*100:>6.2f}% | {mdd_disp:>8s} | {c['sharpe']:>5.2f} | {c['switches']:>6d} | {c['cb_pct']*100:>6.1f}% | {c['total_fee']*100:>5.2f}% | {len(c['cb_events']):>4d}")

# ============ 7. 导出 ============
def clean(o):
    if isinstance(o, (np.floating, np.integer)): return float(o)
    if isinstance(o, np.ndarray): return o.tolist()
    return o

output = {
    'results': {k: {
        'n_days': v['n_days'],
        'stock_ids': v['stock_ids'],
        'raw_total': float(v['raw_total']),
        'raw_mdd': float(v['raw_mdd']),
        'bh_totals': {str(i): float(vv) for i, vv in v['bh_totals'].items()},
        'combos': [{kk: clean(vv) for kk, vv in c.items()} for c in v['combos']],
        'nav_dates': v['nav_dates'],
    } for k, v in results.items()},
    'names': names,
    'bond_id': BOND,
}
with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v14_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)
print("\n数据已导出到 backtest_v14_data.json")
