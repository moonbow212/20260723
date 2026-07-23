# -*- coding: utf-8 -*-
"""
MA20轮动策略回测 V2 —— 叠加中证红利全收益指数 + 交易费率
策略规则：
  买入因子 = 当日收盘价 / 当日MA20 - 1
  - 两个指数 bf 都 < 0（均跌破MA20）→ 买入中证红利全收益指数（有数据时），否则空仓
  - 否则 → 持有买入因子更高的那个指数
  - 次日开盘价执行
  - 每次买入或卖出收取万分之二(0.02%)手续费，切换(卖A买B)总成本万分之四

注意：中证红利全收益指数数据仅 2025-02-14 起，此前该条件回退为空仓。
"""

import pandas as pd
import numpy as np
import json

FEE = 0.0002  # 万分之二，单边（买或卖）

# ============ 1. 读取数据 ============
df1 = pd.read_csv('C:/Users/wbl/Desktop/上证50.xlsx', sep='\t', encoding='gbk')
df2 = pd.read_csv('C:/Users/wbl/Desktop/创业板50.xlsx', sep='\t', encoding='gbk')
df3 = pd.read_csv('C:/Users/wbl/Desktop/中证红利全收益指数.xlsx', sep='\t', encoding='gbk')

# 解析日期
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

# 先内连接上证50和创业板50
df = pd.merge(df1, df2, on='date', how='inner').sort_values('date').reset_index(drop=True)
# 再左连接红利指数（可能没有数据）
df = pd.merge(df, df3, on='date', how='left').sort_values('date').reset_index(drop=True)

print(f"上证50+创业板50合并后: {len(df)} 天, {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}")
div_days = df['open_3'].notna().sum()
print(f"中证红利全收益指数有数据: {div_days} 天, 从 {df[df['open_3'].notna()]['date'].iloc[0].date()} 起")

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
#   两个 bf 都 < 0 (ratio < 1):
#     如果红利指数有次日开盘数据 → 3 (持有红利)
#     否则 → 0 (空仓)
#   bf_1 >= bf_2 → 1 (上证50)
#   否则 → 2 (创业板50)
def get_signal(row):
    if row['ratio_1'] < 1 and row['ratio_2'] < 1:
        # 检查次日是否有红利指数数据
        return 3  # 先标记为3，后面根据数据可用性调整
    elif row['bf_1'] >= row['bf_2']:
        return 1
    else:
        return 2

df['signal'] = df.apply(get_signal, axis=1)

# position[t] = signal[t-1]，次日开盘执行
df['position'] = df['signal'].shift(1)
df.loc[df.index[0], 'position'] = 0

# 检查红利指数数据可用性：如果position==3但当日没有红利开盘价，回退空仓
df['has_div'] = df['open_3'].notna()
# position==3但无红利数据 → 0(空仓)
df.loc[(df['position'] == 3) & (~df['has_div']), 'position'] = 0

# ============ 4. 计算每日收益（含手续费）============
df['open_1_next'] = df['open_1'].shift(-1)
df['open_2_next'] = df['open_2'].shift(-1)
df['open_3_next'] = df['open_3'].shift(-1)

# 三个指数的日收益（open-to-open，最后一天open-to-close）
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
# 最后一天如果有红利数据
if df.loc[last_idx, 'has_div']:
    df.loc[last_idx, 'ret_3'] = df.loc[last_idx, 'close_3'] / df.loc[last_idx, 'open_3'] - 1

# 计算手续费：当position变化时
df['prev_position'] = df['position'].shift(1)
df.loc[df.index[0], 'prev_position'] = df.loc[df.index[0], 'position']

def calc_cost(row):
    old = row['prev_position']
    new = row['position']
    if old == new:
        return 0.0
    cost = 0.0
    # 卖出旧持仓（如果是指数）
    if old in (1, 2, 3):
        cost += FEE
    # 买入新持仓（如果是指数）
    if new in (1, 2, 3):
        cost += FEE
    return cost

df['trade_cost'] = df.apply(calc_cost, axis=1)

# 策略日收益（扣除手续费）
def get_strat_ret(row):
    pos = row['position']
    if pos == 1:
        gross = row['ret_1']
    elif pos == 2:
        gross = row['ret_2']
    elif pos == 3:
        gross = row['ret_3'] if pd.notna(row['ret_3']) else 0.0
    else:  # 0 = 空仓
        gross = 0.0
    # 扣手续费
    cost = row['trade_cost']
    return (1 + gross) * (1 - cost) - 1

df['strat_ret'] = df.apply(get_strat_ret, axis=1)

# ============ 同时计算无费率版本用于对比 ============
df['strat_ret_nofee'] = df.apply(lambda r: 
    r['ret_1'] if r['position']==1 else
    r['ret_2'] if r['position']==2 else
    r['ret_3'] if (r['position']==3 and pd.notna(r['ret_3'])) else 0.0, axis=1)

