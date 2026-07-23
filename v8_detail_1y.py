# -*- coding: utf-8 -*-
"""V8近1年操作明细生成器"""
import pandas as pd
import numpy as np
import json
from functools import reduce

FEE = 0.0002

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
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债',0:'空仓'}

dfs = {}
for i, path in files.items():
    d = pd.read_csv(path, sep='\t', encoding='gbk')
    d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
    d = d[['date','开盘','收盘']].rename(columns={'开盘':f'open_{i}','收盘':f'close_{i}'})
    for c in [f'open_{i}',f'close_{i}']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    dfs[i] = d.dropna()

# 近1年：8股票+国债
stock_ids = [1,2,3,4,5,6,7,8]
bond_id = 9
all_ids = stock_ids + [bond_id]

df = reduce(lambda a,b: pd.merge(a,b,on='date',how='inner'), [dfs[i] for i in all_ids])
df = df.sort_values('date').reset_index(drop=True)

last_date = df['date'].max()
start_date = last_date - pd.DateOffset(years=1)
df = df[(df['date'] >= start_date) & (df['date'] <= last_date)].reset_index(drop=True)

# MA20和买入因子
for i in stock_ids:
    df[f'ma20_{i}'] = df[f'close_{i}'].rolling(20).mean()
    df[f'bf_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}'] - 1
    df[f'ratio_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}']
df = df.dropna(subset=[f'ma20_{i}' for i in stock_ids]).reset_index(drop=True)

# 信号
def get_signal(row):
    ratios = [row[f'ratio_{i}'] for i in stock_ids]
    if all(r < 1 for r in ratios):
        return bond_id
    bfs = {i: row[f'bf_{i}'] for i in stock_ids}
    return max(bfs, key=bfs.get)
df['signal'] = df.apply(get_signal, axis=1)
df['position'] = df['signal'].shift(1)
df.loc[df.index[0], 'position'] = 0

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

# 策略收益和净值
def get_strat_ret(row):
    pos = int(row['position'])
    gross = row[f'ret_{pos}'] if pos in all_ids else 0.0
    return (1 + gross) * (1 - row['trade_cost']) - 1
df['strat_ret'] = df.apply(get_strat_ret, axis=1)
df['strat_nav'] = (1 + df['strat_ret']).cumprod()

# ============ 输出操作明细 ============
# 提取切换记录
switches = []
for i in range(len(df)):
    pos = int(df['position'].iloc[i])
    prev_pos = int(df['prev_position'].iloc[i])
    if pos != prev_pos:
        row = df.iloc[i]
        rec = {
            'date': row['date'].strftime('%Y-%m-%d'),
            'from': names[prev_pos],
            'to': names[pos],
            'from_id': prev_pos,
            'to_id': pos,
            'cost': float(row['trade_cost']),
            'nav_before': float(df['strat_nav'].iloc[i-1]) if i > 0 else 1.0,
            'nav_after': float(row['strat_nav']),
            'ret': float(row['strat_ret']),
            'bf_values': {names[j]: round(float(row[f'bf_{j}']), 4) for j in stock_ids},
            'top_bf': names[pos] if pos in stock_ids else names[bond_id],
            'reason': '全部跌破MA20，避险转国债' if pos == bond_id else (f'建仓{names[pos]}' if prev_pos == 0 else f'{names[prev_pos]}→{names[pos]}'),
        }
        switches.append(rec)

# 计算每次调仓的区间收益率（从上次调仓后到本次调仓前，持有上次买入资产的累计收益）
for k in range(len(switches)):
    if k == 0:
        switches[k]['period_ret'] = None  # 第一次调仓前为空仓
    else:
        switches[k]['period_ret'] = switches[k]['nav_before'] / switches[k-1]['nav_after'] - 1

# 最后一段（最后一次调仓后至今）
last_period_ret = float(df['strat_nav'].iloc[-1] / switches[-1]['nav_after'] - 1)

# 统计
total_switches = len(switches)
total_fee = float(df['trade_cost'].sum())
n_days = len(df)
strat_total = df['strat_nav'].iloc[-1] - 1

# 持仓分布
hold_counts = {i: int((df['position'] == i).sum()) for i in all_ids}
hold_counts[0] = int((df['position'] == 0).sum())

print(f"近1年操作明细: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {n_days}天")
print(f"总切换: {total_switches}次, 累计手续费: {total_fee:.2%}, 总收益: {strat_total:.2%}")
print(f"持仓分布: " + " ".join(f"{names[i]}{hold_counts[i]/n_days:.0%}" for i in all_ids + [0]))

# 输出每次切换详情
print("\n=== 每次切换明细 ===")
for idx, s in enumerate(switches):
    bf_str = " ".join(f"{k}:{v}" for k, v in s['bf_values'].items())
    pr = s['period_ret']
    pr_str = f"{pr:+.2%}" if pr is not None else "—"
    print(f"{idx+1}. {s['date']} | {s['from']}→{s['to']} | 费{s['cost']:.4f} | 净值{s['nav_after']:.4f} | 区间收益{pr_str} | {bf_str}")
print(f"最后一段: 持有{switches[-1]['to']}至今 | 区间收益{last_period_ret:+.2%}")

# 导出JSON
output = {
    'period': '近1年',
    'start_date': df['date'].iloc[0].strftime('%Y-%m-%d'),
    'end_date': df['date'].iloc[-1].strftime('%Y-%m-%d'),
    'n_days': n_days,
    'strat_total': strat_total,
    'strat_ann': (1+strat_total)**(252/n_days)-1,
    'strat_mdd': float(((df['strat_nav'] - df['strat_nav'].cummax())/df['strat_nav'].cummax()).min()),
    'strat_sharpe': float(np.sqrt(252)*df['strat_ret'].mean()/df['strat_ret'].std()),
    'total_switches': total_switches,
    'total_fee': total_fee,
    'last_period_ret': last_period_ret,
    'hold_pct': {names[i]: hold_counts[i]/n_days for i in all_ids + [0]},
    'switches': switches,
    'daily_records': [],
}
# 每日记录（精简）
for i in range(len(df)):
    row = df.iloc[i]
    pos = int(row['position'])
    output['daily_records'].append({
        'date': row['date'].strftime('%Y-%m-%d'),
        'position': names[pos],
        'pos_id': pos,
        'is_switch': pos != int(row['prev_position']),
        'ret': round(float(row['strat_ret']), 4),
        'nav': round(float(row['strat_nav']), 4),
        'cost': round(float(row['trade_cost']), 5),
        'bf': {names[j]: round(float(row[f'bf_{j}']), 4) for j in stock_ids},
        'signal': names[int(row['signal'])],
    })

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v8_detail_1y.json','w',encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)
print(f"\n数据已导出到 v8_detail_1y.json")
print(f"切换明细共 {len(switches)} 条, 每日记录共 {len(output['daily_records'])} 条")
