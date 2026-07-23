# -*- coding: utf-8 -*-
"""V14 MA10 vs MA20 逐年收益对比
策略定义：
  - 决策日期 = T日（执行日）
  - 决策bf = (T-1日收盘价 / T-1日MA) - 1  (MA=10 或 MA=20)
  - T日开盘执行，收益口径 open-to-open
  - 5%回撤触发熔断转国债，4%解除
"""
import pandas as pd
import numpy as np
import json, os

FEE = 0.0002
DD_TRIGGER = 0.05
DD_RELEASE = 0.04

STOCK_ALL = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}
all_names = {0:'空仓', 1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== 1. 读取数据 =====
print("读取数据...")
dfs = {}
for i in STOCK_ALL + [BOND]:
    name = names[i]
    csv_path = os.path.join(BASE_DIR, 'data', f'{i}_{name}.csv')
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"未找到 {name} 数据文件 {csv_path}")
    d = pd.read_csv(csv_path, parse_dates=['date'])
    d = d[['date', 'open', 'close']].rename(columns={'open': f'open_{i}', 'close': f'close_{i}'})
    d = d.sort_values('date').reset_index(drop=True)
    if i != BOND:
        # 计算MA10和MA20
        d[f'ma10_{i}'] = d[f'close_{i}'].rolling(10).mean()
        d[f'bf10_{i}'] = d[f'close_{i}'] / d[f'ma10_{i}'] - 1
        d[f'ratio10_{i}'] = d[f'close_{i}'] / d[f'ma10_{i}']
        d[f'ma20_{i}'] = d[f'close_{i}'].rolling(20).mean()
        d[f'bf20_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}'] - 1
        d[f'ratio20_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}']
    dfs[i] = d
    print(f"  {names[i]}: {d['date'].iloc[0].date()} ~ {d['date'].iloc[-1].date()}, {len(d)}条")

last_date = dfs[BOND]['date'].max()
print(f"\n数据最新日期: {last_date.date()}")


# ===== 2. 构建合并数据 =====
def build_merged_data(start_date, end_date, ma_period):
    """ma_period: 10 or 20"""
    df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)

    for i in STOCK_ALL:
        bf_col = f'bf{ma_period}_{i}'
        ratio_col = f'ratio{ma_period}_{i}'
        ma_col = f'ma{ma_period}_{i}'
        cols = ['date', f'open_{i}', f'close_{i}', ma_col, bf_col, ratio_col]
        df = pd.merge(df, dfs[i][cols], on='date', how='left')

    all_ids = STOCK_ALL + [BOND]
    for i in all_ids:
        df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
    last_idx = df.index[-1]
    for i in all_ids:
        df[f'ret_{i}'] = np.nan
        mask = df[f'open_{i}_next'].notna() & df[f'open_{i}'].notna()
        df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
        if pd.notna(df.loc[last_idx, f'open_{i}']) and pd.notna(df.loc[last_idx, f'close_{i}']):
            df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

    bf_prefix = f'bf{ma_period}'
    ratio_prefix = f'ratio{ma_period}'

    def get_signal(row):
        available = {}
        for i in STOCK_ALL:
            bf_val = row[f'{bf_prefix}_{i}']
            ratio_val = row[f'{ratio_prefix}_{i}']
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

    def get_raw_strat_ret(row):
        pos = int(row['raw_position'])
        if pos == 0:
            gross = 0.0
        else:
            ret_val = row[f'ret_{pos}']
            gross = ret_val if pd.notna(ret_val) else 0.0
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
    return df, all_ids


# ===== 3. 熔断 =====
def apply_circuit_breaker(df, all_ids, bond_id):
    raw_pos = df['raw_position'].values
    raw_dd = df['raw_dd'].values
    n = len(df)
    in_cb = False
    final_position = []
    for i in range(n):
        sig = int(raw_pos[i])
        dd = raw_dd[i]
        if not in_cb:
            if dd < -DD_TRIGGER and sig != bond_id:
                in_cb = True
                final_position.append(bond_id)
            else:
                final_position.append(sig)
        else:
            if dd > -DD_RELEASE:
                in_cb = False
                final_position.append(sig)
            else:
                final_position.append(bond_id)
    return np.array(final_position)