# ============ 5. 净值和指标 ============
df['strat_nav'] = (1 + df['strat_ret']).cumprod()
df['bh_1_nav'] = (1 + df['ret_1']).cumprod()
df['bh_2_nav'] = (1 + df['ret_2']).cumprod()
# 红利买入持有净值（仅有数据区间）
df['bh_3_nav'] = np.nan
div_mask = df['ret_3'].notna()
df.loc[div_mask, 'bh_3_nav'] = (1 + df.loc[div_mask, 'ret_3']).cumprod()

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

    n_days = len(sub)
    strat_total = sub['strat_nav_r'].iloc[-1] - 1
    bh1_total = sub['bh_1_nav_r'].iloc[-1] - 1
    bh2_total = sub['bh_2_nav_r'].iloc[-1] - 1

    strat_ann = annualized_ret(strat_total, n_days)
    bh1_ann = annualized_ret(bh1_total, n_days)
    bh2_ann = annualized_ret(bh2_total, n_days)

    strat_mdd = max_drawdown(sub['strat_nav_r'])
    bh1_mdd = max_drawdown(sub['bh_1_nav_r'])
    bh2_mdd = max_drawdown(sub['bh_2_nav_r'])

    strat_sharpe = sharpe(sub['strat_ret'], n_days)
    bh1_sharpe = sharpe(sub['ret_1'], n_days)
    bh2_sharpe = sharpe(sub['ret_2'], n_days)

    # 交易统计
    pos = sub['position'].values
    switches = np.sum(np.diff(pos) != 0)
    cash_days = int(np.sum(pos == 0))
    hold1_days = int(np.sum(pos == 1))
    hold2_days = int(np.sum(pos == 2))
    hold3_days = int(np.sum(pos == 3))

    # 总手续费
    total_fee = sub['trade_cost'].sum()

    results[name] = {
        'start_date': sub['date'].iloc[0].strftime('%Y-%m-%d'),
        'end_date': sub['date'].iloc[-1].strftime('%Y-%m-%d'),
        'n_days': n_days,
        'strat_total': strat_total,
        'bh1_total': bh1_total,
        'bh2_total': bh2_total,
        'strat_ann': strat_ann,
        'bh1_ann': bh1_ann,
        'bh2_ann': bh2_ann,
        'strat_mdd': strat_mdd,
        'bh1_mdd': bh1_mdd,
        'bh2_mdd': bh2_mdd,
        'strat_sharpe': strat_sharpe,
        'bh1_sharpe': bh1_sharpe,
        'bh2_sharpe': bh2_sharpe,
        'switches': int(switches),
        'cash_days': cash_days,
        'hold1_days': hold1_days,
        'hold2_days': hold2_days,
        'hold3_days': hold3_days,
        'cash_pct': cash_days / n_days,
        'hold1_pct': hold1_days / n_days,
        'hold2_pct': hold2_days / n_days,
        'hold3_pct': hold3_days / n_days,
        'total_fee': float(total_fee),
    }

# ============ 7. 打印结果 ============
print("\n" + "="*95)
print("MA20轮动策略 V2 回测结果（叠加中证红利全收益 + 手续费万分之二/单边）")
print("="*95)
print(f"策略规则: 买入因子=收盘/MA20-1")
print(f"  bf更高者持有 | 两者bf均<0时持有中证红利全收益(无数据时空仓)")
print(f"  次日开盘执行 | 手续费: 买入0.02%+卖出0.02%=切换0.04%")

for name in ['近10年', '近5年', '近3年', '近1年']:
    r = results[name]
    if r is None:
        print(f"\n{name}: 数据不足")
        continue
    print(f"\n{'─'*75}")
    print(f"  {name}  ({r['start_date']} ~ {r['end_date']}, {r['n_days']}个交易日)")
    print(f"{'─'*75}")
    print(f"  {'指标':<16} {'轮动策略':>14} {'上证50持有':>14} {'创业板50持有':>14}")
    print(f"  {'总收益率':<14} {r['strat_total']:>13.2%} {r['bh1_total']:>13.2%} {r['bh2_total']:>13.2%}")
    print(f"  {'年化收益率':<13} {r['strat_ann']:>13.2%} {r['bh1_ann']:>13.2%} {r['bh2_ann']:>13.2%}")
    print(f"  {'最大回撤':<15} {r['strat_mdd']:>13.2%} {r['bh1_mdd']:>13.2%} {r['bh2_mdd']:>13.2%}")
    print(f"  {'夏普比率':<15} {r['strat_sharpe']:>14.2f} {r['bh1_sharpe']:>14.2f} {r['bh2_sharpe']:>14.2f}")
    print(f"  交易切换次数: {r['switches']}  |  总手续费成本: {r['total_fee']:.2%}")
    print(f"  持仓分布: 上证50 {r['hold1_pct']:.1%} | 创业板50 {r['hold2_pct']:.1%} | 红利 {r['hold3_pct']:.1%} | 空仓 {r['cash_pct']:.1%}")

# ============ 8. 导出数据 ============
nav_data = df[['date', 'strat_nav', 'bh_1_nav', 'bh_2_nav']].copy()
nav_data['date'] = nav_data['date'].dt.strftime('%Y-%m-%d')

full_nav = {
    'dates': nav_data['date'].tolist(),
    'strat': [round(x, 4) for x in nav_data['strat_nav'].tolist()],
    'bh1': [round(x, 4) for x in nav_data['bh_1_nav'].tolist()],
    'bh2': [round(x, 4) for x in nav_data['bh_2_nav'].tolist()],
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
    }

# 持仓时间序列（用于可视化）
pos_data = df[['date', 'position']].copy()
pos_data['date'] = pos_data['date'].dt.strftime('%Y-%m-%d')

output = {
    'results': {k: {kk: (vv if not isinstance(vv, (np.floating, np.integer)) else float(vv))
                     for kk, vv in v.items()} for k, v in results.items() if v is not None},
    'full_nav': full_nav,
    'period_navs': period_navs,
    'div_start_date': df[df['open_3'].notna()]['date'].iloc[0].strftime('%Y-%m-%d'),
}

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v2_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)

print(f"\n\n中证红利全收益指数数据起始: {output['div_start_date']}")
print("数据已导出到 backtest_v2_data.json")
