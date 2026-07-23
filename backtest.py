# -*- coding: utf-8 -*-
"""
MA20轮动策略回测
策略规则：
  买入因子 = 当日收盘价 / 当日MA20 - 1  （即收盘价相对MA20的偏离度）
  - 每日收盘后计算两个指数的买入因子
  - 如果两个指数的 close/MA20 都 < 1（即都低于MA20，买入因子都<0）→ 清仓（持现金）
  - 否则 → 持有买入因子更高的那个指数
  - 次日开盘价执行买入/切换

注：用户说"买入因子都低于1就清仓"，按公式买入因子=close/MA20-1，
    "低于1"字面意思是close/MA20<2（几乎永远满足，不合理）。
    合理理解：close/MA20这个比值低于1（即跌破MA20）时清仓，
    等价于买入因子<0时清仓。本回测采用此合理解释。
"""

import pandas as pd
import numpy as np
import json

# ============ 1. 读取数据 ============
df1 = pd.read_csv('C:/Users/wbl/Desktop/上证50.xlsx', sep='\t', encoding='gbk')
df2 = pd.read_csv('C:/Users/wbl/Desktop/创业板50.xlsx', sep='\t', encoding='gbk')

# 解析日期 "2003-12-31,三" -> 2003-12-31
df1['date'] = pd.to_datetime(df1['时间'].str.split(',').str[0])
df2['date'] = pd.to_datetime(df2['时间'].str.split(',').str[0])

# 只保留需要的列
df1 = df1[['date', '开盘', '收盘']].rename(columns={'开盘': 'open_1', '收盘': 'close_1'})
df2 = df2[['date', '开盘', '收盘']].rename(columns={'开盘': 'open_2', '收盘': 'close_2'})

# 转数值
for c in ['open_1', 'close_1']:
    df1[c] = pd.to_numeric(df1[c], errors='coerce')
for c in ['open_2', 'close_2']:
    df2[c] = pd.to_numeric(df2[c], errors='coerce')
df1 = df1.dropna()
df2 = df2.dropna()

# 内连接合并（两个指数都有数据的日期）
df = pd.merge(df1, df2, on='date', how='inner').sort_values('date').reset_index(drop=True)
print(f"合并后总交易日: {len(df)}")
print(f"数据区间: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}")

# ============ 2. 计算MA20和买入因子 ============
df['ma20_1'] = df['close_1'].rolling(20).mean()
df['ma20_2'] = df['close_2'].rolling(20).mean()

# 买入因子 = 收盘价/MA20 - 1
df['bf_1'] = df['close_1'] / df['ma20_1'] - 1
df['bf_2'] = df['close_2'] / df['ma20_2'] - 1

# close/MA20 比值（用于清仓判断）
df['ratio_1'] = df['close_1'] / df['ma20_1']
df['ratio_2'] = df['close_2'] / df['ma20_2']

df = df.dropna().reset_index(drop=True)
print(f"MA20计算后交易日: {len(df)}")

# ============ 3. 生成交易信号 ============
# signal[t] 在收盘时确定：
#   两个 ratio 都 < 1 → 0 (清仓/现金)
#   bf_1 >= bf_2 → 1 (持有上证50)
#   否则 → 2 (持有创业板50)
def get_signal(row):
    if row['ratio_1'] < 1 and row['ratio_2'] < 1:
        return 0
    elif row['bf_1'] >= row['bf_2']:
        return 1
    else:
        return 2

df['signal'] = df.apply(get_signal, axis=1)

# position[t] = signal[t-1]，即昨天收盘的信号，今天开盘执行
df['position'] = df['signal'].shift(1)
df.loc[df.index[0], 'position'] = 0  # 第一天无信号，持现金

# ============ 4. 计算每日收益（开盘到开盘）============
# 持仓position[t]决定当天open[t]到open[t+1]的收益
# 最后一天用 close[last]/open[last] - 1（mark to close）
df['open_1_next'] = df['open_1'].shift(-1)
df['open_2_next'] = df['open_2'].shift(-1)

# 指数1的日收益（open-to-open，最后一天open-to-close）
df['ret_1'] = np.nan
mask = df['open_1_next'].notna()
df.loc[mask, 'ret_1'] = df.loc[mask, 'open_1_next'] / df.loc[mask, 'open_1'] - 1
# 最后一天
last_idx = df.index[-1]
df.loc[last_idx, 'ret_1'] = df.loc[last_idx, 'close_1'] / df.loc[last_idx, 'open_1'] - 1

# 指数2的日收益
df['ret_2'] = np.nan
df.loc[mask, 'ret_2'] = df.loc[mask, 'open_2_next'] / df.loc[mask, 'open_2'] - 1
df.loc[last_idx, 'ret_2'] = df.loc[last_idx, 'close_2'] / df.loc[last_idx, 'open_2'] - 1

