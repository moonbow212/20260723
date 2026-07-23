# -*- coding: utf-8 -*-
"""V14 (5%/4%阈值) 近1年操作明细生成器
在V8八指数轮动基础上加5%/4%回撤熔断：
- 策略净值从cummax回撤>5% → 强制转国债
- 回撤<4%时解除熔断，恢复V8原始信号
- 次日开盘价执行 | 万分之二手续费/单边
"""
import pandas as pd
import numpy as np
import json
import os
from functools import reduce

FEE = 0.0002
DD_TRIGGER = 0.05   # 5%触发
DD_RELEASE = 0.04   # 4%解除

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

# V8原始信号
def get_signal(row):
    ratios = [row[f'ratio_{i}'] for i in stock_ids]
    if all(r < 1 for r in ratios):
        return bond_id
    bfs = {i: row[f'bf_{i}'] for i in stock_ids}
    return max(bfs, key=bfs.get)
df['signal'] = df.apply(get_signal, axis=1)
df['raw_position'] = df['signal'].shift(1)
df.loc[df.index[0], 'raw_position'] = 0

# 收益
for i in all_ids:
    df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
last_idx = df.index[-1]
for i in all_ids:
    df[f'ret_{i}'] = np.nan
    mask = df[f'open_{i}_next'].notna()
    df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
    df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

# V8原始策略收益
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
df['raw_cummax'] = df['raw_strat_nav'].cummax()
df['raw_dd'] = df['raw_strat_nav'] / df['raw_cummax'] - 1

# ========== 应用5%/4%熔断 ==========
in_cb = False
final_position = []
cb_events = []
cb_status = []  # 每日熔断状态

for idx, row in df.iterrows():
    sig = int(row['raw_position'])
    dd = row['raw_dd']
    if not in_cb:
        if dd < -DD_TRIGGER and sig != bond_id:
            in_cb = True
            cb_events.append({'date': row['date'].strftime('%Y-%m-%d'),
                              'event':'TRIGGER', 'dd': float(dd),
                              'from': names[sig], 'to': names[bond_id]})
            final_position.append(bond_id)
            cb_status.append('TRIGGERED')
        else:
            final_position.append(sig)
            cb_status.append('NORMAL')
    else:
        if dd > -DD_RELEASE:
            in_cb = False
            cb_events.append({'date': row['date'].strftime('%Y-%m-%d'),
                              'event':'RELEASE', 'dd': float(dd),
                              'from': names[bond_id], 'to': names[sig]})
            final_position.append(sig)
            cb_status.append('RELEASED')
        else:
            final_position.append(bond_id)
            cb_status.append('IN_CB')

df['position'] = final_position
df['cb_status'] = cb_status

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

# 策略收益和净值
def get_strat_ret(row):
    pos = int(row['position'])
    gross = row[f'ret_{pos}'] if pos in all_ids else 0.0
    return (1 + gross) * (1 - row['trade_cost']) - 1
df['strat_ret'] = df.apply(get_strat_ret, axis=1)
df['strat_nav'] = (1 + df['strat_ret']).cumprod()

# ============ 输出操作明细 ============
switches = []
for i in range(len(df)):
    pos = int(df['position'].iloc[i])
    prev_pos = int(df['prev_position'].iloc[i])
    if pos != prev_pos:
        row = df.iloc[i]
        cb = row['cb_status']
        # 判断切换类型
        if cb == 'TRIGGERED':
            switch_type = '熔断触发'
            reason = f"回撤{row['raw_dd']*100:.2f}%>{DD_TRIGGER*100:.0f}%，强制转国债"
        elif cb == 'RELEASED':
            switch_type = '熔断解除'
            reason = f"回撤{row['raw_dd']*100:.2f}%<{DD_RELEASE*100:.0f}%，恢复V8信号"
        elif prev_pos == 0:
            switch_type = '建仓'
            reason = f"建仓{names[pos]}"
        elif pos == bond_id:
            switch_type = '避险'
            reason = '全部跌破MA20，避险转国债'
        else:
            switch_type = '轮动'
            reason = f"{names[prev_pos]}→{names[pos]}（bf最高）"

        # 决策依据bf：T日持仓由T-1日信号决定，故切换明细展示前一日收盘的bf
        if i > 0:
            prev_row = df.iloc[i-1]
            decision_bf = {names[j]: round(float(prev_row[f'bf_{j}']), 4) for j in stock_ids}
        else:
            decision_bf = {names[j]: 0.0 for j in stock_ids}
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
            'bf_values': decision_bf,
            'top_bf': names[pos] if pos in stock_ids else names[bond_id],
            'raw_dd': float(row['raw_dd']),
            'cb_status': cb,
            'switch_type': switch_type,
            'reason': reason,
            'raw_signal': names[int(row['signal'])],
        }
        switches.append(rec)

