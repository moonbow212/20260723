# -*- coding: utf-8 -*-
"""V14标的池替换对比：去上证50+沪深300，加中证A500+北证50+中证A50

策略：MA20轮动 + 5%/4%熔断 + 动态避险v2(金>20日MA→黄金ETF, 金<=20日MA→国债)
费率：万0.5
收益口径：open-to-open

原标的池(8只)：上证50, 创业板50, 纳斯达克100, 沪深300, 中证500, 中证1000, 标普500, 科创50
新标的池(9只)：创业板50, 纳斯达克100, 中证500, 中证1000, 标普500, 科创50, 中证A500, 北证50, 中证A50
"""
import pandas as pd
import numpy as np
import json, os

DD_TRIGGER = 0.05
DD_RELEASE = 0.04
FEE = 0.00005
MA_PERIOD = 20
GOLD_START = pd.Timestamp('2013-07-29')

# 原标的池
OLD_STOCKS = [1, 2, 3, 4, 5, 6, 7, 8]
# 新标的池
NEW_STOCKS = [2, 3, 5, 6, 7, 8, 11, 12, 13]

BOND = 9
GOLD = 10
names = {
    1:'上证50', 2:'创业板50', 3:'纳斯达克100', 4:'沪深300', 5:'中证500',
    6:'中证1000', 7:'标普500', 8:'科创50', 9:'国债', 10:'黄金ETF',
    11:'中证A500', 12:'北证50', 13:'中证A50'
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== 1. 读取数据 =====
print("读取数据...")
dfs = {}
for i in OLD_STOCKS + NEW_STOCKS + [BOND, GOLD]:
    if i in dfs:
        continue
    name = names[i]
    csv_path = os.path.join(BASE_DIR, 'data', f'{i}_{name}.csv')
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"未找到 {name} 数据文件 {csv_path}")
    d = pd.read_csv(csv_path, parse_dates=['date'])
    d = d[['date', 'open', 'close']].rename(columns={'open': f'open_{i}', 'close': f'close_{i}'})
    d = d.sort_values('date').reset_index(drop=True)
    if i != BOND:
        d[f'ma{MA_PERIOD}_{i}'] = d[f'close_{i}'].rolling(MA_PERIOD).mean()
        d[f'bf{MA_PERIOD}_{i}'] = d[f'close_{i}'] / d[f'ma{MA_PERIOD}_{i}'] - 1
        d[f'ratio{MA_PERIOD}_{i}'] = d[f'close_{i}'] / d[f'ma{MA_PERIOD}_{i}']
    dfs[i] = d

last_date = dfs[BOND]['date'].max()
print(f"数据最新日期: {last_date.date()}")

# ===== 1.5 黄金20日MA（动态避险v2） =====
gold_df = dfs[GOLD][['date', f'close_{GOLD}']].copy()
gold_df[f'ma20_{GOLD}'] = gold_df[f'close_{GOLD}'].rolling(20).mean()
gold_ma_map = gold_df[['date', f'ma20_{GOLD}']].dropna().set_index('date')[f'ma20_{GOLD}']
print(f"黄金20日MA有效起始: {gold_ma_map.index.min().date()}")