# 策略日收益
def get_strat_ret(row):
    if row['position'] == 1:
        return row['ret_1']
    elif row['position'] == 2:
        return row['ret_2']
    else:
        return 0.0

df['strat_ret'] = df.apply(get_strat_ret, axis=1)

# ============ 5. 计算净值和指标 ============
df['strat_nav'] = (1 + df['strat_ret']).cumprod()
df['bh_1_nav'] = (1 + df['ret_1']).cumprod()
df['bh_2_nav'] = (1 + df['ret_2']).cumprod()

# 最大回撤
def max_drawdown(nav):
    peak = nav.cummax()
    dd = (nav - peak) / peak
    return dd.min()

def annualized_ret(total_ret, days):
    if days <= 0:
        return 0
    return (1 + total_ret) ** (252 / days) - 1

def sharpe(daily_rets, days):
    if daily_rets.std() == 0 or days == 0:
        return 0
    return np.sqrt(252) * daily_rets.mean() / daily_rets.std()

# ============ 6. 分时段统计 ============
end_date = df['date'].max()
print(f"\n数据结束日期: {end_date.date()}")

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

    # 重置净值起点
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
    cash_days = np.sum(pos == 0)
    hold1_days = np.sum(pos == 1)
    hold2_days = np.sum(pos == 2)

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
        'cash_days': int(cash_days),
        'hold1_days': int(hold1_days),
        'hold2_days': int(hold2_days),
        'cash_pct': cash_days / n_days,
        'hold1_pct': hold1_days / n_days,
        'hold2_pct': hold2_days / n_days,
    }

# ============ 7. 打印结果 ============
print("\n" + "="*90)
print("MA20轮动策略回测结果")
print("="*90)
print(f"策略规则: 买入因子=收盘/MA20-1，持有因子更高者，两者均跌破MA20则清仓")
print(f"执行方式: 信号日收盘决策，次日开盘价执行")
print(f"清仓条件: 两个指数 close/MA20 均 < 1（均跌破MA20）")

for name in ['近10年', '近5年', '近3年', '近1年']:
    r = results[name]
    if r is None:
        print(f"\n{name}: 数据不足")
        continue
    print(f"\n{'─'*70}")
    print(f"  {name}  ({r['start_date']} ~ {r['end_date']}, {r['n_days']}个交易日)")
    print(f"{'─'*70}")
    print(f"  {'指标':<16} {'轮动策略':>14} {'上证50持有':>14} {'创业板50持有':>14}")
    print(f"  {'总收益率':<14} {r['strat_total']:>13.2%} {r['bh1_total']:>13.2%} {r['bh2_total']:>13.2%}")
    print(f"  {'年化收益率':<13} {r['strat_ann']:>13.2%} {r['bh1_ann']:>13.2%} {r['bh2_ann']:>13.2%}")
    print(f"  {'最大回撤':<15} {r['strat_mdd']:>13.2%} {r['bh1_mdd']:>13.2%} {r['bh2_mdd']:>13.2%}")
    print(f"  {'夏普比率':<15} {r['strat_sharpe']:>14.2f} {r['bh1_sharpe']:>14.2f} {r['bh2_sharpe']:>14.2f}")
    print(f"  交易切换次数: {r['switches']}")
    print(f"  持仓分布: 上证50 {r['hold1_pct']:.1%} | 创业板50 {r['hold2_pct']:.1%} | 空仓 {r['cash_pct']:.1%}")

# ============ 8. 导出数据供图表使用 ============
# 净值序列（按日期）
nav_data = df[['date', 'strat_nav', 'bh_1_nav', 'bh_2_nav']].copy()
nav_data['date'] = nav_data['date'].dt.strftime('%Y-%m-%d')

# 全区间净值（用于画图）
full_nav = {
    'dates': nav_data['date'].tolist(),
    'strat': [round(x, 4) for x in nav_data['strat_nav'].tolist()],
    'bh1': [round(x, 4) for x in nav_data['bh_1_nav'].tolist()],
    'bh2': [round(x, 4) for x in nav_data['bh_2_nav'].tolist()],
}

# 各时段净值（重置起点）
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

# 持仓分布
position_data = df[['date', 'position']].copy()
position_data['date'] = position_data['date'].dt.strftime('%Y-%m-%d')

# 导出JSON
output = {
    'results': {k: {kk: (vv if not isinstance(vv, (np.floating, np.integer)) else float(vv))
                     for kk, vv in v.items()} for k, v in results.items() if v is not None},
    'full_nav': full_nav,
    'period_navs': period_navs,
}

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)

print("\n\n数据已导出到 backtest_data.json")
