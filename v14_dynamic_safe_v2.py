# -*- coding: utf-8 -*-
"""V14动态避险资产策略v2：黄金价格高于20日均线选黄金ETF，低于选国债

策略定义：
  - 决策日期 = T日（执行日）
  - 决策bf = (T-1日收盘价 / T-1日MA20) - 1
  - T日开盘执行，收益口径 open-to-open
  - 5%回撤触发熔断，4%解除
  - 费率万0.5(0.00005)
  
避险资产选择规则：
  - 黄金ETF收盘价 > 20日均线 → 避险资产 = 黄金ETF
  - 黄金ETF收盘价 <= 20日均线 → 避险资产 = 国债
  - 20日MA不可用或2013-07-29之前 → 国债
  
对比3个版本：
  A. 原版：始终国债
  B. 黄金ETF版：2013-07-29起始终黄金ETF
  C. 动态版：根据黄金vs20日MA动态选择
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

# ===== 1.5 计算黄金20日均线 =====
print("\n计算黄金20日均线...")
gold_daily = dfs[GOLD][['date', f'close_{GOLD}']].copy()
gold_daily['ma20'] = gold_daily[f'close_{GOLD}'].rolling(20).mean()
gold_daily['above_ma'] = gold_daily[f'close_{GOLD}'] > gold_daily['ma20']
gold_valid = gold_daily.dropna(subset=['ma20'])
print(f"  20日MA有效起始: {gold_valid['date'].min().date()}")
print(f"  20日MA有效数据: {len(gold_valid)}天")

# 统计在均线上下的天数
above_count = gold_valid['above_ma'].sum()
below_count = (~gold_valid['above_ma']).sum()
print(f"  高于20日MA: {above_count}天 ({above_count/len(gold_valid)*100:.1f}%)")
print(f"  低于20日MA: {below_count}天 ({below_count/len(gold_valid)*100:.1f}%)")


# ===== 2. 构建合并数据 =====
def build_merged_data(start_date, end_date, safe_mode='bond'):
    """构建合并数据
    safe_mode: 'bond'=始终国债, 'gold'=始终黄金ETF, 'dynamic'=动态选择
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
    if safe_mode == 'bond':
        df['safe_haven'] = BOND
    elif safe_mode == 'gold':
        df['safe_haven'] = np.where(df['date'] >= GOLD_START, GOLD, BOND)
    elif safe_mode == 'dynamic':
        # 计算黄金20日MA
        df[f'gold_ma20'] = df[f'close_{GOLD}'].rolling(20).mean()
        # 黄金收盘价 > 20日MA → 黄金ETF；<= 20日MA → 国债
        # 2013-07-29之前或20日MA不可用时 → 国债
        df['safe_haven'] = BOND  # 默认国债
        mask_gold_available = df['date'] >= GOLD_START
        mask_ma_available = df['gold_ma20'].notna()
        mask_above_ma = df[f'close_{GOLD}'] > df['gold_ma20']
        # 条件：有黄金数据 + 有20日MA + 收盘价高于MA → 黄金ETF
        df.loc[mask_gold_available & mask_ma_available & mask_above_ma, 'safe_haven'] = GOLD

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
def apply_circuit_breaker(df, all_ids):
    """应用熔断逻辑，使用每行的safe_haven作为避险资产"""
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

variants = [
    ('bond', '原版(国债避险)'),
    ('gold', '黄金ETF避险(2013起)'),
    ('dynamic', '动态避险(金>20日MA→黄金,金<=20日MA→国债)'),
]