def compute_v14_ret(df, all_ids, bond_id, pos):
    n = len(df)
    prev_pos = np.concatenate([[pos[0]], pos[:-1]])
    rets = np.zeros(n)
    for i in range(n):
        p = int(pos[i])
        if p == 0:
            gross = 0.0
        else:
            ret_val = df[f'ret_{p}'].iloc[i]
            gross = ret_val if pd.notna(ret_val) else 0.0
        cost = 0.0
        if int(prev_pos[i]) != p:
            if int(prev_pos[i]) in all_ids: cost += FEE
            if p in all_ids: cost += FEE
        rets[i] = (1 + gross) * (1 - cost) - 1
    return rets


# ===== 4. 跑各时段 =====
periods_config = {
    '近20年': last_date - pd.DateOffset(years=20),
    '近10年': last_date - pd.DateOffset(years=10),
    '近5年':  last_date - pd.DateOffset(years=5),
    '近3年':  last_date - pd.DateOffset(years=3),
    '近1年':  last_date - pd.DateOffset(years=1),
}

results = {}
for ma in [10, 20]:
    ma_results = {}
    for pname in ['近20年','近10年','近5年','近3年','近1年']:
        sd = periods_config[pname]
        df, all_ids = build_merged_data(sd, last_date, ma)
        pos_v14 = apply_circuit_breaker(df, all_ids, BOND)
        v14_rets = compute_v14_ret(df, all_ids, BOND, pos_v14)
        df['v14_pos'] = pos_v14
        df['v14_ret'] = v14_rets
        df['year'] = df['date'].dt.year

        years = sorted(df['year'].unique())
        yearly_list = []
        for y in years:
            sub = df[df['year'] == y].copy()
            ny = len(sub)
            year_ret = (1 + sub['v14_ret']).prod() - 1
            year_nav = (1 + sub['v14_ret']).cumprod()
            year_mdd = ((year_nav - year_nav.cummax()) / year_nav.cummax()).min()
            yearly_list.append({
                'year': int(y),
                'n_days': int(ny),
                'ret': round(float(year_ret)*100, 2),
                'mdd': round(float(year_mdd)*100, 2),
                'switches': int(np.sum(np.diff(sub['v14_pos'].values) != 0)),
            })

        total_ret = (1 + df['v14_ret']).prod() - 1
        nav_all = (1 + df['v14_ret']).cumprod()
        mdd_all = ((nav_all - nav_all.cummax()) / nav_all.cummax()).min()
        std_all = df['v14_ret'].std()
        sharpe_all = np.sqrt(252) * df['v14_ret'].mean() / std_all if std_all > 0 else 0
        ann_all = (1 + total_ret) ** (252/len(df)) - 1

        ma_results[pname] = {
            'start': df['date'].iloc[0].strftime('%Y-%m-%d'),
            'end': df['date'].iloc[-1].strftime('%Y-%m-%d'),
            'n_days': int(len(df)),
            'yearly': yearly_list,
            'overall': {
                'total_ret': round(float(total_ret)*100, 2),
                'ann_ret': round(float(ann_all)*100, 2),
                'mdd': round(float(mdd_all)*100, 2),
                'sharpe': round(float(sharpe_all), 2),
                'ann_vol': round(float(std_all * np.sqrt(252))*100, 2),
            },
        }
        print(f"  MA{ma} {pname}: 总收益={float(total_ret)*100:+.2f}%, 夏普={float(sharpe_all):.2f}, 回撤={float(mdd_all)*100:.2f}%")
    results[f'MA{ma}'] = ma_results

