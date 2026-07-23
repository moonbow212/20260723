# -*- coding: utf-8 -*-
"""
MA20轮动策略回测 V5 —— 三指数轮动(上证50/创业板50/纳斯达克) + 国债避险
策略规则：
  买入因子 = 当日收盘价 / 当日MA20 - 1
  - 三个股票指数 bf 都 < 0（均跌破MA20）→ 买入国债指数
  - 否则 → 持有三个指数中买入因子最高的那个
  - 次日开盘价执行
  - 每次买入或卖出收取万分之二(0.02%)手续费
"""

import pandas as pd
import numpy as np
import json

FEE = 0.0002  # 万分之二，单边

# ============ 1. 读取数据 ============
df1 = pd.read_csv('C:/Users/wbl/Desktop/同花顺历史数据/上证50.xlsx', sep='\t', encoding='gbk')
df2 = pd.read_csv('C:/Users/wbl/Desktop/同花顺历史数据/创业板50.xlsx', sep='\t', encoding='gbk')
df3 = pd.read_csv('C:/Users/wbl/Desktop/纳斯达克.xlsx', sep='\t', encoding='gbk')
df4 = pd.read_csv('C:/Users/wbl/Desktop/国债.xlsx', sep='\t', encoding='gbk')

df1['date'] = pd.to_datetime(df1['时间'].str.split(',').str[0])
df2['date'] = pd.to_datetime(df2['时间'].str.split(',').str[0])
df3['date'] = pd.to_datetime(df3['时间'].str.split(',').str[0])
df4['date'] = pd.to_datetime(df4['时间'].str.split(',').str[0])

df1 = df1[['date', '开盘', '收盘']].rename(columns={'开盘': 'open_1', '收盘': 'close_1'})  # 上证50
df2 = df2[['date', '开盘', '收盘']].rename(columns={'开盘': 'open_2', '收盘': 'close_2'})  # 创业板50
df3 = df3[['date', '开盘', '收盘']].rename(columns={'开盘': 'open_3', '收盘': 'close_3'})  # 纳斯达克
df4 = df4[['date', '开盘', '收盘']].rename(columns={'开盘': 'open_4', '收盘': 'close_4'})  # 国债

for c in ['open_1', 'close_1']:
    df1[c] = pd.to_numeric(df1[c], errors='coerce')
for c in ['open_2', 'close_2']:
    df2[c] = pd.to_numeric(df2[c], errors='coerce')
for c in ['open_3', 'close_3']:
    df3[c] = pd.to_numeric(df3[c], errors='coerce')
for c in ['open_4', 'close_4']:
    df4[c] = pd.to_numeric(df4[c], errors='coerce')
df1 = df1.dropna()
df2 = df2.dropna()
df3 = df3.dropna()
df4 = df4.dropna()

# 四指数内连接
df = pd.merge(df1, df2, on='date', how='inner')
df = pd.merge(df, df3, on='date', how='inner')
df = pd.merge(df, df4, on='date', how='inner')
df = df.sort_values('date').reset_index(drop=True)

print(f"四指数合并后: {len(df)} 天, {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}")

# ============ 2. 计算MA20和买入因子 ============
df['ma20_1'] = df['close_1'].rolling(20).mean()
df['ma20_2'] = df['close_2'].rolling(20).mean()
df['ma20_3'] = df['close_3'].rolling(20).mean()
df['bf_1'] = df['close_1'] / df['ma20_1'] - 1
df['bf_2'] = df['close_2'] / df['ma20_2'] - 1
df['bf_3'] = df['close_3'] / df['ma20_3'] - 1
df['ratio_1'] = df['close_1'] / df['ma20_1']
df['ratio_2'] = df['close_2'] / df['ma20_2']
df['ratio_3'] = df['close_3'] / df['ma20_3']

df = df.dropna(subset=['ma20_1', 'ma20_2', 'ma20_3']).reset_index(drop=True)
print(f"MA20计算后: {len(df)} 天")

