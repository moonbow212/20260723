# -*- coding: utf-8 -*-
"""V14避险资产对比：国债 vs 黄金ETF(2013/7/29起)
策略定义：
  - 决策日期 = T日（执行日）
  - 决策bf = (T-1日收盘价 / T-1日MA20) - 1
  - T日开盘执行，收益口径 open-to-open
  - 5%回撤触发熔断，4%解除
  - 费率万0.5(0.00005)
  
原版：避险资产始终为国债
黄金版：2013-07-29起避险资产改为黄金ETF，之前仍为国债
"""
import pandas as pd
import numpy as np
import json, os

DD_TRIGGER = 0.05
DD_RELEASE = 0.04
FEE = 0.00005
MA_PERIOD = 20
GOLD_START = pd.Timestamp('2013-07-29')

STOCK_ALL = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9
GOLD = 10
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债',10:'黄金ETF'}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== 1. 读取数据 =====
print("读取数据...")
dfs = {}
for i in STOCK_ALL + [BOND, GOLD]:
    name = names[i]
    csv_path = os.path.join(BASE_DIR, 'data', f'{i}_{name}.csv')
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"未找到 {name} 数据文件 {csv_path}")
    d = pd.read_csv(csv_path, parse_dates=['date'])
    d = d[['date', 'open', 'close']].rename(columns={'open': f'open_{i}', 'close': f'close_{i}'})
    d = d.sort_values('date').reset_index(drop=True)
    if i in STOCK_ALL:
        d[f'ma{MA_PERIOD}_{i}'] = d[f'close_{i}'].rolling(MA_PERIOD).mean()
        d[f'bf{MA_PERIOD}_{i}'] = d[f'close_{i}'] / d[f'ma{MA_PERIOD}_{i}'] - 1
        d[f'ratio{MA_PERIOD}_{i}'] = d[f'close_{i}'] / d[f'ma{MA_PERIOD}_{i}']
    dfs[i] = d

last_date = dfs[BOND]['date'].max()
print(f"数据最新日期: {last_date.date()}")
print(f"黄金ETF数据范围: {dfs[GOLD]['date'].min().date()} ~ {dfs[GOLD]['date'].max().date()}")


# ===== 2. 构建合并数据 =====
def build_merged_data(start_date, end_date, use_gold=False):
    """构建合并数据
    use_gold: True=2013-07-29后避险资产用黄金ETF, False=始终用国债
    """
    # 以国债日历为基础
    df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)

    # 合并股票数据
    for i in STOCK_ALL:
        ma_col = f'ma{MA_PERIOD}_{i}'
        bf_col = f'bf{MA_PERIOD}_{i}'
        ratio_col = f'ratio{MA_PERIOD}_{i}'
        cols = ['date', f'open_{i}', f'close_{i}', ma_col, bf_col, ratio_col]
        df = pd.merge(df, dfs[i][cols], on='date', how='left')

    # 合并黄金ETF数据
    gold_cols = ['date', f'open_{GOLD}', f'close_{GOLD}']
    df = pd.merge(df, dfs[GOLD][gold_cols], on='date', how='left')

    # 确定避险资产id
    if use_gold:
        df['safe_haven'] = np.where(df['date'] >= GOLD_START, GOLD, BOND)
    else:
        df['safe_haven'] = BOND

    # 计算所有资产的收益（open-to-open）
    all_asset_ids = STOCK_ALL + [BOND, GOLD]
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
        for i in STOCK_ALL:
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

    # 计算raw策略收益（用于V8回撤判断）
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
def apply_circuit_breaker(df, all_ids, use_gold=False):
    """应用熔断逻辑
    use_gold: True=避险用黄金ETF(2013后), False=避险用国债
    """
    raw_pos = df['raw_position'].values
    raw_dd = df['raw_dd'].values
    safe_havens = df['safe_haven'].values  # 每行的避险资产id
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
}

variants = [
    ('bond', '原版(国债避险)'),
    ('gold', '黄金ETF避险(2013起)'),
]