results = {}
for vkey, vlabel in variants:
    print(f"\n=== {vlabel} ===")
    v_results = {}
    for pname in ['近20年','近10年','近5年','近3年','近1年','2013年以来']:
        sd = periods_config[pname]
        df, all_ids = build_merged_data(sd, last_date, safe_mode=vkey)
        pos_v14 = apply_circuit_breaker(df, all_ids)
        v14_rets = compute_v14_ret(df, all_ids, pos_v14, FEE)
        df['v14_ret'] = v14_rets
        df['v14_pos'] = pos_v14
        df['year'] = df['date'].dt.year

        # 统计避险资产使用情况
        safe_havens = df['safe_haven'].values
        gold_safe_days = int(np.sum((safe_havens == GOLD) & (pos_v14 == GOLD)))
        bond_safe_days = int(np.sum((safe_havens == BOND) & (pos_v14 == BOND)))

        years = sorted(df['year'].unique())
        yearly_list = []
        for y in years:
            sub = df[df['year'] == y].copy()
            ny = len(sub)
            year_ret = (1 + sub['v14_ret']).prod() - 1
            year_nav = (1 + sub['v14_ret']).cumprod()
            year_mdd = ((year_nav - year_nav.cummax()) / year_nav.cummax()).min()
            
            # 当年避险资产使用统计
            sub_safe = sub['safe_haven'].values
            sub_pos = sub['v14_pos'].values
            y_gold_days = int(np.sum((sub_safe == GOLD) & (sub_pos == GOLD)))
            y_bond_days = int(np.sum((sub_safe == BOND) & (sub_pos == BOND)))
            
            # 动态版统计：当年有多少天选黄金ETF作为避险，多少天选国债
            if vkey == 'dynamic':
                y_gold_haven = int(np.sum(sub_safe == GOLD))
                y_bond_haven = int(np.sum(sub_safe == BOND))
            else:
                y_gold_haven = 0
                y_bond_haven = 0
            
            yearly_list.append({
                'year': int(y),
                'n_days': int(ny),
                'ret': round(float(year_ret)*100, 2),
                'mdd': round(float(year_mdd)*100, 2),
                'gold_safe_days': y_gold_days,
                'bond_safe_days': y_bond_days,
                'gold_haven_days': y_gold_haven,
                'bond_haven_days': y_bond_haven,
                'switches': int(np.sum(np.diff(sub['v14_pos'].values) != 0)),
            })

        total_ret = (1 + df['v14_ret']).prod() - 1
        nav_all = (1 + df['v14_ret']).cumprod()
        mdd_all = ((nav_all - nav_all.cummax()) / nav_all.cummax()).min()
        std_all = df['v14_ret'].std()
        sharpe_all = np.sqrt(252) * df['v14_ret'].mean() / std_all if std_all > 0 else 0
        ann_all = (1 + total_ret) ** (252/len(df)) - 1
        total_switches = int(np.sum(np.diff(pos_v14) != 0))

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
                'gold_safe_days': gold_safe_days,
                'bond_safe_days': bond_safe_days,
            },
        }
        print(f"  {pname}: 总收益={float(total_ret)*100:+.2f}%, 夏普={float(sharpe_all):.2f}, 回撤={float(mdd_all)*100:.2f}%, "
              f"避险持黄金{gold_safe_days}天/国债{bond_safe_days}天, 切换{total_switches}次")
    results[vkey] = v_results

