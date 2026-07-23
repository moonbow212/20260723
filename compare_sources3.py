"""深入分析同花顺 vs akshare数据差异对V14策略的影响"""
import pandas as pd
import numpy as np
import os, warnings
warnings.filterwarnings('ignore')

FEE = 0.0002
DD_TRIGGER = 0.05
DD_RELEASE = 0.04
STOCK_ALL = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}

def load_ths(name):
    path = f'C:/Users/wbl/Desktop/{name}.xlsx'
    if not os.path.exists(path):
        return None
    try:
        d = pd.read_csv(path, sep='\t', encoding='gbk')
    except:
        return None
    if '开盘' not in d.columns or '收盘' not in d.columns:
        return None
    d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
    d = d[['date','开盘','收盘']].rename(columns={'开盘':'open','收盘':'close'})
    for c in ['open','close']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d.dropna().sort_values('date').reset_index(drop=True)
    return d

def load_csv(i, name):
    d = pd.read_csv(f'data/{i}_{name}.csv', parse_dates=['date'])
    d = d[['date','open','close']].sort_values('date').reset_index(drop=True)
    return d

# 加载所有数据
print('=== 1. 各标的数据对比 ===')
ths_dfs = {}
csv_dfs = {}
for i in STOCK_ALL + [BOND]:
    name = names[i]
    csv_dfs[i] = load_csv(i, name)
    ths_d = load_ths(name)
    if ths_d is not None:
        ths_dfs[i] = ths_d
        # 对比日收益率
        merged = pd.merge(ths_d[['date','open','close']], csv_dfs[i][['date','open','close']], on='date', suffixes=('_ths','_csv'))
        merged['ret_ths'] = merged['close_ths'].pct_change()
        merged['ret_csv'] = merged['close_csv'].pct_change()
        diff = (merged['ret_ths'] - merged['ret_csv']).abs()
        max_diff_date = merged.loc[diff.idxmax(), 'date'].date() if diff.max() > 0 else 'N/A'
        print(f'  {name}: 同花顺{ths_d["date"].iloc[0].date()}~{ths_d["date"].iloc[-1].date()}({len(ths_d)}条) vs akshare{csv_dfs[i]["date"].iloc[0].date()}~{csv_dfs[i]["date"].iloc[-1].date()}({len(csv_dfs[i])}条)')
        print(f'    日收益率差异: 平均{diff.mean():.8f}, 最大{diff.max():.8f}({max_diff_date}), 差异>0.01%的天数: {(diff > 0.0001).sum()}')
        # 价格比值
        ratio_last = merged['close_ths'].iloc[-1] / merged['close_csv'].iloc[-1]
        ratio_first = merged['close_ths'].iloc[0] / merged['close_csv'].iloc[0]
        print(f'    价格比值: 首{ratio_first:.6f}, 末{ratio_last:.6f}, 变化{ratio_last/ratio_first-1:+.6f}')
    else:
        print(f'  {name}: 同花顺文件不可用, akshare{csv_dfs[i]["date"].iloc[0].date()}~{csv_dfs[i]["date"].iloc[-1].date()}({len(csv_dfs[i])}条)')

# ==== 用混合数据源运行回测 ====
# 方案D: 同花顺可用的标的用同花顺，不可用的用akshare（模拟上次v14_yearly_all_v2的情况）
print()
print('=== 2. 混合数据源回测（模拟上次v14_yearly_all_v2） ===')