results = {}
for vkey, vlabel in variants:
    use_gold = (vkey == 'gold')
    v_results = {}
    for pname in ['近20年','近10年','近5年','近3年','近1年']:
        sd = periods_config[pname]
        df, all_ids = build_merged_data(sd, last_date, use_gold=use_gold)
        pos_v14 = apply_circuit_breaker(df, all_ids, use_gold=use_gold)
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
            # 统计避险资产持仓天数
            if use_gold:
                bond_days = int((sub['v14_pos'] == BOND).sum())
                gold_days = int((sub['v14_pos'] == GOLD).sum())
                safe_days = bond_days + gold_days
            else:
                safe_days = int((sub['v14_pos'] == BOND).sum())
                gold_days = 0
            yearly_list.append({
                'year': int(y),
                'n_days': int(ny),
                'ret': round(float(year_ret)*100, 2),
                'mdd': round(float(year_mdd)*100, 2),
                'safe_days': safe_days,
                'gold_days': gold_days,
                'switches': int(np.sum(np.diff(sub['v14_pos'].values) != 0)),
            })

        total_ret = (1 + df['v14_ret']).prod() - 1
        nav_all = (1 + df['v14_ret']).cumprod()
        mdd_all = ((nav_all - nav_all.cummax()) / nav_all.cummax()).min()
        std_all = df['v14_ret'].std()
        sharpe_all = np.sqrt(252) * df['v14_ret'].mean() / std_all if std_all > 0 else 0
        ann_all = (1 + total_ret) ** (252/len(df)) - 1
        total_switches = int(np.sum(np.diff(pos_v14) != 0))
        
        if use_gold:
            total_bond_days = int((pos_v14 == BOND).sum())
            total_gold_days = int((pos_v14 == GOLD).sum())
            total_safe_days = total_bond_days + total_gold_days
        else:
            total_safe_days = int((pos_v14 == BOND).sum())
            total_gold_days = 0

        v_results[pname] = {
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
                'safe_days': total_safe_days,
                'gold_days': total_gold_days,
            },
        }
        print(f"  {vlabel} {pname}: 总收益={float(total_ret)*100:+.2f}%, 夏普={float(sharpe_all):.2f}, 回撤={float(mdd_all)*100:.2f}%, "
              f"避险{total_safe_days}天(其中黄金{total_gold_days}天), 切换{total_switches}次")
    results[vkey] = v_results

