# -*- coding: utf-8 -*-
"""
MA20轮动策略回测 V7 —— 六指数轮动 + 国债避险
策略规则：
  买入因子 = 当日收盘价 / 当日MA20 - 1
  - 六个股票指数 bf 都 < 0（均跌破MA20）→ 买入国债指数
  - 否则 → 持有六个指数中买入因子最高的那个
  - 次日开盘价执行
  - 每次买入或卖出收取万分之二(0.02%)手续费
股票指数:
  1=上证50, 2=创业板50, 3=纳斯达克100, 4=沪深300, 5=中证500, 6=中证1000
  7=国债(避险)
"""

import pandas as pd
import numpy as np
import json

FEE = 0.0002  # 万分之二，单边

# ============ 1. 读取数据 ============
df1 = pd.read_csv('C:/Users/wbl/Desktop/同花顺历史数据/上证50.xlsx', sep='\t', encoding='gbk')
df2 = pd.read_csv('C:/Users/wbl/Desktop/同花顺历史数据/创业板50.xlsx', sep='\t', encoding='gbk')
df3 = pd.read_csv('C:/Users/wbl/Desktop/纳斯达克100.xlsx', sep='\t', encoding='gbk')
df4 = pd.read_csv('C:/Users/wbl/Desktop/沪深300.xlsx', sep='\t', encoding='gbk')
df5 = pd.read_csv('C:/Users/wbl/Desktop/中证500.xlsx', sep='\t', encoding='gbk')
df6 = pd.read_csv('C:/Users/wbl/Desktop/中证1000.xlsx', sep='\t', encoding='gbk')
df7 = pd.read_csv('C:/Users/wbl/Desktop/国债.xlsx', sep='\t', encoding='gbk')

names = {1:'上证50', 2:'创业板50', 3:'纳斯达克100', 4:'沪深300', 5:'中证500', 6:'中证1000', 7:'国债'}
dfs = {1:df1, 2:df2, 3:df3, 4:df4, 5:df5, 6:df6, 7:df7}

for i, d in dfs.items():
    d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
    d.rename(columns={'开盘': f'open_{i}', '收盘': f'close_{i}'}, inplace=True)
    for c in [f'open_{i}', f'close_{i}']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    dfs[i] = d[[f'date', f'open_{i}', f'close_{i}']].dropna()

# 内连接所有
from functools import reduce
df = reduce(lambda a, b: pd.merge(a, b, on='date', how='inner'), [dfs[i] for i in [1,2,3,4,5,6,7]])
df = df.sort_values('date').reset_index(drop=True)
print(f"七指数合并后: {len(df)} 天, {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}")

# ============ 2. 计算MA20和买入因子 ============
for i in [1,2,3,4,5,6]:
    df[f'ma20_{i}'] = df[f'close_{i}'].rolling(20).mean()
    df[f'bf_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}'] - 1
    df[f'ratio_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}']

df = df.dropna(subset=[f'ma20_{i}' for i in [1,2,3,4,5,6]]).reset_index(drop=True)
print(f"MA20计算后: {len(df)} 天")

# ============ 3. 生成交易信号 ============
# signal[t]:
#   六个股票 ratio 都 < 1 → 7 (持有国债)
#   否则 → 持有 bf 最高的股票指数 (1-6)
STOCK_IDX = [1,2,3,4,5,6]

def get_signal(row):
    ratios = [row[f'ratio_{i}'] for i in STOCK_IDX]
    if all(r < 1 for r in ratios):
        return 7
    bfs = {i: row[f'bf_{i}'] for i in STOCK_IDX}
    return max(bfs, key=bfs.get)

df['signal'] = df.apply(get_signal, axis=1)
df['position'] = df['signal'].shift(1)
df.loc[df.index[0], 'position'] = 0

# ============ 4. 计算每日收益（含手续费）============
ALL_IDX = [1,2,3,4,5,6,7]
for i in ALL_IDX:
    df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)

last_idx = df.index[-1]
for i in ALL_IDX:
    df[f'ret_{i}'] = np.nan
    mask = df[f'open_{i}_next'].notna()
    df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
    df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

