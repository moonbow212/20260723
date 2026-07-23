"""对比不同日期范围对V14近20年收益的影响（akshare数据）"""
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

def load_csv(i, name):
    d = pd.read_csv(f'data/{i}_{name}.csv', parse_dates=['date'])
    d = d[['date','open','close']].sort_values('date').reset_index(drop=True)
    return d

def load_ths(name):
    """读取同花顺数据（日K格式），文件不存在或格式异常返回None"""
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

# ==== 加载akshare数据 ====
print('加载akshare数据...')
csv_dfs = {}
for i in STOCK_ALL + [BOND]:
    csv_dfs[i] = load_csv(i, names[i])

csv_last = csv_dfs[BOND]['date'].max()
print(f'  akshare国债最后日期: {csv_last.date()}')

# ==== 检查同花顺文件状态 ====
print()
print('=== 同花顺文件状态 ===')
ths_dfs = {}
ths_available = True
for i in STOCK_ALL + [BOND]:
    name = names[i]
    d = load_ths(name)
    if d is None:
        # 文件不存在或格式异常，用akshare替代
        d = load_csv(i, name)
        print(f'  {name}: 同花顺文件不可用，用akshare替代 ({d["date"].iloc[0].date()}~{d["date"].iloc[-1].date()})')
    else:
        print(f'  {name}: {d["date"].iloc[0].date()}~{d["date"].iloc[-1].date()}, {len(d)}条')

# ==== 方案B: akshare数据截止7/20 ====
print()
ret_b, mdd_b, n_b, s_b, e_b, df_b = run_backtest(csv_dfs, end_date=pd.Timestamp('2026-07-20'))
print(f'方案B(akshare, 到{e_b}): 近20年总收益 {ret_b:+.2f}%, 回撤 {mdd_b:.2f}%, {n_b}天, 起始{s_b}')

# ==== 方案C: akshare数据截止7/21 ====
ret_c, mdd_c, n_c, s_c, e_c, df_c = run_backtest(csv_dfs)
print(f'方案C(akshare, 到{e_c}): 近20年总收益 {ret_c:+.2f}%, 回撤 {mdd_c:.2f}%, {n_c}天, 起始{s_c}')

print()
print('=== 对比汇总 ===')
print(f'  上次v14_yearly_all_v2(同花顺, 到7/17~7/20): +86022.83%')
print(f'  方案B(akshare, 到7/20):                    {ret_b:+.2f}%')
print(f'  方案C(akshare, 到7/21):                    {ret_c:+.2f}%')
print()
print(f'  B vs C (日期范围差异, 7/20->7/21): {ret_b:+.2f}% -> {ret_c:+.2f}%, 差 {ret_c-ret_b:+.2f}%')

# ==== 检查7/20~7/21的持仓和收益 ====
print()
print('=== 7/20~7/21持仓和收益 ===')
for idx in range(max(0, len(df_c) - 5), len(df_c)):
    row = df_c.iloc[idx]
    date = row['date'].date()
    pos = int(row['final_position'])
    ret = row['final_ret']
    nav = row['final_nav']
    pos_name = names.get(pos, '空仓') if pos > 0 else '空仓'
    print(f'  {date}: 持仓={pos_name}({pos}), 日收益={ret:+.4f}%, 净值={nav:.2f}')

# ==== 如果同花顺数据可用，对比数据源差异 ====
if ths_available:
    print()
    print('=== 方案A: 同花顺数据 ===')
    ret_a, mdd_a, n_a, s_a, e_a, df_a = run_backtest(ths_dfs)
    print(f'方案A(同花顺, 到{e_a}): 近20年总收益 {ret_a:+.2f}%, 回撤 {mdd_a:.2f}%, {n_a}天')
    print()
    print(f'  A vs B (数据源差异, 同花顺 vs akshare, 都截止7/20附近):')
    print(f'    {ret_a:+.2f}% vs {ret_b:+.2f}%, 差 {ret_b-ret_a:+.2f}%')
else:
    print()
    print('  (同花顺上证50文件已损坏，无法用同花顺数据复现86022.83%)')

# ==== 检查akshare数据的起始日期 ====
print()
print('=== akshare各标的数据起始日期 ===')
for i in STOCK_ALL + [BOND]:
    name = names[i]
    start = csv_dfs[i]['date'].iloc[0].date()
    end = csv_dfs[i]['date'].iloc[-1].date()
    print(f'  {name}: {start}~{end}, {len(csv_dfs[i])}条')