# 保存JSON
with open(os.path.join(BASE_DIR, 'v14_ma10_vs_ma20.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\n数据已保存到 v14_ma10_vs_ma20.json")


# ===== 5. 生成HTML =====
html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14 MA10 vs MA20 逐年收益对比</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Microsoft YaHei','Segoe UI',sans-serif; background:#f5f6fa; color:#333; padding:20px; }}
h1 {{ text-align:center; font-size:22px; margin-bottom:5px; }}
.sub {{ text-align:center; font-size:13px; color:#666; margin-bottom:20px; }}
.note {{ background:#e8f4fd; border:1px solid #b3d9f2; border-radius:6px; padding:10px 16px; margin-bottom:16px; font-size:13px; color:#1a5276; }}
.summary-grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:24px; }}
.summary-card {{ background:#fff; border-radius:8px; padding:14px; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.06); }}
.summary-card h3 {{ font-size:14px; color:#666; margin-bottom:8px; }}
.summary-card .val {{ font-size:18px; font-weight:700; }}
.summary-card .sub-val {{ font-size:12px; color:#888; margin-top:4px; }}
.summary-card .compare {{ font-size:11px; margin-top:6px; padding:3px 8px; border-radius:4px; display:inline-block; }}
.better {{ background:#e8f5e9; color:#2e7d32; }}
.worse {{ background:#fce4ec; color:#c62828; }}
.period-card {{ background:#fff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.08); margin-bottom:24px; overflow:hidden; }}
.period-header {{ background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; padding:14px 20px; }}
.period-header h2 {{ font-size:18px; margin-bottom:4px; }}
.period-header .info {{ font-size:13px; opacity:0.9; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#f8f9fa; padding:10px 6px; text-align:center; font-weight:600; border-bottom:2px solid #e0e0e0; white-space:nowrap; }}
td {{ padding:8px 6px; text-align:center; border-bottom:1px solid #eee; }}
tr:hover td {{ background:#f8f9ff; }}
.pos {{ color:#e74c3c; font-weight:600; }}
.neg {{ color:#27ae60; font-weight:600; }}
.ma10-col {{ background:#fff3e0; }}
.ma20-col {{ background:#e3f2fd; }}
.diff-pos {{ color:#e74c3c; font-weight:600; }}
.diff-neg {{ color:#27ae60; font-weight:600; }}
.overall-row {{ background:#fffde7 !important; font-weight:600; }}
.overall-row td {{ border-top:2px solid #f0e68c; border-bottom:2px solid #f0e68c; }}
.group-header td {{ background:#e8eaf6; font-weight:600; color:#3f51b5; font-size:12px; }}
</style>
</head>
<body>
<h1>V14策略 MA10 vs MA20 逐年收益对比</h1>
<div class="sub">5%/4%熔断 · 8股+国债动态标的池 · 决策bf=(T-1收盘/T-1的MA)-1 · T日开盘执行 · open-to-open · 手续费0.02%</div>
<div class="note">对比说明：除MA周期不同外，其余策略参数完全一致。MA10 = 收盘价/10日均线-1，MA20 = 收盘价/20日均线-1。</div>
'''

# 汇总卡片
html += '<div class="summary-grid">'
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r10 = results['MA10'][pname]['overall']
    r20 = results['MA20'][pname]['overall']
    diff = r10['total_ret'] - r20['total_ret']
    diff_class = 'better' if diff > 0 else 'worse'
    diff_text = f'MA10 {"多" if diff>0 else "少"} {abs(diff):.2f}%'
    html += f'''<div class="summary-card">
    <h3>{pname}</h3>
    <div style="display:flex;justify-content:center;gap:12px;align-items:baseline">
        <div><span style="font-size:11px;color:#e65100">MA10</span> <span class="val {'pos' if r10['total_ret']>=0 else 'neg'}">{r10['total_ret']:+.1f}%</span></div>
        <div><span style="font-size:11px;color:#1565c0">MA20</span> <span class="val {'pos' if r20['total_ret']>=0 else 'neg'}">{r20['total_ret']:+.1f}%</span></div>
    </div>
    <div class="compare {diff_class}">{diff_text}</div>
    <div class="sub-val">MA10夏普 {r10['sharpe']:.2f} vs MA20夏普 {r20['sharpe']:.2f}</div>
    <div class="sub-val">MA10回撤 {r10['mdd']:.2f}% vs MA20回撤 {r20['mdd']:.2f}%</div>
    </div>'''
html += '</div>'

# 各时段表格
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r10 = results['MA10'][pname]
    r20 = results['MA20'][pname]
    o10 = r10['overall']
    o20 = r20['overall']

    # 获取所有年份
    all_years = sorted(set([y['year'] for y in r10['yearly']] + [y['year'] for y in r20['yearly']]))
    y10_map = {y['year']: y for y in r10['yearly']}
    y20_map = {y['year']: y for y in r20['yearly']}

    html += f'''<div class="period-card">
    <div class="period-header">
        <h2>{pname}</h2>
        <div class="info">{r10['start']} ~ {r10['end']} · {r10['n_days']}天</div>
    </div>
    <table>
    <thead><tr>
        <th rowspan="2">年份</th>
        <th rowspan="2">交易日</th>
        <th colspan="3" style="border-right:1px solid #ddd">年度收益</th>
        <th colspan="2" style="border-right:1px solid #ddd">最大回撤</th>
        <th colspan="2">切换次数</th>
    </tr><tr>
        <th class="ma10-col">MA10</th>
        <th class="ma20-col">MA20</th>
        <th>差异</th>
        <th class="ma10-col">MA10</th>
        <th class="ma20-col">MA20</th>
        <th class="ma10-col">MA10</th>
        <th class="ma20-col">MA20</th>
    </tr></thead><tbody>'''

    for y in all_years:
        y10 = y10_map.get(y)
        y20 = y20_map.get(y)
        if y10 and y20:
            diff = y10['ret'] - y20['ret']
            diff_cls = 'diff-pos' if diff > 0 else 'diff-neg'
            html += f'''<tr>
            <td>{y}</td>
            <td>{y10['n_days']}</td>
            <td class="ma10-col {'pos' if y10['ret']>=0 else 'neg'}">{y10['ret']:+.2f}%</td>
            <td class="ma20-col {'pos' if y20['ret']>=0 else 'neg'}">{y20['ret']:+.2f}%</td>
            <td class="{diff_cls}">{diff:+.2f}%</td>
            <td class="ma10-col">{y10['mdd']:.2f}%</td>
            <td class="ma20-col">{y20['mdd']:.2f}%</td>
            <td class="ma10-col">{y10['switches']}</td>
            <td class="ma20-col">{y20['switches']}</td>
            </tr>'''
        elif y10:
            html += f'''<tr>
            <td>{y}</td><td>{y10['n_days']}</td>
            <td class="ma10-col {'pos' if y10['ret']>=0 else 'neg'}">{y10['ret']:+.2f}%</td>
            <td class="ma20-col">-</td><td>-</td>
            <td class="ma10-col">{y10['mdd']:.2f}%</td><td class="ma20-col">-</td>
            <td class="ma10-col">{y10['switches']}</td><td class="ma20-col">-</td>
            </tr>'''
        else:
            html += f'''<tr>
            <td>{y}</td><td>{y20['n_days']}</td>
            <td class="ma10-col">-</td>
            <td class="ma20-col {'pos' if y20['ret']>=0 else 'neg'}">{y20['ret']:+.2f}%</td><td>-</td>
            <td class="ma10-col">-</td><td class="ma20-col">{y20['mdd']:.2f}%</td>
            <td class="ma10-col">-</td><td class="ma20-col">{y20['switches']}</td>
            </tr>'''

    # 整体行
    diff_total = o10['total_ret'] - o20['total_ret']
    diff_cls = 'diff-pos' if diff_total > 0 else 'diff-neg'
    html += f'''<tr class="overall-row">
    <td>整体</td>
    <td>{r10['n_days']}</td>
    <td class="ma10-col {'pos' if o10['total_ret']>=0 else 'neg'}">{o10['total_ret']:+.2f}%</td>
    <td class="ma20-col {'pos' if o20['total_ret']>=0 else 'neg'}">{o20['total_ret']:+.2f}%</td>
    <td class="{diff_cls}">{diff_total:+.2f}%</td>
    <td class="ma10-col">{o10['mdd']:.2f}%</td>
    <td class="ma20-col">{o20['mdd']:.2f}%</td>
    <td class="ma10-col">-</td><td class="ma20-col">-</td>
    </tr>'''

    # 年化、夏普行
    html += f'''<tr class="group-header"><td colspan="9">MA10: 年化{o10['ann_ret']:+.2f}% · 夏普{o10['sharpe']:.2f} · 波动{o10['ann_vol']:.2f}%  ||  MA20: 年化{o20['ann_ret']:+.2f}% · 夏普{o20['sharpe']:.2f} · 波动{o20['ann_vol']:.2f}%</td></tr>'''

    html += '</tbody></table></div>'

html += '''
<div style="text-align:center;font-size:12px;color:#999;margin-top:20px;">
收益口径: open-to-open · 橙色列=MA10 · 蓝色列=MA20 · 差异=MA10-MA20(正数表示MA10更好)
</div>
</body></html>'''

out_path = os.path.join(BASE_DIR, 'v14_ma10_vs_ma20.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nHTML报告已生成: {out_path}")