def run_backtest(dfs_src, end_date=None):
    dfs = {}
    for i in STOCK_ALL + [BOND]:
        d = dfs_src[i].copy()
        if i != BOND:
            d['ma20'] = d['close'].rolling(20).mean()
            d['bf'] = d['close'] / d['ma20'] - 1
            d['ratio'] = d['close'] / d['ma20']
        dfs[i] = d

    last_date = dfs[BOND]['date'].max()
    if end_date:
        last_date = min(last_date, end_date)
    start_date = last_date - pd.DateOffset(years=20)

    df = dfs[BOND][['date']].copy()
    df = df[(df['date'] >= start_date) & (df['date'] <= last_date)].reset_index(drop=True)

    for i in STOCK_ALL:
        sub = dfs[i][['date','close','bf','ratio']].copy()
        sub = sub.rename(columns={'close': f'close_{i}', 'bf': f'bf_{i}', 'ratio': f'ratio_{i}'})
        df = pd.merge(df, sub, on='date', how='left')

    for i in STOCK_ALL + [BOND]:
        sub = dfs[i][['date','open','close']].copy()
        sub = sub.rename(columns={'open': f'open_{i}', 'close': f'close2_{i}'})
        df = pd.merge(df, sub, on='date', how='left')
        df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)

    last_idx = df.index[-1]
    for i in STOCK_ALL + [BOND]:
        df[f'ret_{i}'] = np.nan
        mask = df[f'open_{i}_next'].notna() & df[f'open_{i}'].notna()
        df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
        if pd.notna(df.loc[last_idx, f'open_{i}']) and pd.notna(df.loc[last_idx, f'close2_{i}']):
            df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close2_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

    all_ids = STOCK_ALL + [BOND]

    def get_signal(row):
        available = {}
        for i in STOCK_ALL:
            bf_val = row[f'bf_{i}']
            ratio_val = row[f'ratio_{i}']
            if pd.notna(bf_val) and pd.notna(ratio_val):
                available[i] = (bf_val, ratio_val)
        if not available:
            return BOND
        if all(v[1] < 1 for v in available.values()):
            return BOND
        return max(available, key=lambda k: available[k][0])

    df['raw_signal'] = df.apply(get_signal, axis=1)
    df['raw_position'] = df['raw_signal'].shift(1)
    df.loc[df.index[0], 'raw_position'] = 0
    df['raw_prev_position'] = df['raw_position'].shift(1)
    df.loc[df.index[0], 'raw_prev_position'] = df.loc[df.index[0], 'raw_position']

    def get_raw_ret(row):
        pos = int(row['raw_position'])
        gross = 0.0 if pos == 0 else (row[f'ret_{pos}'] if pd.notna(row[f'ret_{pos}']) else 0.0)
        prev = int(row['raw_prev_position'])
        cost = 0.0
        if prev != pos:
            if prev in all_ids: cost += FEE
            if pos in all_ids: cost += FEE
        return (1 + gross) * (1 - cost) - 1

    df['raw_ret'] = df.apply(get_raw_ret, axis=1)
    df['raw_nav'] = (1 + df['raw_ret']).cumprod()
    df['raw_cummax'] = df['raw_nav'].cummax()
    df['raw_dd'] = df['raw_nav'] / df['raw_cummax'] - 1

    raw_pos = df['raw_position'].values
    raw_dd = df['raw_dd'].values
    n = len(df)
    in_cb = False
    final_position = []

    for i in range(n):
        sig = int(raw_pos[i])
        dd = raw_dd[i]
        if not in_cb:
            if dd < -DD_TRIGGER and sig != BOND:
                in_cb = True
                final_position.append(BOND)
            else:
                final_position.append(sig)
        else:
            if dd > -DD_RELEASE:
                in_cb = False
                final_position.append(sig)
            else:
                final_position.append(BOND)

    df['final_position'] = final_position
    df['final_prev_position'] = df['final_position'].shift(1)
    df.loc[df.index[0], 'final_prev_position'] = df.loc[df.index[0], 'final_position']

    def get_final_ret(row):
        pos = int(row['final_position'])
        gross = 0.0 if pos == 0 else (row[f'ret_{pos}'] if pd.notna(row[f'ret_{pos}']) else 0.0)
        prev = int(row['final_prev_position'])
        cost = 0.0
        if prev != pos:
            if prev in all_ids: cost += FEE
            if pos in all_ids: cost += FEE
        return (1 + gross) * (1 - cost) - 1

    df['final_ret'] = df.apply(get_final_ret, axis=1)
    df['final_nav'] = (1 + df['final_ret']).cumprod()
    df['final_cummax'] = df['final_nav'].cummax()
    df['final_dd'] = df['final_nav'] / df['final_cummax'] - 1

    total_ret = (df['final_nav'].iloc[-1] - 1) * 100
    mdd = df['final_dd'].min() * 100
    return total_ret, mdd, df