# ============ 3. 生成交易信号 ============
# signal[t]:
#   三个股票 ratio 都 < 1 → 4 (持有国债)
#   否则 → 持有 bf 最高的股票指数 (1/2/3)
def get_signal(row):
    if row['ratio_1'] < 1 and row['ratio_2'] < 1 and row['ratio_3'] < 1:
        return 4
    bfs = {1: row['bf_1'], 2: row['bf_2'], 3: row['bf_3']}
    return max(bfs, key=bfs.get)

df['signal'] = df.apply(get_signal, axis=1)
df['position'] = df['signal'].shift(1)
df.loc[df.index[0], 'position'] = 0

# ============ 4. 计算每日收益（含手续费）============
for i in [1, 2, 3, 4]:
    df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)

last_idx = df.index[-1]
for i in [1, 2, 3, 4]:
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
    if old in (1, 2, 3, 4):
        cost += FEE
    if new in (1, 2, 3, 4):
        cost += FEE
    return cost

df['trade_cost'] = df.apply(calc_cost, axis=1)

# 策略日收益
def get_strat_ret(row):
    pos = int(row['position'])
    if pos in (1, 2, 3, 4):
        gross = row[f'ret_{pos}']
    else:
        gross = 0.0
    cost = row['trade_cost']
    return (1 + gross) * (1 - cost) - 1

df['strat_ret'] = df.apply(get_strat_ret, axis=1)

# ============ 5. 净值和指标 ============
df['strat_nav'] = (1 + df['strat_ret']).cumprod()
for i in [1, 2, 3, 4]:
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

name_map = {1: '上证50', 2: '创业板50', 3: '纳斯达克', 4: '国债'}

results = {}
for name, start_date in periods.items():
    sub = df[df['date'] >= start_date].copy()
    if len(sub) < 2:
        results[name] = None
        continue

    sub['strat_nav_r'] = (1 + sub['strat_ret']).cumprod()
    for i in [1, 2, 3, 4]:
        sub[f'bh_{i}_nav_r'] = (1 + sub[f'ret_{i}']).cumprod()

    n_days = len(sub)
    strat_total = sub['strat_nav_r'].iloc[-1] - 1
    bh_totals = {i: sub[f'bh_{i}_nav_r'].iloc[-1] - 1 for i in [1, 2, 3, 4]}

    strat_ann = annualized_ret(strat_total, n_days)
    bh_anns = {i: annualized_ret(bh_totals[i], n_days) for i in [1, 2, 3, 4]}

    strat_mdd = max_drawdown(sub['strat_nav_r'])
    bh_mdds = {i: max_drawdown(sub[f'bh_{i}_nav_r']) for i in [1, 2, 3, 4]}

    strat_sharpe = sharpe(sub['strat_ret'], n_days)
    bh_sharpes = {i: sharpe(sub[f'ret_{i}'], n_days) for i in [1, 2, 3, 4]}

    pos = sub['position'].values
    switches = int(np.sum(np.diff(pos) != 0))
    hold_days = {i: int(np.sum(pos == i)) for i in [1, 2, 3, 4]}
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
    for i in [1, 2, 3, 4]:
        r[f'bh{i}_total'] = bh_totals[i]
        r[f'bh{i}_ann'] = bh_anns[i]
        r[f'bh{i}_mdd'] = bh_mdds[i]
        r[f'bh{i}_sharpe'] = bh_sharpes[i]
        r[f'hold{i}_days'] = hold_days[i]
        r[f'hold{i}_pct'] = hold_days[i] / n_days
    r['cash_pct'] = cash_days / n_days
    results[name] = r

# ============ 7. 打印结果 ============
print("\n" + "="*110)
print("MA20轮动策略 V5 回测结果（上证50/创业板50/纳斯达克 三指数轮动 + 国债避险）")
print("="*110)
print(f"策略: 买入因子=收盘/MA20-1，三股票指数取bf最高者，三者均跌破MA20时持有国债")
print(f"执行: 次日开盘价 | 手续费: 买入0.02%+卖出0.02%=切换0.04%")

