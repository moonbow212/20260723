# -*- coding: utf-8 -*-
"""
MA20轮动策略回测 V11 —— V8 + 最小持仓周期5天约束
策略规则：
  买入因子 = 当日收盘价 / 当日MA20 - 1
  - 所有参与指数 bf 都 < 0（均跌破MA20）→ 买入国债指数
  - 否则 → 持有 bf 最高的股票指数
  - 次日开盘价执行 | 每次买卖收万分之二手续费
  - 【新增】最小持仓周期5天：当前持仓不满5个交易日时，即使有更优信号也维持现状

分段：
  近10年：上证50/创业板50/纳斯达克100/沪深300/中证500/中证1000/标普500 (7股票) + 国债
  近5/3/1年：上述7个 + 科创50 (8股票) + 国债

编号：1=上证50 2=创业板50 3=纳斯达克100 4=沪深300 5=中证500 6=中证1000 7=标普500 8=科创50 9=国债
"""

import pandas as pd
import numpy as np
import json
from functools import reduce

FEE = 0.0002
MIN_HOLD = 5  # 最小持仓周期（交易日）

# ============ 1. 读取数据 ============
files = {
    1: 'C:/Users/wbl/Desktop/同花顺历史数据/上证50.xlsx',
    2: 'C:/Users/wbl/Desktop/同花顺历史数据/创业板50.xlsx',
    3: 'C:/Users/wbl/Desktop/纳斯达克100.xlsx',
    4: 'C:/Users/wbl/Desktop/沪深300.xlsx',
    5: 'C:/Users/wbl/Desktop/中证500.xlsx',
    6: 'C:/Users/wbl/Desktop/中证1000.xlsx',
    7: 'C:/Users/wbl/Desktop/标普500.xlsx',
    8: 'C:/Users/wbl/Desktop/科创50.xlsx',
    9: 'C:/Users/wbl/Desktop/国债.xlsx',
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

# ============ 2. 通用回测函数 ============
def run_backtest(stock_ids, bond_id, start_date, end_date, label):
    """对指定股票指数集合+国债做回测（含最小持仓期约束）"""
    all_ids = stock_ids + [bond_id]
    # 内连接
    df = reduce(lambda a,b: pd.merge(a,b,on='date',how='inner'), [dfs[i] for i in all_ids])
    df = df.sort_values('date').reset_index(drop=True)
    # 限定区间
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)
    if len(df) < 25:
        print(f"  {label}: 数据不足({len(df)}天)，跳过")
        return None

    print(f"  {label}: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)}天, 股票{stock_ids}+国债{bond_id}")

    # MA20和买入因子
    for i in stock_ids:
        df[f'ma20_{i}'] = df[f'close_{i}'].rolling(20).mean()
        df[f'bf_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}'] - 1
        df[f'ratio_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}']
    df = df.dropna(subset=[f'ma20_{i}' for i in stock_ids]).reset_index(drop=True)

    # 信号（与V8一致）
    def get_signal(row):
        ratios = [row[f'ratio_{i}'] for i in stock_ids]
        if all(r < 1 for r in ratios):
            return bond_id
        bfs = {i: row[f'bf_{i}'] for i in stock_ids}
        return max(bfs, key=bfs.get)
    df['signal'] = df.apply(get_signal, axis=1)

    # ============ 最小持仓期约束的持仓计算 ============
    # position[i] 基于前一天 signal（次日开盘执行）
    # 约束：当前持仓不满MIN_HOLD天则不切换
    positions = [0]  # 第一天position=0（空仓）
    hold_days_list = [0]
    blocked_switches = 0  # 被最小持仓期阻止的切换次数
    for i in range(1, len(df)):
        target_sig = df['signal'].iloc[i-1]  # 前一天信号
        prev_pos = positions[-1]
        prev_hold = hold_days_list[-1]

        if prev_pos == 0:
            # 前一天空仓，直接按信号建仓
            new_pos = target_sig
            new_hold = 1
        elif prev_hold < MIN_HOLD:
            # 未满最小持仓期，维持现状（即使信号变化）
            if target_sig != prev_pos:
                blocked_switches += 1
            new_pos = prev_pos
            new_hold = prev_hold + 1
        else:
            # 已满最小持仓期，可以按信号切换
            new_pos = target_sig
            new_hold = 1 if new_pos != prev_pos else prev_hold + 1

        positions.append(new_pos)
        hold_days_list.append(new_hold)

    df['position'] = positions

    # 收益
    for i in all_ids:
        df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
    last_idx = df.index[-1]
    for i in all_ids:
        df[f'ret_{i}'] = np.nan
        mask = df[f'open_{i}_next'].notna()
        df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
        df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

    # 手续费
    df['prev_position'] = df['position'].shift(1)
    df.loc[df.index[0], 'prev_position'] = df.loc[df.index[0], 'position']
    def calc_cost(row):
        old, new = row['prev_position'], row['position']
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

    # 净值
    df['strat_nav'] = (1 + df['strat_ret']).cumprod()
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
    pos_arr = df['position'].values
    switches = int(np.sum(np.diff(pos_arr)!=0))
    hold = {i: int(np.sum(pos_arr==i)) for i in all_ids}
    cash_days = int(np.sum(pos_arr==0))

    r = {
        'start_date': df['date'].iloc[0].strftime('%Y-%m-%d'),
        'end_date': df['date'].iloc[-1].strftime('%Y-%m-%d'),
        'n_days': n,
        'stock_ids': stock_ids,
        'strat_total': strat_total,
        'strat_ann': ann(strat_total, n),
        'strat_mdd': mdd(df['strat_nav']),
        'strat_sharpe': sharpe(df['strat_ret'], n),
        'switches': switches,
        'blocked_switches': blocked_switches,
        'total_fee': float(df['trade_cost'].sum()),
        'nav_dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
        'strat_nav': [round(x,4) for x in df['strat_nav'].tolist()],
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
    r = run_backtest(stocks, BOND, sd, last_date, name)
    results[name] = r
    print()

# ============ 4. 打印结果 ============
print("="*100)
print(f"MA20轮动策略 V11 回测结果（V8 + 最小持仓{MIN_HOLD}天约束）")
print("="*100)

for name in ['近10年','近5年','近3年','近1年']:
    r = results[name]
    if r is None: continue
    stocks = r['stock_ids']
    all_ids = stocks + [BOND]
    print(f"\n{'─'*95}")
    print(f"  {name} ({r['start_date']}~{r['end_date']}, {r['n_days']}天) 参与股票: {','.join(names[i] for i in stocks)}")
    print(f"{'─'*95}")
    hdr = f"  {'指标':<7} {'策略':>9}"
    for i in all_ids:
        hdr += f" {names[i]:>9}"
    print(hdr)
    print(f"  {'总收益率':<5} {r['strat_total']:>9.2%}", end='')
    for i in all_ids: print(f" {r[f'bh{i}_total']:>9.2%}", end='')
    print()
    print(f"  {'年化收益':<5} {r['strat_ann']:>9.2%}", end='')
    for i in all_ids: print(f" {r[f'bh{i}_ann']:>9.2%}", end='')
    print()
    print(f"  {'最大回撤':<5} {r['strat_mdd']:>9.2%}", end='')
    for i in all_ids: print(f" {r[f'bh{i}_mdd']:>9.2%}", end='')
    print()
    print(f"  {'夏普比率':<5} {r['strat_sharpe']:>9.2f}", end='')
    for i in all_ids: print(f" {r[f'bh{i}_sharpe']:>9.2f}", end='')
    print()
    print(f"  切换{r['switches']}次(被阻止{r['blocked_switches']}次) | 手续费{r['total_fee']:.2%} | 持仓:", end='')
    for i in all_ids:
        print(f" {names[i]}{r[f'hold{i}_pct']:.0%}", end='')
    print(f" | 空仓{r['cash_pct']:.0%}")

# ============ 5. 导出 ============
def clean(o):
    if isinstance(o, (np.floating, np.integer)): return float(o)
    return o

output = {
    'results': {k: {kk: clean(vv) for kk,vv in v.items()} for k,v in results.items() if v},
    'names': names,
    'min_hold': MIN_HOLD,
}
with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v11_data.json','w',encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)
print("\n数据已导出到 backtest_v11_data.json")
