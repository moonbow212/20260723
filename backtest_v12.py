"""
V12 回测脚本：V8 + 2%切换阈值
- 基础：V8 八指数轮动（科创50仅近5/3/1年）+ 国债避险 + 手续费万分之二
- 改动：只在"目标资产bf > 当前持仓bf + 0.02"时才切换，否则维持现状
"""
import pandas as pd
import numpy as np
import json
from functools import reduce
from datetime import timedelta

# ============== 1. 加载数据 ==============
def load_data(path, name):
    df = pd.read_csv(path, sep='\t', encoding='gbk')
    if '时间' in df.columns:
        df['date'] = pd.to_datetime(df['时间'].str.split(',').str[0])
    elif '日期' in df.columns:
        df['date'] = pd.to_datetime(df['日期'])
    rename = {'今开':'open','开盘':'open','最高':'high','最低':'low','收盘':'close','收盘价':'close',
              '成交量':'volume','成交额':'volume','昨收':'prev_close'}
    df = df.rename(columns=rename)
    for c in ['open','close']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['date','close','open'])
    df = df.sort_values('date').reset_index(drop=True)
    df['name'] = name
    return df[['date','open','close']]

print("加载数据...")
all_files = {
    'sh50':  ('C:/Users/wbl/Desktop/同花顺历史数据/上证50.xlsx', '上证50'),
    'gem50': ('C:/Users/wbl/Desktop/同花顺历史数据/创业板50.xlsx', '创业板50'),
    'ndx':   ('C:/Users/wbl/Desktop/纳斯达克100.xlsx', '纳斯达克100'),
    'hs300': ('C:/Users/wbl/Desktop/沪深300.xlsx', '沪深300'),
    'zz500': ('C:/Users/wbl/Desktop/中证500.xlsx', '中证500'),
    'zz1000':('C:/Users/wbl/Desktop/中证1000.xlsx', '中证1000'),
    'sp500': ('C:/Users/wbl/Desktop/标普500.xlsx', '标普500'),
    'kc50':  ('C:/Users/wbl/Desktop/科创50.xlsx', '科创50'),
    'bond':  ('C:/Users/wbl/Desktop/国债.xlsx', '国债'),
}
raw = {key: load_data(path, name) for key, (path, name) in all_files.items()}
print(f"已加载{len(raw)}个数据集")

# ============== 2. 时段配置 ==============
end_date = max(df['date'].max() for df in raw.values())
print(f"数据截止: {end_date.date()}")

names_map = {'sh50':'上证50','gem50':'创业板50','ndx':'纳斯达克100','hs300':'沪深300',
             'zz500':'中证500','zz1000':'中证1000','sp500':'标普500','kc50':'科创50','bond':'国债'}

# 各时段参与的股票
periods_config = {
    '近10年': (['sh50','gem50','ndx','hs300','zz500','zz1000','sp500'], 10),  # 不含科创50
    '近5年':  (['sh50','gem50','ndx','hs300','zz500','zz1000','sp500','kc50'], 5),
    '近3年':  (['sh50','gem50','ndx','hs300','zz500','zz1000','sp500','kc50'], 3),
    '近1年':  (['sh50','gem50','ndx','hs300','zz500','zz1000','sp500','kc50'], 1),
}

THRESHOLD = 0.02  # 切换阈值