# ===== 2. 构建合并数据 =====
def build_merged_data(start_date, end_date, stock_list):
    """构建合并数据，使用动态避险v2逻辑"""
    df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)

    for i in stock_list:
        ma_col = f'ma{MA_PERIOD}_{i}'
        bf_col = f'bf{MA_PERIOD}_{i}'
        ratio_col = f'ratio{MA_PERIOD}_{i}'
        cols = ['date', f'open_{i}', f'close_{i}', ma_col, bf_col, ratio_col]
        df = pd.merge(df, dfs[i][cols], on='date', how='left')

    # 合并黄金ETF数据
    gold_cols = ['date', f'open_{GOLD}', f'close_{GOLD}']
    df = pd.merge(df, dfs[GOLD][gold_cols], on='date', how='left')

    # 动态避险v2：金>20日MA→黄金ETF，金<=20日MA→国债
    df['safe_haven'] = BOND
    mask_gold = df['date'] >= GOLD_START
    # 需要黄金20日MA
    df['_gold_ma20'] = df['date'].map(gold_ma_map)
    mask_above = df[f'close_{GOLD}'] > df['_gold_ma20']
    df.loc[mask_gold & mask_above, 'safe_haven'] = GOLD
    df = df.drop(columns=['_gold_ma20'])

    # 计算收益
    all_asset_ids = list(set(stock_list + [BOND, GOLD]))
    for i in all_asset_ids:
        df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
    last_idx = df.index[-1]
    for i in all_asset_ids:
        df[f'ret_{i}'] = np.nan
        mask = df[f'open_{i}_next'].notna() & df[f'open_{i}'].notna()
        df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
        if pd.notna(df.loc[last_idx, f'open_{i}']) and pd.notna(df.loc[last_idx, f'close_{i}']):
            df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

    bf_prefix = f'bf{MA_PERIOD}'
    ratio_prefix = f'ratio{MA_PERIOD}'

    def get_signal(row):
        available = {}
        for i in stock_list:
            bf_val = row[f'{bf_prefix}_{i}']
            ratio_val = row[f'{ratio_prefix}_{i}']
            if pd.notna(bf_val) and pd.notna(ratio_val):
                available[i] = (bf_val, ratio_val)
        safe = int(row['safe_haven'])
        if not available:
            return safe
        if all(v[1] < 1 for v in available.values()):
            return safe
        return max(available, key=lambda k: available[k][0])

    df['raw_signal'] = df.apply(get_signal, axis=1)
    df['raw_position'] = df['raw_signal'].shift(1)
    df.loc[df.index[0], 'raw_position'] = 0
    df['raw_prev_position'] = df['raw_position'].shift(1)
    df.loc[df.index[0], 'raw_prev_position'] = df.loc[df.index[0], 'raw_position']

    all_ids_set = set(all_asset_ids)
    def get_raw_strat_ret(row, fee):
        pos = int(row['raw_position'])
        if pos == 0:
            gross = 0.0
        else:
            ret_val = row[f'ret_{pos}']
            gross = ret_val if pd.notna(ret_val) else 0.0
        prev = int(row['raw_prev_position'])
        cost = 0.0
        if prev != pos:
            if prev in all_ids_set: cost += fee
            if pos in all_ids_set: cost += fee
        return (1 + gross) * (1 - cost) - 1

    df['raw_strat_ret'] = df.apply(lambda r: get_raw_strat_ret(r, FEE), axis=1)
    df['raw_strat_nav'] = (1 + df['raw_strat_ret']).cumprod()
    df['raw_cummax'] = df['raw_strat_nav'].cummax()
    df['raw_dd'] = df['raw_strat_nav'] / df['raw_cummax'] - 1
    return df, all_asset_ids


# ===== 3. 熔断 =====
def apply_circuit_breaker(df, all_ids):
    raw_pos = df['raw_position'].values
    raw_dd = df['raw_dd'].values
    safe_havens = df['safe_haven'].values
    n = len(df)
    in_cb = False
    final_position = []
    for i in range(n):
        sig = int(raw_pos[i])
        dd = raw_dd[i]
        safe = int(safe_havens[i])
        if not in_cb:
            if dd < -DD_TRIGGER and sig != safe:
                in_cb = True
                final_position.append(safe)
            else:
                final_position.append(sig)
        else:
            if dd > -DD_RELEASE:
                in_cb = False
                final_position.append(sig)
            else:
                final_position.append(safe)
    return np.array(final_position)


