"""对比两种数据源对V14近20年收益的影响"""
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
    d = pd.read_csv(path, sep='\t', encoding='gbk')
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
    n_days = len(df)
    start = df['date'].iloc[0].date()
    end = df['date'].iloc[-1].date()

    return total_ret, mdd, n_days, start, end, df

# ==== 方案A: 用同花顺数据 ====
print('加载同花顺数据...')
ths_dfs = {}
for i in STOCK_ALL + [BOND]:
    ths_dfs[i] = load_ths(names[i])

ths_last = ths_dfs[BOND]['date'].max()
print(f'  同花顺国债最后日期: {ths_last.date()}')

ret_a, mdd_a, n_a, s_a, e_a, df_a = run_backtest(ths_dfs)
print(f'  方案A(同花顺, 到{e_a}): 近20年总收益 {ret_a:+.2f}%, 回撤 {mdd_a:.2f}%, {n_a}天')

# ==== 方案B: 用akshare CSV数据，截止到7/20 ====
print()
print('加载akshare数据(截止7/20)...')
csv_dfs = {}
for i in STOCK_ALL + [BOND]:
    csv_dfs[i] = load_csv(i, names[i])

csv_last = csv_dfs[BOND]['date'].max()
print(f'  akshare国债最后日期: {csv_last.date()}')

ret_b, mdd_b, n_b, s_b, e_b, df_b = run_backtest(csv_dfs, end_date=pd.Timestamp('2026-07-20'))
print(f'  方案B(akshare, 到{e_b}): 近20年总收益 {ret_b:+.2f}%, 回撤 {mdd_b:.2f}%, {n_b}天')

# ==== 方案C: 用akshare CSV数据，截止到7/21 ====
print()
ret_c, mdd_c, n_c, s_c, e_c, df_c = run_backtest(csv_dfs)
print(f'  方案C(akshare, 到{e_c}): 近20年总收益 {ret_c:+.2f}%, 回撤 {mdd_c:.2f}%, {n_c}天')

print()
print('=== 对比汇总 ===')
print(f'  A: 同花顺 {s_a}~{e_a}  => {ret_a:+.2f}%  (上次v14_yearly_all_v2结果: +86022.83%)')
print(f'  B: akshare {s_b}~{e_b}  => {ret_b:+.2f}%  (同数据源, 截止7/20)')
print(f'  C: akshare {s_c}~{e_c}  => {ret_c:+.2f}%  (同数据源, 截止7/21, v14_daily_signal结果: +104336.12%)')
print()
print(f'  A vs B (数据源差异):     {ret_a:+.2f}% vs {ret_b:+.2f}%  差 {ret_b-ret_a:+.2f}%')
print(f'  B vs C (日期范围差异):   {ret_b:+.2f}% vs {ret_c:+.2f}%  差 {ret_c-ret_b:+.2f}%')

# ==== 深入分析：对比A股数据差异 ====
print()
print('=== 美股数据日收益率差异分析 ===')
for i, name in [(3, '纳斯达克100'), (7, '标普500')]:
    d_ths = ths_dfs[i][['date','open','close']].copy()
    d_csv = csv_dfs[i][['date','open','close']].copy()
    merged = pd.merge(d_ths, d_csv, on='date', suffixes=('_ths', '_csv'))
    merged['ret_ths'] = merged['close_ths'].pct_change()
    merged['ret_csv'] = merged['close_csv'].pct_change()
    diff = (merged['ret_ths'] - merged['ret_csv']).abs()
    print(f'  {name}: 日收益率平均差异 {diff.mean():.8f}, 最大差异 {diff.max():.8f}, 差异>0.001%的天数 {(diff > 0.00001).sum()}')

# ==== 对比国债数据差异 ====
print()
print('=== 国债数据差异分析 ===')
d_ths = ths_dfs[BOND][['date','open','close']].copy()
d_csv = csv_dfs[BOND][['date','open','close']].copy()
print(f'  同花顺: {d_ths["date"].iloc[0].date()}~{d_ths["date"].iloc[-1].date()}, {len(d_ths)}条')
print(f'  akshare: {d_csv["date"].iloc[0].date()}~{d_csv["date"].iloc[-1].date()}, {len(d_csv)}条')
merged = pd.merge(d_ths, d_csv, on='date', suffixes=('_ths', '_csv'))
merged['ret_ths'] = merged['close_ths'].pct_change()
merged['ret_csv'] = merged['close_csv'].pct_change()
diff = (merged['ret_ths'] - merged['ret_csv']).abs()
print(f'  日收益率平均差异 {diff.mean():.8f}, 最大差异 {diff.max():.8f}')
print(f'  价格比值(最后): {merged["close_ths"].iloc[-1] / merged["close_csv"].iloc[-1]:.6f}')
print(f'  价格比值(最初): {merged["close_ths"].iloc[0] / merged["close_csv"].iloc[0]:.6f}')

# ==== 检查各标的数据起始日期差异 ====
print()
print('=== 各标的数据起始日期对比 ===')
for i in STOCK_ALL + [BOND]:
    name = names[i]
    ths_start = ths_dfs[i]['date'].iloc[0].date()
    csv_start = csv_dfs[i]['date'].iloc[0].date()
    ths_end = ths_dfs[i]['date'].iloc[-1].date()
    csv_end = csv_dfs[i]['date'].iloc[-1].date()
    diff_flag = ' <<<' if (ths_start != csv_start or ths_end != csv_end) else ''
    print(f'  {name}: 同花顺 {ths_start}~{ths_end} ({len(ths_dfs[i])}) | akshare {csv_start}~{csv_end} ({len(csv_dfs[i])}){diff_flag}')
