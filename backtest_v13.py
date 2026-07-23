# -*- coding: utf-8 -*-
"""
MA20轮动策略回测 V13 —— V8基础 + 回撤熔断机制
策略规则：
  1. 原始信号 = V8的MA20轮动（bf最高买/全负买国债）
  2. 熔断机制：策略净值从cummax回撤 > 10% → 强制转国债
  3. 熔断解除：净值回到cummax的95%以上（回撤缩小到5%以内）
  4. 次日开盘价执行 | 每次买卖收万分之二手续费
  5. 熔断切换也按正常手续费收

分段：
  近10年：上证50/创业板50/纳斯达克100/沪深300/中证500/中证1000/标普500 (7股票) + 国债
  近5/3/1年：上述7个 + 科创50 (8股票) + 国债
"""

import pandas as pd
import numpy as np
import json
from functools import reduce

FEE = 0.0002
DD_TRIGGER = 0.10   # 回撤>10%触发熔断
DD_RELEASE = 0.05   # 回撤<5%解除熔断

# ============ 1. 读取数据 ============
# 优先用同花顺格式（包含"开盘/收盘"列），找不到则用桌面文件
import os
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

# ============ 2. 回测函数（含熔断）============
def run_backtest_with_circuit_breaker(stock_ids, bond_id, start_date, end_date, label):
    all_ids = stock_ids + [bond_id]
    df = reduce(lambda a,b: pd.merge(a,b,on='date',how='inner'), [dfs[i] for i in all_ids])
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)
    if len(df) < 25:
        print(f"  {label}: 数据不足({len(df)}天)，跳过")
        return None

    print(f"  {label}: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)}天, 股票{len(stock_ids)}+国债")

    # MA20和买入因子
    for i in stock_ids:
        df[f'ma20_{i}'] = df[f'close_{i}'].rolling(20).mean()
        df[f'bf_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}'] - 1
        df[f'ratio_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}']
    df = df.dropna(subset=[f'ma20_{i}' for i in stock_ids]).reset_index(drop=True)

    # 原始信号（V8逻辑）
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

    # ========== 关键：带熔断的position计算 ==========
    # 由于熔断逻辑需要"已发生"的回撤信息，而回撤依赖position计算的结果
    # 这里采用迭代方式：先按raw_signal算一遍得到strat_nav，再应用熔断重新算
    # 简化方案：先按raw_signal算一次得原始strat_nav_v8，再按熔断规则覆写position
    df['raw_position'] = df['raw_signal'].shift(1)
    df.loc[df.index[0], 'raw_position'] = 0

    # 原始策略净值
    def get_raw_strat_ret(row):
        pos = int(row['raw_position'])
        gross = row[f'ret_{pos}'] if pos in all_ids else 0.0
        cost = 0.0
        prev = row.get('raw_prev_position', pos)
        if prev != pos:
            if prev in all_ids: cost += FEE
            if pos in all_ids: cost += FEE
        return (1 + gross) * (1 - cost) - 1
    df['raw_prev_position'] = df['raw_position'].shift(1)
    df.loc[df.index[0], 'raw_prev_position'] = df.loc[df.index[0], 'raw_position']
    df['raw_strat_ret'] = df.apply(get_raw_strat_ret, axis=1)
    df['raw_strat_nav'] = (1 + df['raw_strat_ret']).cumprod()

    # 应用熔断：跟踪raw_strat_nav的cummax和回撤
    df['raw_cummax'] = df['raw_strat_nav'].cummax()
    df['raw_dd'] = df['raw_strat_nav'] / df['raw_cummax'] - 1

    # 熔断状态机
    in_cb = False  # 是否处于熔断状态
    final_position = []  # 最终持仓序列
    cb_log = []  # 熔断事件日志

    for idx, row in df.iterrows():
        sig = int(row['raw_position'])
        dd = row['raw_dd']
        if not in_cb:
            # 未熔断
            if dd < -DD_TRIGGER and sig != bond_id:
                # 触发熔断：强制转国债
                in_cb = True
                cb_log.append({'date': row['date'].strftime('%Y-%m-%d'),
                              'event':'TRIGGER', 'dd': dd, 'raw_signal': sig, 'forced': bond_id})
                final_position.append(bond_id)
            else:
                final_position.append(sig)
        else:
            # 已熔断
            if dd > -DD_RELEASE:
                # 解除熔断：回到raw_signal
                in_cb = False
                cb_log.append({'date': row['date'].strftime('%Y-%m-%d'),
                              'event':'RELEASE', 'dd': dd, 'from': bond_id, 'to': sig})
                final_position.append(sig)
            else:
                final_position.append(bond_id)

    df['position'] = final_position

    # 手续费
    df['prev_position'] = df['position'].shift(1)
    df.loc[df.index[0], 'prev_position'] = df.loc[df.index[0], 'position']
    def calc_cost(row):
        old, new = int(row['prev_position']), int(row['position'])
        if old == new:
            return 0.0
        cost = 0.0
        if old in all_ids: cost += FEE
        if new in all_ids: cost += FEE
        return cost
    df['trade_cost'] = df.apply(calc_cost, axis=1)

    # 策略收益
    def get_strat_ret(row):
        pos = int(row['position'])
        gross = row[f'ret_{pos}'] if pos in all_ids else 0.0
        return (1 + gross) * (1 - row['trade_cost']) - 1
    df['strat_ret'] = df.apply(get_strat_ret, axis=1)
    df['strat_nav'] = (1 + df['strat_ret']).cumprod()

    # 买入持有净值
    for i in all_ids:
        df[f'bh_{i}_nav'] = (1 + df[f'ret_{i}']).cumprod()

    # 指标
    def mdd(s):
        s = s.dropna()
        if len(s)==0: return 0
        return ((s - s.cummax())/s.cummax()).min()
    def ann(r, d):
        if d<=0 or r<=-1: return 0
        return (1+r)**(252/d)-1
    def sharpe(r, d):
        s = r.std()
        if s==0 or d==0: return 0
        return np.sqrt(252)*r.mean()/s

    n = len(df)
    strat_total = df['strat_nav'].iloc[-1]-1
    bh_totals = {i: df[f'bh_{i}_nav'].iloc[-1]-1 for i in all_ids}
    pos = df['position'].values
    switches = int(np.sum(np.diff(pos)!=0))
    hold = {i: int(np.sum(pos==i)) for i in all_ids}
    cash_days = int(np.sum(pos==0))
    cb_days = int(np.sum(np.array(final_position)==bond_id))
    bond_hold = hold[bond_id]
    cb_pct = cb_days/n

    r = {
        'start_date': df['date'].iloc[0].strftime('%Y-%m-%d'),
        'end_date': df['date'].iloc[-1].strftime('%Y-%m-%d'),
        'n_days': n,
        'stock_ids': stock_ids,
        'strat_total': strat_total,
        'strat_ann': ann(strat_total, n),
        'strat_mdd': mdd(df['strat_nav']),
        'strat_sharpe': sharpe(df['strat_ret'], n),
        'raw_total': df['raw_strat_nav'].iloc[-1]-1,
        'raw_mdd': mdd(df['raw_strat_nav']),
        'switches': switches,
        'total_fee': float(df['trade_cost'].sum()),
        'cb_days': cb_days,
        'cb_pct': cb_pct,
        'cb_events': cb_log,
        'nav_dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
        'strat_nav': [round(x,4) for x in df['strat_nav'].tolist()],
        'raw_strat_nav': [round(x,4) for x in df['raw_strat_nav'].tolist()],
        'raw_dd': [round(x,4) for x in df['raw_dd'].tolist()],
        'position_seq': [int(p) for p in pos],
    }
    for i in all_ids:
        r[f'bh{i}_total'] = bh_totals[i]
        r[f'bh{i}_ann'] = ann(bh_totals[i], n)
        r[f'bh{i}_mdd'] = mdd(df[f'bh_{i}_nav'])
        r[f'bh{i}_sharpe'] = sharpe(df[f'ret_{i}'], n)
        r[f'bh{i}_nav'] = [round(x,4) for x in df[f'bh_{i}_nav'].tolist()]
        r[f'hold{i}_pct'] = hold[i]/n
    r['cash_pct'] = cash_days/n
    return r