def compute_v14_ret(df, all_ids, pos, fee):
    n = len(df)
    prev_pos = np.concatenate([[pos[0]], pos[:-1]])
    rets = np.zeros(n)
    all_ids_set = set(all_ids)
    for i in range(n):
        p = int(pos[i])
        if p == 0:
            gross = 0.0
        else:
            ret_val = df[f'ret_{p}'].iloc[i]
            gross = ret_val if pd.notna(ret_val) else 0.0
        cost = 0.0
        if int(prev_pos[i]) != p:
            if int(prev_pos[i]) in all_ids_set: cost += fee
            if p in all_ids_set: cost += fee
        rets[i] = (1 + gross) * (1 - cost) - 1
    return rets


# ===== 4. 跑各时段 =====
periods_config = {
    '近20年': last_date - pd.DateOffset(years=20),
    '近10年': last_date - pd.DateOffset(years=10),
    '近5年':  last_date - pd.DateOffset(years=5),
    '近3年':  last_date - pd.DateOffset(years=3),
    '近1年':  last_date - pd.DateOffset(years=1),
    '2013年以来': pd.Timestamp('2013-01-01'),
}

pools = [
    (OLD_STOCKS, '原标的池(8只)'),
    (NEW_STOCKS, '新标的池(9只)'),
]

results = {}
for stock_list, pool_label in pools:
    print(f"\n=== {pool_label} ===")
    p_results = {}
    for pname in ['近20年','近10年','近5年','近3年','近1年','2013年以来']:
        sd = periods_config[pname]
        df, all_ids = build_merged_data(sd, last_date, stock_list)
        pos_v14 = apply_circuit_breaker(df, all_ids)
        v14_rets = compute_v14_ret(df, all_ids, pos_v14, FEE)
        df['v14_ret'] = v14_rets
        df['v14_pos'] = pos_v14
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
            })

        total_ret = (1 + df['v14_ret']).prod() - 1
        nav_all = (1 + df['v14_ret']).cumprod()
        mdd_all = ((nav_all - nav_all.cummax()) / nav_all.cummax()).min()
        std_all = df['v14_ret'].std()
        sharpe_all = np.sqrt(252) * df['v14_ret'].mean() / std_all if std_all > 0 else 0
        ann_all = (1 + total_ret) ** (252/len(df)) - 1
        total_switches = int(np.sum(np.diff(pos_v14) != 0))

        p_results[pname] = {
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
                'switches': total_switches,
            },
        }
        print(f"  {pname}: 总收益={float(total_ret)*100:+.2f}%, 夏普={float(sharpe_all):.2f}, 回撤={float(mdd_all)*100:.2f}%, 切换{total_switches}次")
    results[pool_label] = p_results