# ============== 3. 时段回测函数 ==============
def run_period(stocks, start_date, end_date, period_name):
    """对单时段做V12回测"""
    # 只用该时段参与的指数做内连接
    dfs = []
    for key in stocks + ['bond']:
        df = raw[key].copy()
        df = df.rename(columns={'open': f'open_{key}', 'close': f'close_{key}'})
        dfs.append(df[['date', f'open_{key}', f'close_{key}']])

    df = reduce(lambda a, b: pd.merge(a, b, on='date', how='inner'), dfs)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].sort_values('date').reset_index(drop=True)

    if len(df) < 30:
        print(f"  {period_name}: 数据不足{len(df)}天，跳过")
        return None

    # MA20 和 bf
    for key in stocks:
        df[f'ma20_{key}'] = df[f'close_{key}'].rolling(20).mean()
        df[f'bf_{key}'] = df[f'close_{key}'] / df[f'ma20_{key}'] - 1
        df[f'ret_{key}'] = df[f'open_{key}'].shift(-1) / df[f'close_{key}'] - 1
    df[f'ret_bond'] = df['close_bond'].shift(-1) / df['close_bond'] - 1  # 债券用close代替

    # 删除MA20未计算的早期行
    df = df.dropna(subset=[f'ma20_{k}' for k in stocks]).reset_index(drop=True)

    # ============== V12策略核心 ==============
    n = len(df)
    pos = np.zeros(n, dtype=int)  # 0=国债, 1..len(stocks)=各股票

    # 给每个股票分配ID: 1..len(stocks)
    stock_to_id = {s: i+1 for i, s in enumerate(stocks)}

    # 第一天：选择bf最高（如果bf都<0则持国债）
    first_bfs = {s: df.iloc[0][f'bf_{s}'] for s in stocks}
    if all(v < 0 for v in first_bfs.values()):
        pos[0] = 0
    else:
        best = max(first_bfs, key=first_bfs.get)
        pos[0] = stock_to_id[best]

    for i in range(1, n):
        prev = pos[i-1]
        # 当日各股票bf
        bfs = {s: df.iloc[i][f'bf_{s}'] for s in stocks}
        best_s = max(bfs, key=bfs.get)
        best_bf = bfs[best_s]
        all_neg = all(v < 0 for v in bfs.values())

        if prev == 0:
            # 当前持国债
            if all_neg:
                pos[i] = 0
            else:
                pos[i] = stock_to_id[best_s]
        else:
            # 当前持股票prev
            prev_key = stocks[prev-1]
            prev_bf = bfs[prev_key]

            if all_neg:
                # 全跌破MA20 → 国债
                pos[i] = 0
            elif best_s == prev_key:
                # 维持
                pos[i] = prev
            elif best_bf > prev_bf + THRESHOLD:
                # 目标bf高出阈值，切换
                pos[i] = stock_to_id[best_s]
            else:
                # 差距不够，维持
                pos[i] = prev

    # ============== 收益计算 ==============
    nav = np.ones(n)
    strat_ret = np.full(n, np.nan)
    total_fee = 0.0
    switch_count = 0

    for i in range(n):
        if i < n-1:
            # 用次日开盘价
            if pos[i] == 0:
                r = df.iloc[i]['ret_bond']
            else:
                r = df.iloc[i][f'ret_{stocks[pos[i]-1]}']
        else:
            # 最后一天无次日，用当日open->close
            if pos[i] == 0:
                r = df.iloc[i]['close_bond'] / df.iloc[i]['close_bond'] - 1  # 假设0
            else:
                k = stocks[pos[i]-1]
                r = df.iloc[i][f'close_{k}'] / df.iloc[i][f'open_{k}'] - 1

        if pd.isna(r): r = 0

        # 换仓成本（第一天空仓建仓不算切换）
        is_switch = (i > 0 and pos[i] != pos[i-1])
        cost = 0.0002 if is_switch else 0.0
        if is_switch: switch_count += 1

        if i == 0:
            nav[i] = 1.0 * (1 + r) * (1 - cost)
        else:
            nav[i] = nav[i-1] * (1 + r) * (1 - cost)
        strat_ret[i] = (1 + r) * (1 - cost) - 1
        total_fee += cost

    # 买入持有参考
    bh_metrics = {}
    for key in stocks + ['bond']:
        col = f'close_{key}'
        bh_total = df[col].iloc[-1] / df[col].iloc[0] - 1
        days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
        bh_ann = (1 + bh_total) ** (252/days) - 1 if days > 0 else 0
        bh_daily = df[col].pct_change().dropna()
        bh_vol = bh_daily.std() * np.sqrt(252) if len(bh_daily) > 1 else 0
        bh_sharpe = bh_ann / bh_vol if bh_vol > 0 else 0
        # 最大回撤
        nav_bh = df[col].values / df[col].iloc[0]
        peak = np.maximum.accumulate(nav_bh)
        dd = (nav_bh - peak) / peak
        bh_mdd = dd.min()
        bh_metrics[key] = {'total': bh_total, 'ann': bh_ann, 'mdd': bh_mdd, 'sharpe': bh_sharpe}

    # 持仓分布
    pos_counts = pd.Series(pos).value_counts(normalize=True)
    hold_pct = {}
    for s in stocks:
        hold_pct[s] = float(pos_counts.get(stock_to_id[s], 0))
    hold_pct['bond'] = float(pos_counts.get(0, 0))

    # 策略指标
    days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
    strat_total = nav[-1] - 1
    strat_ann = (1 + strat_total) ** (252/days) - 1 if days > 0 else 0
    rets_clean = pd.Series(strat_ret).dropna()
    vol = rets_clean.std() * np.sqrt(252) if len(rets_clean) > 1 else 0
    sharpe = strat_ann / vol if vol > 0 else 0
    peak = np.maximum.accumulate(nav)
    dd = (nav - peak) / peak
    mdd = dd.min()

    # 净值序列（用于图表）
    bh_navs = {}
    for key in stocks + ['bond']:
        col = f'close_{key}'
        bh_navs[key] = [float(x) for x in df[col].values / df[col].iloc[0]]

    return {
        'period': period_name,
        'start': str(df['date'].iloc[0].date()),
        'end': str(df['date'].iloc[-1].date()),
        'n_days': n,
        'days': days,
        'stocks': stocks,
        'strat_total': strat_total,
        'strat_ann': strat_ann,
        'strat_sharpe': sharpe,
        'strat_mdd': mdd,
        'strat_vol': vol,
        'switch_count': switch_count,
        'total_fee': total_fee,
        'hold_pct': hold_pct,
        'bh_metrics': bh_metrics,
        'nav_dates': [d.strftime('%Y-%m-%d') for d in df['date']],
        'strat_nav': [float(x) for x in nav],
        'bh_navs': bh_navs,
    }

# ============== 4. 跑所有时段 ==============
results = {}
for period, (stocks, years) in periods_config.items():
    start = end_date - pd.DateOffset(years=years)
    print(f"\n=== {period} ({start.date()} ~ {end_date.date()}, 参与{len(stocks)}股票) ===")
    r = run_period(stocks, start, end_date, period)
    if r is None: continue
    results[period] = r
    print(f"  策略: 总收益 {r['strat_total']:.2%}, 年化 {r['strat_ann']:.2%}, 夏普 {r['strat_sharpe']:.2f}, 最大回撤 {r['strat_mdd']:.2%}")
    print(f"  切换: {r['switch_count']}次, 累计手续费: {r['total_fee']:.2%}")
    print(f"  持仓: " + ", ".join(f"{names_map[k]}={v:.1%}" for k, v in r['hold_pct'].items() if v > 0.01))

# 保存
out = {
    'threshold': THRESHOLD,
    'description': f'V8 + 切换阈值{THRESHOLD*100:.0f}%（目标bf > 当前bf+{THRESHOLD*100:.0f}%才切换）',
    'results': results,
}
with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/backtest_v12.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, default=str)
print("\n\n数据已保存到 backtest_v12.json")