# 手续费
df['prev_position'] = df['position'].shift(1)
df.loc[df.index[0], 'prev_position'] = df.loc[df.index[0], 'position']

def calc_cost(row):
    old = row['prev_position']
    new = row['position']
    if old == new:
        return 0.0
    cost = 0.0
    if old in ALL_IDX:
        cost += FEE
    if new in ALL_IDX:
        cost += FEE
    return cost

df['trade_cost'] = df.apply(calc_cost, axis=1)

# 策略日收益
def get_strat_ret(row):
    pos = int(row['position'])
    if pos in ALL_IDX:
        gross = row[f'ret_{pos}']
    else:
        gross = 0.0
    cost = row['trade_cost']
    return (1 + gross) * (1 - cost) - 1

df['strat_ret'] = df.apply(get_strat_ret, axis=1)

# ============ 5. 净值和指标 ============
df['strat_nav'] = (1 + df['strat_ret']).cumprod()
for i in ALL_IDX:
    df[f'bh_{i}_nav'] = (1 + df[f'ret_{i}']).cumprod()

def max_drawdown(nav_series):
    nav = nav_series.dropna()
    if len(nav) == 0:
        return 0
    peak = nav.cummax()
    dd = (nav - peak) / peak
    return dd.min()

def annualized_ret(total_ret, days):
    if days <= 0 or total_ret <= -1:
        return 0
    return (1 + total_ret) ** (252 / days) - 1

def sharpe(daily_rets, days):
    s = daily_rets.std()
    if s == 0 or days == 0:
        return 0
    return np.sqrt(252) * daily_rets.mean() / s

# ============ 6. 分时段统计 ============
end_date = df['date'].max()
periods = {
    '近10年': end_date - pd.DateOffset(years=10),
    '近5年': end_date - pd.DateOffset(years=5),
    '近3年': end_date - pd.DateOffset(years=3),
    '近1年': end_date - pd.DateOffset(years=1),
}

results = {}
for name, start_date in periods.items():
    sub = df[df['date'] >= start_date].copy()
    if len(sub) < 2:
        results[name] = None
        continue

    sub['strat_nav_r'] = (1 + sub['strat_ret']).cumprod()
    for i in ALL_IDX:
        sub[f'bh_{i}_nav_r'] = (1 + sub[f'ret_{i}']).cumprod()

    n_days = len(sub)
    strat_total = sub['strat_nav_r'].iloc[-1] - 1
    bh_totals = {i: sub[f'bh_{i}_nav_r'].iloc[-1] - 1 for i in ALL_IDX}

    strat_ann = annualized_ret(strat_total, n_days)
    bh_anns = {i: annualized_ret(bh_totals[i], n_days) for i in ALL_IDX}

    strat_mdd = max_drawdown(sub['strat_nav_r'])
    bh_mdds = {i: max_drawdown(sub[f'bh_{i}_nav_r']) for i in ALL_IDX}

    strat_sharpe = sharpe(sub['strat_ret'], n_days)
    bh_sharpes = {i: sharpe(sub[f'ret_{i}'], n_days) for i in ALL_IDX}

    pos = sub['position'].values
    switches = int(np.sum(np.diff(pos) != 0))
    hold_days = {i: int(np.sum(pos == i)) for i in ALL_IDX}
    cash_days = int(np.sum(pos == 0))

    total_fee = float(sub['trade_cost'].sum())

    r = {
        'start_date': sub['date'].iloc[0].strftime('%Y-%m-%d'),
        'end_date': sub['date'].iloc[-1].strftime('%Y-%m-%d'),
        'n_days': n_days,
        'strat_total': strat_total,
        'strat_ann': strat_ann,
        'strat_mdd': strat_mdd,
        'strat_sharpe': strat_sharpe,
        'switches': switches,
        'total_fee': total_fee,
    }
    for i in ALL_IDX:
        r[f'bh{i}_total'] = bh_totals[i]
        r[f'bh{i}_ann'] = bh_anns[i]
        r[f'bh{i}_mdd'] = bh_mdds[i]
        r[f'bh{i}_sharpe'] = bh_sharpes[i]
        r[f'hold{i}_days'] = hold_days[i]
        r[f'hold{i}_pct'] = hold_days[i] / n_days
    r['cash_pct'] = cash_days / n_days
    results[name] = r

