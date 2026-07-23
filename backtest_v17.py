# -*- coding: utf-8 -*-
"""
MA20轮动策略 V17 —— 阈值网格搜索
在V14基础上同时加入中证2000 + 3个海外指数 = 12股+债
搜索最优触发/解除阈值组合，与V14(8股,5%/4%)对比

标的池:
  原8股: 上证50/创业板50/纳指100/沪深300/中证500/中证1000/标普500/科创50
  新增:  中证2000(ID=13) / 日经225(ID=10) / 越南胡志明(ID=11) / 英国富时100(ID=12)
  债券:  国债(ID=9)

处理方式:
  - 原8股+国债: inner join (按主日历算MA20/bf)
  - 中证2000: A股日历，按自己日历算MA20/bf，left join (近20年前7年缺失→NaN不选)
  - 3海外指数: 各自日历算MA20/bf，left join (缺失日NaN不选)
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

names = {0:'空仓',1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',
         7:'标普500',8:'科创50',9:'国债',10:'日经225',11:'越南胡志明',12:'英国富时100',13:'中证2000'}

# 原9个标的 (GBK制表符分隔)
orig_files = {
    1: find_file('上证50'), 2: find_file('创业板50'), 3: find_file('纳斯达克100'),
    4: find_file('沪深300'), 5: find_file('中证500'), 6: find_file('中证1000'),
    7: find_file('标普500'), 8: find_file('科创50'), 9: find_file('国债'),
}

dfs = {}
for i, path in orig_files.items():
    d = pd.read_csv(path, sep='\t', encoding='gbk')
    d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
    d = d[['date','开盘','收盘']].rename(columns={'开盘':f'open_{i}','收盘':f'close_{i}'})
    for c in [f'open_{i}',f'close_{i}']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    dfs[i] = d.dropna()

# 中证2000 (GBK制表符分隔, ID=13)
path_zz2000 = find_file('中证2000')
d = pd.read_csv(path_zz2000, sep='\t', encoding='gbk')
d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
d = d[['date','开盘','收盘']].rename(columns={'开盘':f'open_13','收盘':f'close_13'})
for c in [f'open_13',f'close_13']:
    d[c] = pd.to_numeric(d[c], errors='coerce')
d = d.dropna().sort_values('date').reset_index(drop=True)
d['ma20_13'] = d['close_13'].rolling(20).mean()
d['bf_13'] = d['close_13'] / d['ma20_13'] - 1
d['ratio_13'] = d['close_13'] / d['ma20_13']
dfs[13] = d.dropna(subset=['ma20_13']).reset_index(drop=True)
print(f"  中证2000: {d['date'].min().date()} ~ {d['date'].max().date()}, {len(d)}行")

# 3个海外指数 (UTF-8 CSV, 价格含千分位逗号)
overseas_files = {
    10: 'C:/Users/wbl/Desktop/日经225指数历史数据 (4).csv',
    11: 'C:/Users/wbl/Desktop/越南胡志明指数历史数据.csv',
    12: 'C:/Users/wbl/Desktop/英国富时100指数历史数据.csv',
}
for i, path in overseas_files.items():
    d = pd.read_csv(path, encoding='utf-8')
    d['date'] = pd.to_datetime(d['日期'])
    for c in ['收盘','开盘']:
        d[c] = d[c].astype(str).str.replace(',','')
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d[['date','开盘','收盘']].rename(columns={'开盘':f'open_{i}','收盘':f'close_{i}'})
    d = d.dropna().sort_values('date').reset_index(drop=True)
    d[f'ma20_{i}'] = d[f'close_{i}'].rolling(20).mean()
    d[f'bf_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}'] - 1
    d[f'ratio_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}']
    dfs[i] = d.dropna(subset=[f'ma20_{i}']).reset_index(drop=True)
    print(f"  {names[i]}: {d['date'].min().date()} ~ {d['date'].max().date()}, {len(d)}行")

# 固定last_date保证与V14可比
last_date = pd.Timestamp('2026-07-17')
print(f"主日历最新日期(固定): {last_date.date()}")

# ============ 2. 时段配置 ============
# V17标的池 = 原标的 + 中证2000(13) + 海外(10,11,12)
STOCK_20Y_ORIG = [1, 3, 4, 6]
STOCK_10Y_ORIG = [1, 2, 3, 4, 5, 6, 7]
STOCK_RECENT_ORIG = [1, 2, 3, 4, 5, 6, 7, 8]
EXTRA = [10, 11, 12, 13]  # 海外3 + 中证2000
BOND = 9

STOCK_20Y_V17 = STOCK_20Y_ORIG + EXTRA
STOCK_10Y_V17 = STOCK_10Y_ORIG + EXTRA
STOCK_RECENT_V17 = STOCK_RECENT_ORIG + EXTRA

periods_config = {
    '近20年': (STOCK_20Y_V17, STOCK_20Y_ORIG, last_date - pd.DateOffset(years=20)),
    '近10年': (STOCK_10Y_V17, STOCK_10Y_ORIG, last_date - pd.DateOffset(years=10)),
    '近5年':  (STOCK_RECENT_V17, STOCK_RECENT_ORIG, last_date - pd.DateOffset(years=5)),
    '近3年':  (STOCK_RECENT_V17, STOCK_RECENT_ORIG, last_date - pd.DateOffset(years=3)),
    '近1年':  (STOCK_RECENT_V17, STOCK_RECENT_ORIG, last_date - pd.DateOffset(years=1)),
}

# ============ 3. 构建时段基础数据 ============
def build_period_data(stock_ids_v17, stock_ids_v14, bond_id, start_date, end_date):
    """构建V17数据：原标的inner join + 额外标的left join"""
    extra_ids = [i for i in stock_ids_v17 if i not in stock_ids_v14]
    orig_ids = stock_ids_v14 + [bond_id]

    # 原标的inner join
    df = reduce(lambda a,b: pd.merge(a,b,on='date',how='inner'), [dfs[i] for i in orig_ids])
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)

    # 原标的算ma20/bf
    for i in stock_ids_v14:
        df[f'ma20_{i}'] = df[f'close_{i}'].rolling(20).mean()
        df[f'bf_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}'] - 1
        df[f'ratio_{i}'] = df[f'close_{i}'] / df[f'ma20_{i}']
    df = df.dropna(subset=[f'ma20_{i}' for i in stock_ids_v14]).reset_index(drop=True)

    # 额外标的left join (已按自己日历算好ma20/bf)
    for i in extra_ids:
        sub = dfs[i][['date', f'open_{i}', f'close_{i}', f'ma20_{i}', f'bf_{i}', f'ratio_{i}']].copy()
        df = pd.merge(df, sub, on='date', how='left')

    all_ids_v17 = stock_ids_v17 + [bond_id]

    # V17信号 (12股, NaN跳过)
    def get_signal_v17(row):
        bfs = {}
        for i in stock_ids_v17:
            v = row.get(f'bf_{i}', np.nan)
            if pd.notna(v):
                bfs[i] = v
        if len(bfs) == 0:
            return bond_id
        if all(v < 0 for v in bfs.values()):
            return bond_id
        return max(bfs, key=bfs.get)

    # V14信号 (仅原标的)
    def get_signal_v14(row):
        ratios = [row[f'ratio_{i}'] for i in stock_ids_v14]
        if all(r < 1 for r in ratios):
            return bond_id
        bfs = {i: row[f'bf_{i}'] for i in stock_ids_v14}
        return max(bfs, key=bfs.get)

    df['signal_v17'] = df.apply(get_signal_v17, axis=1)
    df['signal_v14'] = df.apply(get_signal_v14, axis=1)

    # 收益: 所有标的按主日历算 open.shift(-1)/open-1
    for i in all_ids_v17:
        df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
    last_idx = df.index[-1]
    for i in all_ids_v17:
        df[f'ret_{i}'] = np.nan
        mask = df[f'open_{i}_next'].notna() & df[f'open_{i}'].notna()
        df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
        if pd.notna(df.loc[last_idx, f'open_{i}']) and pd.notna(df.loc[last_idx, f'close_{i}']):
            df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1
        df[f'ret_{i}'] = df[f'ret_{i}'].fillna(0)

    # V17原始信号持仓和净值 (无熔断)
    df['pos_v17_raw'] = df['signal_v17'].shift(1)
    df.loc[df.index[0], 'pos_v17_raw'] = 0
    df['prev_pos_v17_raw'] = df['pos_v17_raw'].shift(1)
    df.loc[df.index[0], 'prev_pos_v17_raw'] = df.loc[df.index[0], 'pos_v17_raw']

    # V14原始信号持仓和净值 (无熔断, =V8基线)
    df['pos_v14_raw'] = df['signal_v14'].shift(1)
    df.loc[df.index[0], 'pos_v14_raw'] = 0
    df['prev_pos_v14_raw'] = df['pos_v14_raw'].shift(1)
    df.loc[df.index[0], 'prev_pos_v14_raw'] = df.loc[df.index[0], 'pos_v14_raw']

    def get_ret(row, pos_col, prev_col, ids):
        pos = int(row[pos_col])
        gross = row[f'ret_{pos}'] if pos in ids else 0.0
        prev = int(row[prev_col])
        cost = 0.0
        if prev != pos:
            if prev in ids: cost += FEE
            if pos in ids: cost += FEE
        return (1 + gross) * (1 - cost) - 1

    df['ret_v17_raw'] = df.apply(get_ret, axis=1, args=('pos_v17_raw','prev_pos_v17_raw',all_ids_v17))
    df['ret_v14_raw'] = df.apply(get_ret, axis=1, args=('pos_v14_raw','prev_pos_v14_raw',all_ids_v17))
    df['nav_v17_raw'] = (1 + df['ret_v17_raw']).cumprod()
    df['nav_v14_raw'] = (1 + df['ret_v14_raw']).cumprod()

    # V17原始信号净值的回撤 (熔断判断基准)
    df['cummax_v17'] = df['nav_v17_raw'].cummax()
    df['dd_v17'] = df['nav_v17_raw'] / df['cummax_v17'] - 1

    return df, all_ids_v17, stock_ids_v17

print("\n构建基础数据...")
period_data = {}
for pname, (stocks_v17, stocks_v14, sd) in periods_config.items():
    df, all_ids, stocks_v17 = build_period_data(stocks_v17, stocks_v14, BOND, sd, last_date)
    period_data[pname] = {'df': df, 'all_ids': all_ids, 'stock_ids_v17': stocks_v17, 'stock_ids_v14': stocks_v14}
    print(f"  {pname}: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)}天, V17={len(stocks_v17)}股+债")

# ============ 4. 阈值网格搜索 ============
# 熔断函数
def apply_cb(df, dd_col, signal_col, bond_id, dd_trigger, dd_release):
    n = len(df)
    raw_pos = df[signal_col].shift(1).fillna(0).astype(int).values
    raw_dd = df[dd_col].values
    dates = df['date'].values
    in_cb = False
    final_pos = np.zeros(n, dtype=int)
    cb_count = 0
    for i in range(n):
        sig = int(raw_pos[i])
        dd = raw_dd[i]
        if not in_cb:
            if dd < -dd_trigger and sig != bond_id:
                in_cb = True
                cb_count += 1
                final_pos[i] = bond_id
            else:
                final_pos[i] = sig
        else:
            if dd > -dd_release:
                in_cb = False
                final_pos[i] = sig
            else:
                final_pos[i] = bond_id
    return final_pos, cb_count

def compute_metrics(df, pos, all_ids, bond_id):
    n = len(df)
    prev_pos = np.concatenate([[pos[0]], pos[:-1]])
    rets = np.zeros(n)
    for i in range(n):
        p = int(pos[i])
        gross = df[f'ret_{p}'].iloc[i] if p in all_ids else 0.0
        cost = 0.0
        if int(prev_pos[i]) != p:
            if int(prev_pos[i]) in all_ids: cost += FEE
            if p in all_ids: cost += FEE
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
    return {
        'total': float(total), 'ann': float(ann_ret), 'mdd': float(mdd_val),
        'sharpe': float(sharpe), 'switches': switches, 'cb_days': cb_days,
        'cb_pct': float(cb_pct), 'cb_events': 0,
    }

# 阈值组合
thresholds = [
    (0.03, 0.02), (0.03, 0.03),
    (0.04, 0.03), (0.04, 0.04),
    (0.05, 0.03), (0.05, 0.04), (0.05, 0.05),
    (0.06, 0.04), (0.06, 0.05), (0.06, 0.06),
    (0.07, 0.05), (0.07, 0.06), (0.07, 0.07),
    (0.08, 0.06), (0.08, 0.07),
]

print(f"\n阈值网格搜索: {len(thresholds)}个组合 × 5个时段")
print("=" * 100)

# 搜索
search_results = {}
for trig, rel in thresholds:
    key = f"{int(trig*100)}/{int(rel*100)}"
    search_results[key] = {}
    for pname in ['近20年','近10年','近5年','近3年','近1年']:
        pdat = period_data[pname]
        df = pdat['df']
        all_ids = pdat['all_ids']
        pos, cb_cnt = apply_cb(df, 'dd_v17', 'signal_v17', BOND, trig, rel)
        m = compute_metrics(df, pos, all_ids, BOND)
        m['cb_events'] = cb_cnt
        search_results[key][pname] = m

# 打印结果表
print(f"\n{'阈值':>8s} | {'近20年':>10s} | {'近10年':>10s} | {'近5年':>10s} | {'近3年':>10s} | {'近1年':>10s}")
print("-" * 80)
for key in search_results:
    vals = [search_results[key][p]['total']*100 for p in ['近20年','近10年','近5年','近3年','近1年']]
    print(f"{key:>8s} | {vals[0]:>9.1f}% | {vals[1]:>9.1f}% | {vals[2]:>9.1f}% | {vals[3]:>9.1f}% | {vals[4]:>9.1f}%")

# 找各时段最优
print("\n" + "=" * 100)
print("各时段最优阈值 (按总收益)")
print("=" * 100)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    best_key = max(search_results.keys(), key=lambda k: search_results[k][pname]['total'])
    best = search_results[best_key][pname]
    print(f"{pname}: 最优={best_key} | 总收益={best['total']*100:.1f}% | 年化={best['ann']*100:.2f}% | 回撤={best['mdd']*100:.2f}% | 夏普={best['sharpe']:.2f} | 熔断天%={best['cb_pct']*100:.1f}%")

# 综合排名 (各时段收益排名的平均)
print("\n" + "=" * 100)
print("综合排名 (各时段收益排名平均值, 越小越好)")
print("=" * 100)
rank_sum = {k: 0 for k in search_results}
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    sorted_keys = sorted(search_results.keys(), key=lambda k: -search_results[k][pname]['total'])
    for rank, k in enumerate(sorted_keys):
        rank_sum[k] += rank + 1

for k in sorted(rank_sum.keys(), key=lambda x: rank_sum[x]):
    avg_rank = rank_sum[k] / 5
    vals = [search_results[k][p]['total']*100 for p in ['近20年','近10年','近5年','近3年','近1年']]
    print(f"{k:>8s} | 平均排名={avg_rank:.1f} | 近20年={vals[0]:.1f}% 近10年={vals[1]:.1f}% 近5年={vals[2]:.1f}% 近3年={vals[3]:.1f}% 近1年={vals[4]:.1f}%")

# ============ 5. V14(8股,5%/4%)对比基准 ============
# 从v14_periods_data.json读取V14结果
v14_ref = {}
try:
    with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_periods_data.json', 'r', encoding='utf-8') as f:
        v14_data = json.load(f)
    for pname in ['近20年','近10年','近5年','近3年','近1年']:
        if pname in v14_data.get('results', {}):
            v14_ref[pname] = v14_data['results'][pname]['v14']
            print(f"\nV14基准 {pname}: 总收益={v14_ref[pname]['total']*100:.1f}% 年化={v14_ref[pname]['ann']*100:.2f}% 回撤={v14_ref[pname]['mdd']*100:.2f}%")
except Exception as e:
    print(f"读取V14基准失败: {e}")

# ============ 6. V17最优 vs V14对比 ============
print("\n" + "=" * 100)
print("V17最优阈值 vs V14(8股,5%/4%) 对比")
print("=" * 100)
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    best_key = max(search_results.keys(), key=lambda k: search_results[k][pname]['total'])
    v17_best = search_results[best_key][pname]
    v14 = v14_ref.get(pname, {})
    if v14:
        diff = v17_best['total'] - v14['total']
        win = "V17胜" if diff > 0 else "V14胜"
        print(f"{pname}: V17最优[{best_key}] {v17_best['total']*100:.1f}% vs V14[5/4] {v14['total']*100:.1f}% → {win} ({diff*100:+.1f}pp)")

# ============ 7. 导出JSON ============
def clean(o):
    if isinstance(o, (np.floating, np.integer)): return float(o)
    if isinstance(o, np.ndarray): return o.tolist()
    return o

output = {
    'config': {'fee': FEE, 'bond_id': BOND},
    'names': names,
    'extra_names': [names[i] for i in EXTRA],
    'thresholds': [[t, r] for t, r in thresholds],
    'search_results': {k: {p: {kk: clean(vv) for kk, vv in v.items()} for p, v in v2.items()} for k, v2 in search_results.items()},
    'v14_ref': {p: {kk: clean(vv) for kk, vv in v.items()} for p, v in v14_ref.items()} if v14_ref else {},
    'rank_sum': {k: float(v) for k, v in rank_sum.items()},
}

with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v17_threshold_search.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)
print("\n数据已导出到 v17_threshold_search.json")