with open(os.path.join(BASE_DIR, 'v14_new_pool_compare.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\n数据已保存到 v14_new_pool_compare.json")


# ===== 5. 生成HTML =====
old_names_str = '上证50·创业板50·纳斯达克100·沪深300·中证500·中证1000·标普500·科创50'
new_names_str = '创业板50·纳斯达克100·中证500·中证1000·标普500·科创50·中证A500·北证50·中证A50'

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14标的池替换对比：去上证50+沪深300，加中证A500+北证50+中证A50</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Microsoft YaHei','Segoe UI',sans-serif; background:#f5f6fa; color:#333; padding:20px; }}
h1 {{ text-align:center; font-size:22px; margin-bottom:5px; }}
.sub {{ text-align:center; font-size:13px; color:#666; margin-bottom:20px; }}
.note {{ background:#fff8e1; border:1px solid #ffe082; border-radius:6px; padding:12px 16px; margin-bottom:16px; font-size:13px; color:#5d4037; line-height:1.8; }}
.summary-grid {{ display:grid; grid-template-columns:repeat(6,1fr); gap:10px; margin-bottom:24px; }}
.summary-card {{ background:#fff; border-radius:8px; padding:12px; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.06); }}
.summary-card h3 {{ font-size:13px; color:#666; margin-bottom:6px; }}
.summary-card .v-row {{ display:flex; justify-content:center; gap:6px; margin:2px 0; font-size:12px; }}
.summary-card .v-label {{ font-size:10px; min-width:70px; text-align:right; color:#888; }}
.summary-card .v-val {{ font-weight:700; min-width:60px; text-align:left; }}
.period-card {{ background:#fff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.08); margin-bottom:24px; overflow:hidden; }}
.period-header {{ background:linear-gradient(135deg,#00897b,#00695c); color:#fff; padding:14px 20px; }}
.period-header h2 {{ font-size:18px; margin-bottom:4px; }}
.period-header .info {{ font-size:13px; opacity:0.9; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ background:#f8f9fa; padding:8px 4px; text-align:center; font-weight:600; border-bottom:2px solid #e0e0e0; white-space:nowrap; }}
td {{ padding:6px 4px; text-align:center; border-bottom:1px solid #eee; }}
tr:hover td {{ background:#f8fffe; }}
.pos {{ color:#e74c3c; font-weight:600; }}
.neg {{ color:#27ae60; font-weight:600; }}
.col-old {{ background:#e3f2fd; }}
.col-new {{ background:#e8f5e9; }}
.diff-pos {{ color:#e74c3c; font-weight:600; }}
.diff-neg {{ color:#27ae60; font-weight:600; }}
.overall-row {{ background:#fffde7 !important; font-weight:600; }}
.overall-row td {{ border-top:2px solid #f0e68c; border-bottom:2px solid #f0e68c; }}
</style>
</head>
<body>
<h1>V14标的池替换对比</h1>
<div class="sub">MA20轮动 · 费率万0.5 · 5%/4%熔断 · 动态避险v2(金>20日MA→黄金ETF,金<=20日MA→国债) · open-to-open</div>
<div class="note">
<b>标的池变更：</b><br>
&nbsp;&nbsp;• <b>原标的池(8只)</b>：{old_names_str}<br>
&nbsp;&nbsp;• <b>新标的池(9只)</b>：{new_names_str}<br>
<span style="color:#666">变更：去掉上证50、沪深300，新增中证A500(2004起)、北证50(2022起)、中证A50(2014起)</span>
</div>
'''

# 汇总卡片
html += '<div class="summary-grid">'
for pname in ['近20年','近10年','近5年','近3年','近1年','2013年以来']:
    html += f'<div class="summary-card"><h3>{pname}</h3>'
    for pool_label in ['原标的池(8只)', '新标的池(9只)']:
        o = results[pool_label][pname]['overall']
        ret_cls = 'pos' if o['total_ret'] >= 0 else 'neg'
        short = '原池' if '原' in pool_label else '新池'
        html += f'<div class="v-row"><span class="v-label">{short}</span><span class="v-val {ret_cls}">{o["total_ret"]:+.1f}%</span></div>'
    diff = results['新标的池(9只)'][pname]['overall']['total_ret'] - results['原标的池(8只)'][pname]['overall']['total_ret']
    diff_cls = 'diff-pos' if diff >= 0 else 'diff-neg'
    html += f'<div class="v-row"><span class="v-label" style="color:#888">新-原</span><span class="v-val {diff_cls}">{diff:+.1f}%</span></div>'
    html += '</div>'
html += '</div>'

# 各时段表格
for pname in ['近20年','近10年','近5年','近3年','近1年','2013年以来']:
    r = results['原标的池(8只)'][pname]
    html += f'''<div class="period-card">
    <div class="period-header">
        <h2>{pname}</h2>
        <div class="info">{r["start"]} ~ {r["end"]} · {r["n_days"]}天</div>
    </div>
    <table>
    <thead><tr>
        <th rowspan="2">年份</th>
        <th rowspan="2">交易日</th>
        <th colspan="2" style="border-right:1px solid #ddd;background:#e3f2fd">原标的池(8只)</th>
        <th colspan="2" style="border-right:1px solid #ddd;background:#e8f5e9">新标的池(9只)</th>
        <th rowspan="2">新-原</th>
    </tr><tr>
        <th class="col-old">收益</th>
        <th class="col-old">回撤</th>
        <th class="col-new">收益</th>
        <th class="col-new">回撤</th>
    </tr></thead><tbody>'''

    all_years = sorted(set([y['year'] for y in r['yearly']]))
    for y in all_years:
        yo = next((yy for yy in results['原标的池(8只)'][pname]['yearly'] if yy['year']==y), None)
        yn = next((yy for yy in results['新标的池(9只)'][pname]['yearly'] if yy['year']==y), None)

        html += f'<tr><td>{y}</td>'
        html += f'<td>{yo["n_days"] if yo else (yn["n_days"] if yn else "-")}</td>'

        if yo:
            ret_cls = 'pos' if yo['ret'] >= 0 else 'neg'
            html += f'<td class="col-old {ret_cls}">{yo["ret"]:+.2f}%</td>'
            html += f'<td class="col-old">{yo["mdd"]:.2f}%</td>'
        else:
            html += '<td class="col-old">-</td><td class="col-old">-</td>'

        if yn:
            ret_cls = 'pos' if yn['ret'] >= 0 else 'neg'
            html += f'<td class="col-new {ret_cls}">{yn["ret"]:+.2f}%</td>'
            html += f'<td class="col-new">{yn["mdd"]:.2f}%</td>'
        else:
            html += '<td class="col-new">-</td><td class="col-new">-</td>'

        if yo and yn:
            diff = yn['ret'] - yo['ret']
            diff_cls = 'diff-pos' if diff >= 0 else 'diff-neg'
            html += f'<td class="{diff_cls}">{diff:+.2f}%</td>'
        else:
            html += '<td>-</td>'
        html += '</tr>'

    # 整体行
    html += '<tr class="overall-row"><td>整体</td><td>-</td>'
    for pool_label in ['原标的池(8只)', '新标的池(9只)']:
        o = results[pool_label][pname]['overall']
        ret_cls = 'pos' if o['total_ret'] >= 0 else 'neg'
        col_cls = 'col-old' if '原' in pool_label else 'col-new'
        html += f'<td class="{col_cls} {ret_cls}">{o["total_ret"]:+.2f}%</td>'
        html += f'<td class="{col_cls}">{o["mdd"]:.2f}%</td>'
    diff = results['新标的池(9只)'][pname]['overall']['total_ret'] - results['原标的池(8只)'][pname]['overall']['total_ret']
    diff_cls = 'diff-pos' if diff >= 0 else 'diff-neg'
    html += f'<td class="{diff_cls}">{diff:+.2f}%</td></tr>'

    # 统计行
    html += '<tr><td colspan="7" style="background:#f5f5f5;font-size:11px;color:#666;text-align:left;padding:8px 16px">'
    for pool_label in ['原标的池(8只)', '新标的池(9只)']:
        o = results[pool_label][pname]['overall']
        short = '原池' if '原' in pool_label else '新池'
        html += f'<b>{short}</b>: 年化{o["ann_ret"]:+.2f}% · 夏普{o["sharpe"]:.2f} · 回撤{o["mdd"]:.2f}% · 切换{o["switches"]}次 &nbsp;|&nbsp; '
    html += '</td></tr>'

    html += '</tbody></table></div>'

html += '''
<div style="text-align:center;font-size:12px;color:#999;margin-top:20px;">
收益口径: open-to-open · 蓝色列=原标的池 · 绿色列=新标的池<br>
新标的池去掉上证50、沪深300，新增中证A500(2004起)、北证50(2022起)、中证A50(2014起) | 北证50和中证A50数据较晚，之前不参与选股
</div>
</body></html>'''

out_path = os.path.join(BASE_DIR, 'v14_new_pool_compare.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nHTML报告已生成: {out_path}")