# ============ 7. 打印结果 ============
print("\n" + "="*120)
print("MA20轮动策略 V7 回测结果（六指数轮动 + 国债避险）")
print("="*120)
print(f"股票指数: 1=上证50 2=创业板50 3=纳斯达克100 4=沪深300 5=中证500 6=中证1000 | 7=国债")
print(f"策略: 买入因子=收盘/MA20-1，六股票指数取bf最高者，六者均跌破MA20时持有国债")
print(f"执行: 次日开盘价 | 手续费: 买入0.02%+卖出0.02%=切换0.04%")

for name in ['近10年', '近5年', '近3年', '近1年']:
    r = results[name]
    if r is None:
        continue
    print(f"\n{'─'*100}")
    print(f"  {name}  ({r['start_date']} ~ {r['end_date']}, {r['n_days']}个交易日)")
    print(f"{'─'*100}")
    hdr = f"  {'指标':<8} {'策略':>10}"
    for i in ALL_IDX:
        hdr += f" {names[i]:>10}"
    print(hdr)
    print(f"  {'总收益率':<6} {r['strat_total']:>10.2%}", end='')
    for i in ALL_IDX:
        print(f" {r[f'bh{i}_total']:>10.2%}", end='')
    print()
    print(f"  {'年化收益':<6} {r['strat_ann']:>10.2%}", end='')
    for i in ALL_IDX:
        print(f" {r[f'bh{i}_ann']:>10.2%}", end='')
    print()
    print(f"  {'最大回撤':<6} {r['strat_mdd']:>10.2%}", end='')
    for i in ALL_IDX:
        print(f" {r[f'bh{i}_mdd']:>10.2%}", end='')
    print()
    print(f"  {'夏普比率':<6} {r['strat_sharpe']:>10.2f}", end='')
    for i in ALL_IDX:
        print(f" {r[f'bh{i}_sharpe']:>10.2f}", end='')
    print()
    print(f"  切换次数: {r['switches']} | 累计手续费: {r['total_fee']:.2%}")
    hold_str = "  持仓占比: "
    for i in ALL_IDX:
        hold_str += f"{names[i]} {r[f'hold{i}_pct']:.1%} | "
    hold_str += f"空仓 {r['cash_pct']:.1%}"
    print(hold_str)

# ============ 8. 导出数据 ============
nav_cols = ['date', 'strat_nav'] + [f'bh_{i}_nav' for i in ALL_IDX]
nav_data = df[nav_cols].copy()
nav_data['date'] = nav_data['date'].dt.strftime('%Y-%m-%d')

full_nav = {
    'dates': nav_data['date'].tolist(),
    'strat': [round(x, 4) for x in nav_data['strat_nav'].tolist()],
}
for i in ALL_IDX:
    full_nav[f'bh{i}'] = [round(x, 4) for x in nav_data[f'bh_{i}_nav'].tolist()]

period_navs = {}
for name, start_date in periods.items():
    sub = df[df['date'] >= start_date].copy()
    if len(sub) < 2:
        continue
    period_navs[name] = {
        'dates': sub['date'].dt.strftime('%Y-%m-%d').tolist(),
        'strat': [round(x, 4) for x in (1 + sub['strat_ret']).cumprod().tolist()],
    }
    for i in ALL_IDX:
        period_navs[name][f'bh{i}'] = [round(x, 4) for x in (1 + sub[f'ret_{i}']).cumprod().tolist()]

output = {
    'results': {k: {kk: (vv if not isinstance(vv, (np.floating, np.integer)) else float(vv))
                     for kk, vv in v.items()} for k, v in results.items() if v is not None},
    'full_nav': full_nav,
    'period_navs': period_navs,
    'names': names,
}

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v7_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)

print("\n数据已导出到 backtest_v7_data.json")