# 方案D: 混合数据（同花顺可用的用同花顺，不可用的用akshare）
mixed_dfs = {}
for i in STOCK_ALL + [BOND]:
    if i in ths_dfs:
        mixed_dfs[i] = ths_dfs[i]
    else:
        mixed_dfs[i] = csv_dfs[i]
        print(f'  {names[i]}: 用akshare替代(同花顺不可用)')

ret_d, mdd_d, df_d = run_backtest(mixed_dfs, end_date=pd.Timestamp('2026-07-20'))
print(f'  方案D(混合, 到7/20): 近20年总收益 {ret_d:+.2f}%, 回撤 {mdd_d:.2f}%')

# 方案B: 全akshare
ret_b, mdd_b, df_b = run_backtest(csv_dfs, end_date=pd.Timestamp('2026-07-20'))
print(f'  方案B(全akshare, 到7/20): 近20年总收益 {ret_b:+.2f}%, 回撤 {mdd_b:.2f}%')

print()
print(f'  D vs B (数据源差异): {ret_d:+.2f}% vs {ret_b:+.2f}%, 差 {ret_b-ret_d:+.2f}%')
print(f'  上次v14_yearly_all_v2结果: +86022.83%')

# ==== 逐标的替换分析 ====
print()
print('=== 3. 逐标的替换分析（从混合数据源逐个替换为akshare） ===')
for test_i in STOCK_ALL + [BOND]:
    if test_i not in ths_dfs:
        continue  # 同花顺不可用的跳过
    test_dfs = {}
    for i in STOCK_ALL + [BOND]:
        if i == test_i:
            test_dfs[i] = csv_dfs[i]  # 替换为akshare
        elif i in ths_dfs:
            test_dfs[i] = ths_dfs[i]
        else:
            test_dfs[i] = csv_dfs[i]
    ret_test, mdd_test, _ = run_backtest(test_dfs, end_date=pd.Timestamp('2026-07-20'))
    delta = ret_test - ret_d
    print(f'  替换{names[test_i]}为akshare: {ret_test:+.2f}% (差{delta:+.2f}%)')

# ==== 对比熔断时点差异 ====
print()
print('=== 4. 熔断时点差异 ===')
# 方案D的熔断事件
cb_events_d = []
in_cb = False
for idx in range(len(df_d)):
    pos = int(df_d.iloc[idx]['final_position'])
    date = df_d.iloc[idx]['date'].date()
    raw_pos = int(df_d.iloc[idx]['raw_position'])
    if pos == BOND and raw_pos != BOND and not in_cb:
        cb_events_d.append(('触发', date))
        in_cb = True
    elif pos != BOND and in_cb:
        cb_events_d.append(('解除', date))
        in_cb = False

cb_events_b = []
in_cb = False
for idx in range(len(df_b)):
    pos = int(df_b.iloc[idx]['final_position'])
    date = df_b.iloc[idx]['date'].date()
    raw_pos = int(df_b.iloc[idx]['raw_position'])
    if pos == BOND and raw_pos != BOND and not in_cb:
        cb_events_b.append(('触发', date))
        in_cb = True
    elif pos != BOND and in_cb:
        cb_events_b.append(('解除', date))
        in_cb = False

print(f'  方案D(混合): {len(cb_events_d)}次熔断事件')
for evt in cb_events_d:
    print(f'    {evt[0]}: {evt[1]}')

print(f'  方案B(akshare): {len(cb_events_b)}次熔断事件')
for evt in cb_events_b:
    print(f'    {evt[0]}: {evt[1]}')
