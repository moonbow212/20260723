# -*- coding: utf-8 -*-
"""
MA20轮动策略回测 V3 —— 使用中证红利指数（价格指数，2005年起，全程覆盖）
策略规则：
  买入因子 = 当日收盘价 / 当日MA20 - 1
  - 两个指数 bf 都 < 0（均跌破MA20）→ 买入中证红利指数
  - 否则 → 持有买入因子更高的那个指数（上证50/创业板50）
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
df3 = pd.read_csv('C:/Users/wbl/Desktop/中证红利.xlsx', sep='\t', encoding='gbk')

df1['date'] = pd.to_datetime(df1['时间'].str.split(',').str[0])
df2['date'] = pd.to_datetime(df2['时间'].str.split(',').str[0])
df3['date'] = pd.to_datetime(df3['时间'].str.split(',').str[0])

df1 = df1[['date', '开盘', '收盘']].rename(columns={'开盘': 'open_1', '收盘': 'close_1'})
df2 = df2[['date', '开盘', '收盘']].rename(columns={'开盘': 'open_2', '收盘': 'close_2'})
df3 = df3[['date', '开盘', '收盘']].rename(columns={'开盘': 'open_3', '收盘': 'close_3'})

for c in ['open_1', 'close_1']:
    df1[c] = pd.to_numeric(df1[c], errors='coerce')
for c in ['open_2', 'close_2']:
    df2[c] = pd.to_numeric(df2[c], errors='coerce')
for c in ['open_3', 'close_3']:
    df3[c] = pd.to_numeric(df3[c], errors='coerce')
df1 = df1.dropna()
df2 = df2.dropna()
df3 = df3.dropna()

# 三指数内连接
df = pd.merge(df1, df2, on='date', how='inner')
df = pd.merge(df, df3, on='date', how='inner')
df = df.sort_values('date').reset_index(drop=True)

print(f"三指数合并后: {len(df)} 天, {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}")
print(f"中证红利覆盖: 全程 {len(df3)} 天 (无缺口)")

# ============ 2. 计算MA20和买入因子 ============
df['ma20_1'] = df['close_1'].rolling(20).mean()
df['ma20_2'] = df['close_2'].rolling(20).mean()
df['bf_1'] = df['close_1'] / df['ma20_1'] - 1
df['bf_2'] = df['close_2'] / df['ma20_2'] - 1
df['ratio_1'] = df['close_1'] / df['ma20_1']
df['ratio_2'] = df['close_2'] / df['ma20_2']

df = df.dropna(subset=['ma20_1', 'ma20_2']).reset_index(drop=True)
print(f"MA20计算后: {len(df)} 天")

# ============ 3. 生成交易信号 ============
# signal[t]:
#   两个 bf 都 < 0 → 3 (持有中证红利)
#   bf_1 >= bf_2 → 1 (上证50)
#   否则 → 2 (创业板50)
def get_signal(row):
    if row['ratio_1'] < 1 and row['ratio_2'] < 1:
        return 3
    elif row['bf_1'] >= row['bf_2']:
        return 1
    else:
        return 2

df['signal'] = df.apply(get_signal, axis=1)
df['position'] = df['signal'].shift(1)
df.loc[df.index[0], 'position'] = 0

# ============ 4. 计算每日收益（含手续费）============
df['open_1_next'] = df['open_1'].shift(-1)
df['open_2_next'] = df['open_2'].shift(-1)
df['open_3_next'] = df['open_3'].shift(-1)

last_idx = df.index[-1]

df['ret_1'] = np.nan
mask = df['open_1_next'].notna()
df.loc[mask, 'ret_1'] = df.loc[mask, 'open_1_next'] / df.loc[mask, 'open_1'] - 1
df.loc[last_idx, 'ret_1'] = df.loc[last_idx, 'close_1'] / df.loc[last_idx, 'open_1'] - 1

df['ret_2'] = np.nan
df.loc[mask, 'ret_2'] = df.loc[mask, 'open_2_next'] / df.loc[mask, 'open_2'] - 1
df.loc[last_idx, 'ret_2'] = df.loc[last_idx, 'close_2'] / df.loc[last_idx, 'open_2'] - 1

df['ret_3'] = np.nan
mask3 = df['open_3_next'].notna()
df.loc[mask3, 'ret_3'] = df.loc[mask3, 'open_3_next'] / df.loc[mask3, 'open_3'] - 1
df.loc[last_idx, 'ret_3'] = df.loc[last_idx, 'close_3'] / df.loc[last_idx, 'open_3'] - 1

# 手续费
df['prev_position'] = df['position'].shift(1)
df.loc[df.index[0], 'prev_position'] = df.loc[df.index[0], 'position']

def calc_cost(row):
    old = row['prev_position']
    new = row['position']
    if old == new:
        return 0.0
    cost = 0.0
    if old in (1, 2, 3):
        cost += FEE
    if new in (1, 2, 3):
        cost += FEE
    return cost

df['trade_cost'] = df.apply(calc_cost, axis=1)

# 策略日收益
def get_strat_ret(row):
    pos = row['position']
    if pos == 1:
        gross = row['ret_1']
    elif pos == 2:
        gross = row['ret_2']
    elif pos == 3:
        gross = row['ret_3']
    else:
        gross = 0.0
    cost = row['trade_cost']
    return (1 + gross) * (1 - cost) - 1

df['strat_ret'] = df.apply(get_strat_ret, axis=1)

# ============ 5. 净值和指标 ============
df['strat_nav'] = (1 + df['strat_ret']).cumprod()
df['bh_1_nav'] = (1 + df['ret_1']).cumprod()
df['bh_2_nav'] = (1 + df['ret_2']).cumprod()
df['bh_3_nav'] = (1 + df['ret_3']).cumprod()

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
    sub['bh_1_nav_r'] = (1 + sub['ret_1']).cumprod()
    sub['bh_2_nav_r'] = (1 + sub['ret_2']).cumprod()
    sub['bh_3_nav_r'] = (1 + sub['ret_3']).cumprod()

    n_days = len(sub)
    strat_total = sub['strat_nav_r'].iloc[-1] - 1
    bh1_total = sub['bh_1_nav_r'].iloc[-1] - 1
    bh2_total = sub['bh_2_nav_r'].iloc[-1] - 1
    bh3_total = sub['bh_3_nav_r'].iloc[-1] - 1

    strat_ann = annualized_ret(strat_total, n_days)
    bh1_ann = annualized_ret(bh1_total, n_days)
    bh2_ann = annualized_ret(bh2_total, n_days)
    bh3_ann = annualized_ret(bh3_total, n_days)

    strat_mdd = max_drawdown(sub['strat_nav_r'])
    bh1_mdd = max_drawdown(sub['bh_1_nav_r'])
    bh2_mdd = max_drawdown(sub['bh_2_nav_r'])
    bh3_mdd = max_drawdown(sub['bh_3_nav_r'])

    strat_sharpe = sharpe(sub['strat_ret'], n_days)
    bh1_sharpe = sharpe(sub['ret_1'], n_days)
    bh2_sharpe = sharpe(sub['ret_2'], n_days)
    bh3_sharpe = sharpe(sub['ret_3'], n_days)

    pos = sub['position'].values
    switches = int(np.sum(np.diff(pos) != 0))
    hold1_days = int(np.sum(pos == 1))
    hold2_days = int(np.sum(pos == 2))
    hold3_days = int(np.sum(pos == 3))
    cash_days = int(np.sum(pos == 0))

    total_fee = float(sub['trade_cost'].sum())

    results[name] = {
        'start_date': sub['date'].iloc[0].strftime('%Y-%m-%d'),
        'end_date': sub['date'].iloc[-1].strftime('%Y-%m-%d'),
        'n_days': n_days,
        'strat_total': strat_total,
        'bh1_total': bh1_total, 'bh2_total': bh2_total, 'bh3_total': bh3_total,
        'strat_ann': strat_ann,
        'bh1_ann': bh1_ann, 'bh2_ann': bh2_ann, 'bh3_ann': bh3_ann,
        'strat_mdd': strat_mdd,
        'bh1_mdd': bh1_mdd, 'bh2_mdd': bh2_mdd, 'bh3_mdd': bh3_mdd,
        'strat_sharpe': strat_sharpe,
        'bh1_sharpe': bh1_sharpe, 'bh2_sharpe': bh2_sharpe, 'bh3_sharpe': bh3_sharpe,
        'switches': switches,
        'hold1_days': hold1_days, 'hold2_days': hold2_days,
        'hold3_days': hold3_days, 'cash_days': cash_days,
        'hold1_pct': hold1_days / n_days, 'hold2_pct': hold2_days / n_days,
        'hold3_pct': hold3_days / n_days, 'cash_pct': cash_days / n_days,
        'total_fee': total_fee,
    }

# ============ 7. 打印结果 ============
print("\n" + "="*100)
print("MA20轮动策略 V3 回测结果（中证红利指数全程覆盖 + 手续费万分之二/单边）")
print("="*100)
print(f"策略: 买入因子=收盘/MA20-1，持有因子更高者，两者bf均<0时持有中证红利")
print(f"执行: 次日开盘价 | 手续费: 买入0.02%+卖出0.02%=切换0.04%")

for name in ['近10年', '近5年', '近3年', '近1年']:
    r = results[name]
    if r is None:
        continue
    print(f"\n{'─'*80}")
    print(f"  {name}  ({r['start_date']} ~ {r['end_date']}, {r['n_days']}个交易日)")
    print(f"{'─'*80}")
    print(f"  {'指标':<14} {'轮动策略':>12} {'上证50':>12} {'创业板50':>12} {'中证红利':>12}")
    print(f"  {'总收益率':<12} {r['strat_total']:>11.2%} {r['bh1_total']:>11.2%} {r['bh2_total']:>11.2%} {r['bh3_total']:>11.2%}")
    print(f"  {'年化收益':<13} {r['strat_ann']:>11.2%} {r['bh1_ann']:>11.2%} {r['bh2_ann']:>11.2%} {r['bh3_ann']:>11.2%}")
    print(f"  {'最大回撤':<14} {r['strat_mdd']:>11.2%} {r['bh1_mdd']:>11.2%} {r['bh2_mdd']:>11.2%} {r['bh3_mdd']:>11.2%}")
    print(f"  {'夏普比率':<14} {r['strat_sharpe']:>12.2f} {r['bh1_sharpe']:>12.2f} {r['bh2_sharpe']:>12.2f} {r['bh3_sharpe']:>12.2f}")
    print(f"  切换次数: {r['switches']} | 累计手续费: {r['total_fee']:.2%}")
    print(f"  持仓: 上证50 {r['hold1_pct']:.1%} | 创业板50 {r['hold2_pct']:.1%} | 红利 {r['hold3_pct']:.1%} | 空仓 {r['cash_pct']:.1%}")

# ============ 8. 导出数据 ============
nav_data = df[['date', 'strat_nav', 'bh_1_nav', 'bh_2_nav', 'bh_3_nav']].copy()
nav_data['date'] = nav_data['date'].dt.strftime('%Y-%m-%d')

full_nav = {
    'dates': nav_data['date'].tolist(),
    'strat': [round(x, 4) for x in nav_data['strat_nav'].tolist()],
    'bh1': [round(x, 4) for x in nav_data['bh_1_nav'].tolist()],
    'bh2': [round(x, 4) for x in nav_data['bh_2_nav'].tolist()],
    'bh3': [round(x, 4) for x in nav_data['bh_3_nav'].tolist()],
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
    }

output = {
    'results': {k: {kk: (vv if not isinstance(vv, (np.floating, np.integer)) else float(vv))
                     for kk, vv in v.items()} for k, v in results.items() if v is not None},
    'full_nav': full_nav,
    'period_navs': period_navs,
}

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v3_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)

print("\n数据已导出到 backtest_v3_data.json")