# 区间收益率
for k in range(len(switches)):
    if k == 0:
        switches[k]['period_ret'] = None
    else:
        switches[k]['period_ret'] = switches[k]['nav_before'] / switches[k-1]['nav_after'] - 1
last_period_ret = float(df['strat_nav'].iloc[-1] / switches[-1]['nav_after'] - 1)

# 统计
total_switches = len(switches)
total_fee = float(df['trade_cost'].sum())
n_days = len(df)
strat_total = df['strat_nav'].iloc[-1] - 1
strat_mdd = float(((df['strat_nav'] - df['strat_nav'].cummax())/df['strat_nav'].cummax()).min())
strat_sharpe = float(np.sqrt(252)*df['strat_ret'].mean()/df['strat_ret'].std()) if df['strat_ret'].std() > 0 else 0

# 持仓分布
hold_counts = {i: int((df['position'] == i).sum()) for i in all_ids}
hold_counts[0] = int((df['position'] == 0).sum())

# 切换类型统计
from collections import Counter
type_counts = Counter(s['switch_type'] for s in switches)

# 熔断事件统计
cb_triggers = [s for s in switches if s['cb_status'] == 'TRIGGERED']
cb_releases = [s for s in switches if s['cb_status'] == 'RELEASED']
cb_days = int((df['cb_status'].isin(['TRIGGERED', 'IN_CB'])).sum())

print(f"\n=== V14 (5%/4%) 近1年操作明细 ===")
print(f"期间: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {n_days}天")
print(f"总收益: {strat_total:.2%}, 年化: {(1+strat_total)**(252/n_days)-1:.2%}")
print(f"夏普: {strat_sharpe:.2f}, 最大回撤: {strat_mdd:.2%}")
print(f"总切换: {total_switches}次, 累计手续费: {total_fee:.2%}")
print(f"熔断事件: 触发{len(cb_triggers)}次, 解除{len(cb_releases)}次, 熔断天数{cb_days} ({cb_days/n_days:.1%})")
print(f"切换类型: {dict(type_counts)}")

print("\n=== 切换明细 ===")
for idx, s in enumerate(switches):
    pr = s['period_ret']
    pr_str = f"{pr:+.2%}" if pr is not None else "—"
    print(f"{idx+1:2d}. {s['date']} | {s['from']}→{s['to']} | {s['switch_type']} | "
          f"回撤{s['raw_dd']*100:+.2f}% | 区间收益{pr_str} | 净值{s['nav_after']:.4f}")

# 导出JSON
output = {
    'period': '近1年',
    'strategy': 'V14 (5%/4%阈值熔断)',
    'dd_trigger': DD_TRIGGER,
    'dd_release': DD_RELEASE,
    'start_date': df['date'].iloc[0].strftime('%Y-%m-%d'),
    'end_date': df['date'].iloc[-1].strftime('%Y-%m-%d'),
    'n_days': n_days,
    'strat_total': strat_total,
    'strat_ann': (1+strat_total)**(252/n_days)-1,
    'strat_mdd': strat_mdd,
    'strat_sharpe': strat_sharpe,
    'total_switches': total_switches,
    'total_fee': total_fee,
    'last_period_ret': last_period_ret,
    'hold_pct': {names[i]: hold_counts[i]/n_days for i in all_ids + [0]},
    'switches': switches,
    'cb_events': cb_events,
    'cb_trigger_count': len(cb_triggers),
    'cb_release_count': len(cb_releases),
    'cb_days': cb_days,
    'cb_pct': cb_days/n_days,
    'type_counts': dict(type_counts),
    'daily_records': [],
}
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
        'raw_dd': round(float(row['raw_dd']), 4),
        'raw_nav': round(float(row['raw_strat_nav']), 4),
        'cb_status': row['cb_status'],
    })

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_detail_1y.json','w',encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)
print(f"\n数据已导出到 v14_detail_1y.json")