# ============ 3. 分段回测 ============
last_date = dfs[9]['date'].max()
print(f"数据最新日期: {last_date.date()}\n")

STOCK_10Y = [1,2,3,4,5,6,7]
STOCK_RECENT = [1,2,3,4,5,6,7,8]
BOND = 9

periods_config = {
    '近10年': (STOCK_10Y, last_date - pd.DateOffset(years=10)),
    '近5年': (STOCK_RECENT, last_date - pd.DateOffset(years=5)),
    '近3年': (STOCK_RECENT, last_date - pd.DateOffset(years=3)),
    '近1年': (STOCK_RECENT, last_date - pd.DateOffset(years=1)),
}

results = {}
for name, (stocks, sd) in periods_config.items():
    print(f"=== {name} ===")
    r = run_backtest_with_circuit_breaker(stocks, BOND, sd, last_date, name)
    results[name] = r
    print()

# ============ 4. 打印结果 ============
print("="*100)
print(f"MA20轮动策略 V13 回测结果（V8+回撤熔断：>10%熔断转国债，<5%解除）")
print("="*100)

for name in ['近10年','近5年','近3年','近1年']:
    r = results[name]
    if r is None: continue
    stocks = r['stock_ids']
    all_ids = stocks + [BOND]
    print(f"\n{'─'*95}")
    print(f"  {name} ({r['start_date']}~{r['end_date']}, {r['n_days']}天) 参与股票: {','.join(names[i] for i in stocks)}")
    print(f"{'─'*95}")
    print(f"  策略:  总收益{r['strat_total']:>9.2%} | 年化{r['strat_ann']:>8.2%} | 回撤{r['strat_mdd']:>8.2%} | 夏普{r['strat_sharpe']:>6.2f}")
    print(f"  V8原:  总收益{r['raw_total']:>9.2%} | 年化{(1+r['raw_total'])**(252/r['n_days'])-1:>8.2%} | 回撤{r['raw_mdd']:>8.2%}")
    print(f"  熔断天数: {r['cb_days']}天 ({r['cb_pct']:.1%}) | 切换{r['switches']}次 | 手续费{r['total_fee']:.2%}")
    print(f"  熔断事件数: {len(r['cb_events'])}")
    for ev in r['cb_events'][:5]:
        print(f"    {ev['date']} {ev['event']:7s} dd={ev['dd']:>7.2%}")

# ============ 5. 导出 ============
def clean(o):
    if isinstance(o, (np.floating, np.integer)): return float(o)
    return o

output = {
    'results': {k: {kk: clean(vv) for kk,vv in v.items()} for k,v in results.items() if v},
    'names': names,
    'dd_trigger': DD_TRIGGER,
    'dd_release': DD_RELEASE,
}
with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v13_data.json','w',encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)
print("\n数据已导出到 backtest_v13_data.json")