with open(os.path.join(BASE_DIR, 'v14_gold_compare.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\n数据已保存到 v14_gold_compare.json")


# ===== 5. 生成HTML =====
html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14避险资产对比：国债 vs 黄金ETF(2013起)</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Microsoft YaHei','Segoe UI',sans-serif; background:#f5f6fa; color:#333; padding:20px; }}
h1 {{ text-align:center; font-size:22px; margin-bottom:5px; }}
.sub {{ text-align:center; font-size:13px; color:#666; margin-bottom:20px; }}
.note {{ background:#fff8e1; border:1px solid #ffe082; border-radius:6px; padding:10px 16px; margin-bottom:16px; font-size:13px; color:#5d4037; }}
.summary-grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:24px; }}
.summary-card {{ background:#fff; border-radius:8px; padding:14px; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.06); }}
.summary-card h3 {{ font-size:14px; color:#666; margin-bottom:8px; }}
.summary-card .v-row {{ display:flex; justify-content:center; gap:8px; margin:3px 0; font-size:13px; }}
.summary-card .v-label {{ font-size:11px; min-width:90px; text-align:right; color:#888; }}
.summary-card .v-val {{ font-weight:700; min-width:65px; text-align:left; }}
.period-card {{ background:#fff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.08); margin-bottom:24px; overflow:hidden; }}
.period-header {{ background:linear-gradient(135deg,#f57f17,#ff8f00); color:#fff; padding:14px 20px; }}
.period-header h2 {{ font-size:18px; margin-bottom:4px; }}
.period-header .info {{ font-size:13px; opacity:0.9; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ background:#f8f9fa; padding:8px 5px; text-align:center; font-weight:600; border-bottom:2px solid #e0e0e0; white-space:nowrap; }}
td {{ padding:7px 5px; text-align:center; border-bottom:1px solid #eee; }}
tr:hover td {{ background:#fffde7; }}
.pos {{ color:#e74c3c; font-weight:600; }}
.neg {{ color:#27ae60; font-weight:600; }}
.col-bond {{ background:#e3f2fd; }}
.col-gold {{ background:#fff8e1; }}
.col-safe {{ background:#fce4ec; }}
.diff-pos {{ color:#e74c3c; font-weight:600; }}
.diff-neg {{ color:#27ae60; font-weight:600; }}
.overall-row {{ background:#fffde7 !important; font-weight:600; }}
.overall-row td {{ border-top:2px solid #f0e68c; border-bottom:2px solid #f0e68c; }}
.gold-tag {{ display:inline-block; padding:1px 5px; border-radius:3px; font-size:10px; background:#ff6f00; color:#fff; }}
</style>
</head>
<body>
<h1>V14避险资产对比：国债 vs 黄金ETF(2013/7/29起)</h1>
<div class="sub">MA20 · 费率万0.5 · 5%/4%熔断 · 8股+避险资产动态标的池 · 决策bf=(T-1收盘/T-1 MA20)-1 · T日开盘执行 · open-to-open</div>
<div class="note">
<b>原版</b>：避险资产始终为国债（熔断时和全部bf&lt;0时持国债）<br>
<b>黄金版</b>：2013-07-29起避险资产改为黄金ETF（华安黄金ETF 518880），之前仍为国债<br>
<span style="color:#666">黄金ETF从2.63涨到9.02（+243%），远超国债收益，但波动也更大。避险时持黄金意味着"避险"期间也有涨跌风险。</span>
</div>
'''

# 汇总卡片
html += '<div class="summary-grid">'
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    html += f'<div class="summary-card"><h3>{pname}</h3>'
    for vkey, vlabel in variants:
        o = results[vkey][pname]['overall']
        ret_cls = 'pos' if o['total_ret'] >= 0 else 'neg'
        html += f'<div class="v-row"><span class="v-label">{vlabel}</span><span class="v-val {ret_cls}">{o["total_ret"]:+.1f}%</span></div>'
    diff = results['gold'][pname]['overall']['total_ret'] - results['bond'][pname]['overall']['total_ret']
    diff_cls = 'diff-pos' if diff >= 0 else 'diff-neg'
    html += f'<div class="v-row"><span class="v-label" style="color:#888">差异</span><span class="v-val {diff_cls}">{diff:+.1f}%</span></div>'
    html += '</div>'
html += '</div>'

# 各时段表格
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results['bond'][pname]
    html += f'''<div class="period-card">
    <div class="period-header">
        <h2>{pname}</h2>
        <div class="info">{r["start"]} ~ {r["end"]} · {r["n_days"]}天</div>
    </div>
    <table>
    <thead><tr>
        <th rowspan="2">年份</th>
        <th rowspan="2">交易日</th>
        <th colspan="3" style="border-right:1px solid #ddd;background:#e3f2fd">原版(国债避险)</th>
        <th colspan="4" style="border-right:1px solid #ddd;background:#fff8e1">黄金ETF避险</th>
        <th rowspan="2">收益差异</th>
    </tr><tr>
        <th class="col-bond">收益</th>
        <th class="col-bond">回撤</th>
        <th class="col-bond">避险天数</th>
        <th class="col-gold">收益</th>
        <th class="col-gold">回撤</th>
        <th class="col-gold">避险天数</th>
        <th class="col-gold">黄金天数</th>
    </tr></thead><tbody>'''

    all_years = sorted(set([y['year'] for y in r['yearly']]))
    for y in all_years:
        yb = next((yy for yy in results['bond'][pname]['yearly'] if yy['year']==y), None)
        yg = next((yy for yy in results['gold'][pname]['yearly'] if yy['year']==y), None)
        html += f'<tr><td>{y}</td>'
        html += f'<td>{yb["n_days"] if yb else "-"}</td>'
        # 原版
        if yb:
            ret_cls = 'pos' if yb['ret'] >= 0 else 'neg'
            html += f'<td class="col-bond {ret_cls}">{yb["ret"]:+.2f}%</td>'
            html += f'<td class="col-bond">{yb["mdd"]:.2f}%</td>'
            html += f'<td class="col-safe">{yb["safe_days"]}</td>'
        else:
            html += '<td class="col-bond">-</td><td class="col-bond">-</td><td class="col-safe">-</td>'
        # 黄金版
        if yg:
            ret_cls = 'pos' if yg['ret'] >= 0 else 'neg'
            html += f'<td class="col-gold {ret_cls}">{yg["ret"]:+.2f}%</td>'
            html += f'<td class="col-gold">{yg["mdd"]:.2f}%</td>'
            html += f'<td class="col-safe">{yg["safe_days"]}</td>'
            html += f'<td class="col-gold">{yg["gold_days"] if yg["gold_days"] > 0 else "-"}</td>'
        else:
            html += '<td class="col-gold">-</td><td class="col-gold">-</td><td class="col-safe">-</td><td class="col-gold">-</td>'
        # 差异
        if yb and yg:
            diff = yg['ret'] - yb['ret']
            diff_cls = 'diff-pos' if diff >= 0 else 'diff-neg'
            html += f'<td class="{diff_cls}">{diff:+.2f}%</td>'
        else:
            html += '<td>-</td>'
        html += '</tr>'

    # 整体行
    html += '<tr class="overall-row"><td>整体</td><td>-</td>'
    for vkey in ['bond', 'gold']:
        o = results[vkey][pname]['overall']
        ret_cls = 'pos' if o['total_ret'] >= 0 else 'neg'
        col_cls = 'col-bond' if vkey == 'bond' else 'col-gold'
        html += f'<td class="{col_cls} {ret_cls}">{o["total_ret"]:+.2f}%</td>'
        html += f'<td class="{col_cls}">{o["mdd"]:.2f}%</td>'
        html += f'<td class="col-safe">{o["safe_days"]}</td>'
        if vkey == 'gold':
            html += f'<td class="{col_cls}">{o["gold_days"] if o["gold_days"] > 0 else "-"}</td>'
    diff = results['gold'][pname]['overall']['total_ret'] - results['bond'][pname]['overall']['total_ret']
    diff_cls = 'diff-pos' if diff >= 0 else 'diff-neg'
    html += f'<td class="{diff_cls}">{diff:+.2f}%</td></tr>'

    # 统计行
    html += '<tr><td colspan="9" style="background:#f5f5f5;font-size:11px;color:#666;text-align:left;padding:8px 16px">'
    for vkey, vlabel in variants:
        o = results[vkey][pname]['overall']
        html += f'<b>{vlabel}</b>: 年化{o["ann_ret"]:+.2f}% · 夏普{o["sharpe"]:.2f} · 回撤{o["mdd"]:.2f}% · 切换{o["switches"]}次 · 避险{o["safe_days"]}天'
        if vkey == 'gold' and o['gold_days'] > 0:
            html += f' <span class="gold-tag">黄金{o["gold_days"]}天</span>'
        html += ' &nbsp;|&nbsp; '
    html += '</td></tr>'

    html += '</tbody></table></div>'

html += '''
<div style="text-align:center;font-size:12px;color:#999;margin-top:20px;">
收益口径: open-to-open · 蓝色列=原版(国债避险) · 黄色列=黄金ETF避险 · 红底=避险持仓天数<br>
黄金ETF数据: 华安黄金ETF(518880) 2013-07-29~2026-07-22 | 避险时持黄金ETF意味着熔断/全部bf<0时不再持有国债而是持有黄金ETF
</div>
</body></html>'''

out_path = os.path.join(BASE_DIR, 'v14_gold_compare.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nHTML报告已生成: {out_path}")