with open(os.path.join(BASE_DIR, 'v14_dynamic_safe_v2.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\n数据已保存到 v14_dynamic_safe_v2.json")


# ===== 5. 生成HTML =====
html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14动态避险策略v2：黄金vs20日均线选择避险资产</title>
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
.col-bond {{ background:#e3f2fd; }}
.col-gold {{ background:#fff8e1; }}
.col-dyn {{ background:#e8f5e9; }}
.diff-pos {{ color:#e74c3c; font-weight:600; }}
.diff-neg {{ color:#27ae60; font-weight:600; }}
.overall-row {{ background:#fffde7 !important; font-weight:600; }}
.overall-row td {{ border-top:2px solid #f0e68c; border-bottom:2px solid #f0e68c; }}
.gold-tag {{ display:inline-block; padding:1px 5px; border-radius:3px; font-size:10px; background:#ff6f00; color:#fff; }}
.bond-tag {{ display:inline-block; padding:1px 5px; border-radius:3px; font-size:10px; background:#1565c0; color:#fff; }}
</style>
</head>
<body>
<h1>V14动态避险策略：黄金价格vs20日均线选择避险资产</h1>
<div class="sub">MA20轮动 · 费率万0.5 · 5%/4%熔断 · 决策bf=(T-1收盘/T-1 MA20)-1 · T日开盘执行 · open-to-open</div>
<div class="note">
<b>避险资产选择规则：</b><br>
&nbsp;&nbsp;• <b>原版</b>：避险资产始终为国债<br>
&nbsp;&nbsp;• <b>黄金ETF版</b>：2013-07-29起避险资产始终为黄金ETF<br>
&nbsp;&nbsp;• <b>动态版</b>：黄金ETF收盘价 &gt; 20日均线 → 避险选黄金ETF；黄金ETF收盘价 ≤ 20日均线 → 避险选国债<br>
<span style="color:#666">20日MA从黄金ETF有数据后20个交易日起有效。黄金高于20日MA时认为处于上升趋势，选黄金避险；低于时认为下行，选国债避险。</span>
</div>
'''

# 汇总卡片
html += '<div class="summary-grid">'
for pname in ['近20年','近10年','近5年','近3年','近1年','2013年以来']:
    html += f'<div class="summary-card"><h3>{pname}</h3>'
    for vkey, vlabel in variants:
        o = results[vkey][pname]['overall']
        ret_cls = 'pos' if o['total_ret'] >= 0 else 'neg'
        short_label = vlabel.split('(')[0]
        html += f'<div class="v-row"><span class="v-label">{short_label}</span><span class="v-val {ret_cls}">{o["total_ret"]:+.1f}%</span></div>'
    # 动态版vs原版差异
    diff = results['dynamic'][pname]['overall']['total_ret'] - results['bond'][pname]['overall']['total_ret']
    diff_cls = 'diff-pos' if diff >= 0 else 'diff-neg'
    html += f'<div class="v-row"><span class="v-label" style="color:#888">动态-原版</span><span class="v-val {diff_cls}">{diff:+.1f}%</span></div>'
    html += '</div>'
html += '</div>'

# 各时段表格（重点展示2013年以来和近20年）
for pname in ['2013年以来','近20年','近10年','近5年','近3年','近1年']:
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
        <th colspan="2" style="border-right:1px solid #ddd;background:#e3f2fd">原版(国债)</th>
        <th colspan="2" style="border-right:1px solid #ddd;background:#fff8e1">黄金ETF版</th>
        <th colspan="3" style="border-right:1px solid #ddd;background:#e8f5e9">动态版</th>
        <th rowspan="2">动态-原版</th>
    </tr><tr>
        <th class="col-bond">收益</th>
        <th class="col-bond">回撤</th>
        <th class="col-gold">收益</th>
        <th class="col-gold">回撤</th>
        <th class="col-dyn">收益</th>
        <th class="col-dyn">回撤</th>
        <th class="col-dyn">避险配置</th>
    </tr></thead><tbody>'''

    all_years = sorted(set([y['year'] for y in r['yearly']]))
    for y in all_years:
        yb = next((yy for yy in results['bond'][pname]['yearly'] if yy['year']==y), None)
        yg = next((yy for yy in results['gold'][pname]['yearly'] if yy['year']==y), None)
        yd = next((yy for yy in results['dynamic'][pname]['yearly'] if yy['year']==y), None)
        
        html += f'<tr><td>{y}</td>'
        html += f'<td>{yb["n_days"] if yb else (yg["n_days"] if yg else yd["n_days"])}</td>'
        
        # 原版
        if yb:
            ret_cls = 'pos' if yb['ret'] >= 0 else 'neg'
            html += f'<td class="col-bond {ret_cls}">{yb["ret"]:+.2f}%</td>'
            html += f'<td class="col-bond">{yb["mdd"]:.2f}%</td>'
        else:
            html += '<td class="col-bond">-</td><td class="col-bond">-</td>'
        
        # 黄金ETF版
        if yg:
            ret_cls = 'pos' if yg['ret'] >= 0 else 'neg'
            html += f'<td class="col-gold {ret_cls}">{yg["ret"]:+.2f}%</td>'
            html += f'<td class="col-gold">{yg["mdd"]:.2f}%</td>'
        else:
            html += '<td class="col-gold">-</td><td class="col-gold">-</td>'
        
        # 动态版
        if yd:
            ret_cls = 'pos' if yd['ret'] >= 0 else 'neg'
            html += f'<td class="col-dyn {ret_cls}">{yd["ret"]:+.2f}%</td>'
            html += f'<td class="col-dyn">{yd["mdd"]:.2f}%</td>'
            # 避险配置：显示黄金天数/国债天数
            gh = yd['gold_haven_days']
            bh = yd['bond_haven_days']
            haven_str = ''
            if gh > 0:
                haven_str += f'<span class="gold-tag">金{gh}天</span>'
            if bh > 0:
                if haven_str:
                    haven_str += ' '
                haven_str += f'<span class="bond-tag">债{bh}天</span>'
            if not haven_str:
                haven_str = '-'
            html += f'<td class="col-dyn" style="font-size:11px">{haven_str}</td>'
        else:
            html += '<td class="col-dyn">-</td><td class="col-dyn">-</td><td class="col-dyn">-</td>'
        
        # 差异
        if yb and yd:
            diff = yd['ret'] - yb['ret']
            diff_cls = 'diff-pos' if diff >= 0 else 'diff-neg'
            html += f'<td class="{diff_cls}">{diff:+.2f}%</td>'
        else:
            html += '<td>-</td>'
        html += '</tr>'

    # 整体行
    html += '<tr class="overall-row"><td>整体</td><td>-</td>'
    for vkey in ['bond', 'gold', 'dynamic']:
        o = results[vkey][pname]['overall']
        ret_cls = 'pos' if o['total_ret'] >= 0 else 'neg'
        col_cls = 'col-bond' if vkey == 'bond' else ('col-gold' if vkey == 'gold' else 'col-dyn')
        html += f'<td class="{col_cls} {ret_cls}">{o["total_ret"]:+.2f}%</td>'
        html += f'<td class="{col_cls}">{o["mdd"]:.2f}%</td>'
        if vkey == 'dynamic':
            gs = o['gold_safe_days']
            bs = o['bond_safe_days']
            haven_str = ''
            if gs > 0:
                haven_str += f'<span class="gold-tag">金{gs}天</span>'
            if bs > 0:
                if haven_str:
                    haven_str += ' '
                haven_str += f'<span class="bond-tag">债{bs}天</span>'
            html += f'<td class="{col_cls}" style="font-size:11px">{haven_str}</td>'
    diff = results['dynamic'][pname]['overall']['total_ret'] - results['bond'][pname]['overall']['total_ret']
    diff_cls = 'diff-pos' if diff >= 0 else 'diff-neg'
    html += f'<td class="{diff_cls}">{diff:+.2f}%</td></tr>'

    # 统计行
    html += '<tr><td colspan="10" style="background:#f5f5f5;font-size:11px;color:#666;text-align:left;padding:8px 16px">'
    for vkey, vlabel in variants:
        o = results[vkey][pname]['overall']
        short = vlabel.split('(')[0]
        html += f'<b>{short}</b>: 年化{o["ann_ret"]:+.2f}% · 夏普{o["sharpe"]:.2f} · 回撤{o["mdd"]:.2f}% · 切换{o["switches"]}次'
        if vkey == 'dynamic' and o['gold_safe_days'] > 0:
            html += f' <span class="gold-tag">避险持金{o["gold_safe_days"]}天</span> <span class="bond-tag">避险持债{o["bond_safe_days"]}天</span>'
        html += ' &nbsp;|&nbsp; '
    html += '</td></tr>'

    html += '</tbody></table></div>'

html += '''
<div style="text-align:center;font-size:12px;color:#999;margin-top:20px;">
收益口径: open-to-open · 蓝色列=原版(国债) · 黄色列=黄金ETF版 · 绿色列=动态版<br>
动态版避险选择：黄金ETF收盘价&gt;20日均线→持黄金ETF，≤20日均线→持国债 | 20日MA基于日频收盘价计算
</div>
</body></html>'''

out_path = os.path.join(BASE_DIR, 'v14_dynamic_safe_v2.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nHTML报告已生成: {out_path}")