for name in ['近10年', '近5年', '近3年', '近1年']:
    r = results[name]
    if r is None:
        continue
    print(f"\n{'─'*90}")
    print(f"  {name}  ({r['start_date']} ~ {r['end_date']}, {r['n_days']}个交易日)")
    print(f"{'─'*90}")
    print(f"  {'指标':<10} {'轮动策略':>12} {'上证50':>11} {'创业板50':>11} {'纳斯达克':>11} {'国债':>11}")
    print(f"  {'总收益率':<8} {r['strat_total']:>11.2%} {r['bh1_total']:>11.2%} {r['bh2_total']:>11.2%} {r['bh3_total']:>11.2%} {r['bh4_total']:>11.2%}")
    print(f"  {'年化收益':<8} {r['strat_ann']:>11.2%} {r['bh1_ann']:>11.2%} {r['bh2_ann']:>11.2%} {r['bh3_ann']:>11.2%} {r['bh4_ann']:>11.2%}")
    print(f"  {'最大回撤':<8} {r['strat_mdd']:>11.2%} {r['bh1_mdd']:>11.2%} {r['bh2_mdd']:>11.2%} {r['bh3_mdd']:>11.2%} {r['bh4_mdd']:>11.2%}")
    print(f"  {'夏普比率':<8} {r['strat_sharpe']:>12.2f} {r['bh1_sharpe']:>11.2f} {r['bh2_sharpe']:>11.2f} {r['bh3_sharpe']:>11.2f} {r['bh4_sharpe']:>11.2f}")
    print(f"  切换次数: {r['switches']} | 累计手续费: {r['total_fee']:.2%}")
    print(f"  持仓: 上证50 {r['hold1_pct']:.1%} | 创业板50 {r['hold2_pct']:.1%} | 纳斯达克 {r['hold3_pct']:.1%} | 国债 {r['hold4_pct']:.1%} | 空仓 {r['cash_pct']:.1%}")

# ============ 8. 导出数据 ============
nav_data = df[['date', 'strat_nav', 'bh_1_nav', 'bh_2_nav', 'bh_3_nav', 'bh_4_nav']].copy()
nav_data['date'] = nav_data['date'].dt.strftime('%Y-%m-%d')

full_nav = {
    'dates': nav_data['date'].tolist(),
    'strat': [round(x, 4) for x in nav_data['strat_nav'].tolist()],
    'bh1': [round(x, 4) for x in nav_data['bh_1_nav'].tolist()],
    'bh2': [round(x, 4) for x in nav_data['bh_2_nav'].tolist()],
    'bh3': [round(x, 4) for x in nav_data['bh_3_nav'].tolist()],
    'bh4': [round(x, 4) for x in nav_data['bh_4_nav'].tolist()],
}

period_navs = {}
for name, start_date in periods.items():
    sub = df[df['date'] >= start_date].copy()
    if len(sub) < 2:
        continue
    period_navs[name] = {
        'dates': sub['date'].dt.strftime('%Y-%m-%d').tolist(),
        'strat': [round(x, 4) for x in (1 + sub['strat_ret']).cumprod().tolist()],
        'bh1': [round(x, 4) for x in (1 + sub['ret_1']).cumprod().tolist()],
        'bh2': [round(x, 4) for x in (1 + sub['ret_2']).cumprod().tolist()],
        'bh3': [round(x, 4) for x in (1 + sub['ret_3']).cumprod().tolist()],
        'bh4': [round(x, 4) for x in (1 + sub['ret_4']).cumprod().tolist()],
    }

output = {
    'results': {k: {kk: (vv if not isinstance(vv, (np.floating, np.integer)) else float(vv))
                     for kk, vv in v.items()} for k, v in results.items() if v is not None},
    'full_nav': full_nav,
    'period_navs': period_navs,
}

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v5_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)

print("\n数据已导出到 backtest_v5_data.json")
