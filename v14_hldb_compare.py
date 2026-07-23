# -*- coding: utf-8 -*-
"""V14策略变体：国债替换为红利低波指数
当策略信号为国债（全bf<0）或熔断时，持有红利低波指数而非国债
对比原V14（持国债）的近10年逐年收益
"""
import pandas as pd
import numpy as np
import json, os

FEE = 0.0002
DD_TRIGGER = 0.05
DD_RELEASE = 0.04

STOCK_ALL = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9
HLDB = 10  # 红利低波
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债',10:'红利低波'}
all_names = {0:'空仓', 1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债',10:'红利低波'}

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
        d[f'ma20_{i}'] = d[f'close_{i}'].rolling(20).mean()
        d[f'bf_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}'] - 1
        d[f'ratio_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}']
    dfs[i] = d
    print(f"  {names[i]}: {d['date'].iloc[0].date()} ~ {d['date'].iloc[-1].date()}, {len(d)}条")

# 读取红利低波数据（同花顺TSV格式）
print("  读取红利低波...")
raw = pd.read_csv('C:/Users/wbl/Desktop/红利低波.xlsx', encoding='gbk', sep='\t')
# 时间列格式: "2013-12-19,四"
raw['date'] = pd.to_datetime(raw['时间'].str.split(',').str[0])
raw = raw[['date', '开盘', '收盘']].rename(columns={'开盘': f'open_{HLDB}', '收盘': f'close_{HLDB}'})
raw = raw.sort_values('date').reset_index(drop=True)
dfs[HLDB] = raw
print(f"  红利低波: {raw['date'].iloc[0].date()} ~ {raw['date'].iloc[-1].date()}, {len(raw)}条")

# ===== 2. 构建合并数据（全历史，动态join）=====
print("\n构建合并数据...")
# 以国债日历为基准
df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
df = df.sort_values('date').reset_index(drop=True)

# left join 各股票
for i in STOCK_ALL:
    cols = ['date', f'open_{i}', f'close_{i}', f'ma20_{i}', f'bf_{i}', f'ratio_{i}']
    df = pd.merge(df, dfs[i][cols], on='date', how='left')

# left join 红利低波
df = pd.merge(df, dfs[HLDB][['date', f'open_{HLDB}', f'close_{HLDB}']], on='date', how='left')

# 计算各标的ret（open-to-open）
all_ids_orig = STOCK_ALL + [BOND]          # 原版：国债
all_ids_hldb = STOCK_ALL + [HLDB]           # 变体：红利低波

for i in all_ids_orig + [HLDB]:
    df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
last_idx = df.index[-1]
for i in all_ids_orig + [HLDB]:
    df[f'ret_{i}'] = np.nan
    mask = df[f'open_{i}_next'].notna() & df[f'open_{i}'].notna()
    df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
    if pd.notna(df.loc[last_idx, f'open_{i}']) and pd.notna(df.loc[last_idx, f'close_{i}']):
        df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

# ===== 3. 策略信号（共用）=====
def get_signal(row):
    available = {}
    for i in STOCK_ALL:
        bf_val = row[f'bf_{i}']
        ratio_val = row[f'ratio_{i}']
        if pd.notna(bf_val) and pd.notna(ratio_val):
            available[i] = (bf_val, ratio_val)
    if not available:
        return BOND  # 信号是国债（原版）或红利低波（变体）的标记
    if all(v[1] < 1 for v in available.values()):
        return BOND
    return max(available, key=lambda k: available[k][0])

df['raw_signal'] = df.apply(get_signal, axis=1)
df['raw_position'] = df['raw_signal'].shift(1)
df.loc[df.index[0], 'raw_position'] = 0
df['raw_prev_position'] = df['raw_position'].shift(1)
df.loc[df.index[0], 'raw_prev_position'] = df.loc[df.index[0], 'raw_position']

# ===== 4. V8基线（原版：国债）=====
def get_raw_strat_ret(row, bond_id, ids_list):
    pos = int(row['raw_position'])
    if pos == 0:
        gross = 0.0
    elif pos == BOND:
        # 原版用国债收益，变体用红利低波收益
        ret_val = row[f'ret_{bond_id}']
        gross = ret_val if pd.notna(ret_val) else 0.0
    else:
        ret_val = row[f'ret_{pos}']
        gross = ret_val if pd.notna(ret_val) else 0.0
    prev = int(row['raw_prev_position'])
    cost = 0.0
    if prev != pos:
        if prev in ids_list: cost += FEE
        if pos in ids_list: cost += FEE
    return (1 + gross) * (1 - cost) - 1

# 原版V8（国债）
df['raw_strat_ret_bond'] = df.apply(lambda r: get_raw_strat_ret(r, BOND, all_ids_orig), axis=1)
df['raw_strat_nav_bond'] = (1 + df['raw_strat_ret_bond']).cumprod()
df['raw_cummax_bond'] = df['raw_strat_nav_bond'].cummax()
df['raw_dd_bond'] = df['raw_strat_nav_bond'] / df['raw_cummax_bond'] - 1

# 变体V8（红利低波）—— 仅在红利低波有数据时使用
df['raw_strat_ret_hldb'] = df.apply(lambda r: get_raw_strat_ret(r, HLDB, all_ids_hldb), axis=1)
df['raw_strat_nav_hldb'] = (1 + df['raw_strat_ret_hldb']).cumprod()
df['raw_cummax_hldb'] = df['raw_strat_nav_hldb'].cummax()
df['raw_dd_hldb'] = df['raw_strat_nav_hldb'] / df['raw_cummax_hldb'] - 1

# ===== 5. 应用5%/4%熔断 =====
def apply_circuit_breaker(raw_pos, raw_dd, n, bond_id):
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

n = len(df)

# 原版：熔断转国债
print("应用熔断（原版-国债）...")
final_pos_bond = apply_circuit_breaker(
    df['raw_position'].values, df['raw_dd_bond'].values, n, BOND
)

# 变体：熔断转红利低波
print("应用熔断（变体-红利低波）...")
final_pos_hldb = apply_circuit_breaker(
    df['raw_position'].values, df['raw_dd_hldb'].values, n, HLDB
)

# ===== 6. 计算V14收益 =====
def compute_v14_ret(df, final_pos, bond_id, ids_list, n):
    prev_pos = np.concatenate([[final_pos[0]], final_pos[:-1]])
    rets = np.zeros(n)
    for i in range(n):
        pos = int(final_pos[i])
        if pos == 0:
            gross = 0.0
        elif pos == bond_id:
            ret_val = df[f'ret_{bond_id}'].iloc[i]
            gross = ret_val if pd.notna(ret_val) else 0.0
        else:
            ret_val = df[f'ret_{pos}'].iloc[i]
            gross = ret_val if pd.notna(ret_val) else 0.0
        p = int(prev_pos[i])
        cost = 0.0
        if p != pos:
            if p in ids_list: cost += FEE
            if pos in ids_list: cost += FEE
        rets[i] = (1 + gross) * (1 - cost) - 1
    return rets

df['v14_ret_bond'] = compute_v14_ret(df, final_pos_bond, BOND, all_ids_orig, n)
df['v14_nav_bond'] = (1 + df['v14_ret_bond']).cumprod()

df['v14_ret_hldb'] = compute_v14_ret(df, final_pos_hldb, HLDB, all_ids_hldb, n)
df['v14_nav_hldb'] = (1 + df['v14_ret_hldb']).cumprod()

# ===== 7. 近10年逐年统计 =====
print("\n计算近10年逐年统计...")

# 近10年起点：2026-07-21往前10年 = 2016-07-21
end_date = df['date'].iloc[-1]
start_10y = end_date - pd.DateOffset(years=10)

mask_10y = df['date'] >= start_10y
df_10y = df[mask_10y].copy().reset_index(drop=True)

# 找到起始日的净值
nav_bond_start = df_10y['v14_nav_bond'].iloc[0]
nav_hldb_start = df_10y['v14_nav_hldb'].iloc[0]

# 按年统计
df_10y['year'] = df_10y['date'].dt.year

results = []
for year in sorted(df_10y['year'].unique()):
    yr = df_10y[df_10y['year'] == year]
    
    # 年初年末净值
    nav_b_start = yr['v14_nav_bond'].iloc[0]
    nav_b_end = yr['v14_nav_bond'].iloc[-1]
    nav_h_start = yr['v14_nav_hldb'].iloc[0]
    nav_h_end = yr['v14_nav_hldb'].iloc[-1]
    
    # 年收益
    ret_bond = nav_b_end / nav_b_start - 1
    ret_hldb = nav_h_end / nav_h_start - 1
    
    # 年内日收益率
    daily_b = yr['v14_ret_bond'].values
    daily_h = yr['v14_ret_hldb'].values
    
    # 夏普（年化，假设252交易日）
    sharpe_b = np.mean(daily_b) / np.std(daily_b) * np.sqrt(252) if np.std(daily_b) > 0 else 0
    sharpe_h = np.mean(daily_h) / np.std(daily_h) * np.sqrt(252) if np.std(daily_h) > 0 else 0
    
    # 最大回撤
    nav_b_cummax = yr['v14_nav_bond'].cummax()
    dd_b = (yr['v14_nav_bond'] / nav_b_cummax - 1).min()
    nav_h_cummax = yr['v14_nav_hldb'].cummax()
    dd_h = (yr['v14_nav_hldb'] / nav_h_cummax - 1).min()
    
    # 持仓占比
    hold_b = {}
    hold_h = {}
    for pos_val in np.unique(final_pos_bond[yr.index.values]):
        name = all_names[int(pos_val)]
        pct = np.mean(final_pos_bond[yr.index.values] == pos_val) * 100
        hold_b[name] = round(pct, 1)
    for pos_val in np.unique(final_pos_hldb[yr.index.values]):
        name = all_names[int(pos_val)]
        pct = np.mean(final_pos_hldb[yr.index.values] == pos_val) * 100
        hold_h[name] = round(pct, 1)
    
    results.append({
        'year': int(year),
        'ret_bond': ret_bond,
        'ret_hldb': ret_hldb,
        'diff': ret_hldb - ret_bond,
        'sharpe_bond': sharpe_b,
        'sharpe_hldb': sharpe_h,
        'mdd_bond': dd_b,
        'mdd_hldb': dd_h,
        'hold_bond': hold_b,
        'hold_hldb': hold_h,
        'days': len(yr),
    })

# 总体统计
total_ret_bond = df_10y['v14_nav_bond'].iloc[-1] / df_10y['v14_nav_bond'].iloc[0] - 1
total_ret_hldb = df_10y['v14_nav_hldb'].iloc[-1] / df_10y['v14_nav_hldb'].iloc[0] - 1
n_years = len(results)
ann_ret_bond = (1 + total_ret_bond) ** (1 / n_years) - 1
ann_ret_hldb = (1 + total_ret_hldb) ** (1 / n_years) - 1

# 全局夏普
daily_b_all = df_10y['v14_ret_bond'].values
daily_h_all = df_10y['v14_ret_hldb'].values
sharpe_b_all = np.mean(daily_b_all) / np.std(daily_b_all) * np.sqrt(252) if np.std(daily_b_all) > 0 else 0
sharpe_h_all = np.mean(daily_h_all) / np.std(daily_h_all) * np.sqrt(252) if np.std(daily_h_all) > 0 else 0

# 全局最大回撤
nav_b_cummax_all = df_10y['v14_nav_bond'].cummax()
dd_b_all = (df_10y['v14_nav_bond'] / nav_b_cummax_all - 1).min()
nav_h_cummax_all = df_10y['v14_nav_hldb'].cummax()
dd_h_all = (df_10y['v14_nav_hldb'] / nav_h_cummax_all - 1).min()

# ===== 8. 打印结果 =====
print(f"\n{'='*90}")
print(f"  近10年 ({start_10y.date()} ~ {end_date.date()}, {len(df_10y)}天)")
print(f"{'='*90}")
print(f"  {'年份':>6}  {'原版(国债)':>10}  {'变体(红利低波)':>12}  {'差值':>8}  {'夏普(国债)':>10}  {'夏普(红利)':>10}  {'回撤(国债)':>10}  {'回撤(红利)':>10}")
print(f"  {'-'*85}")
for r in results:
    print(f"  {r['year']:>6}  {r['ret_bond']*100:>+9.2f}%  {r['ret_hldb']*100:>+11.2f}%  {r['diff']*100:>+7.2f}%  {r['sharpe_bond']:>9.2f}  {r['sharpe_hldb']:>9.2f}  {r['mdd_bond']*100:>9.2f}%  {r['mdd_hldb']*100:>9.2f}%")

print(f"  {'-'*85}")
print(f"  {'总计':>6}  {total_ret_bond*100:>+9.2f}%  {total_ret_hldb*100:>+11.2f}%  {(total_ret_hldb-total_ret_bond)*100:>+7.2f}%")
print(f"  {'年化':>6}  {ann_ret_bond*100:>+9.2f}%  {ann_ret_hldb*100:>+11.2f}%  {(ann_ret_hldb-ann_ret_bond)*100:>+7.2f}%")
print(f"  {'夏普':>6}  {'':>10}  {'':>12}  {'':>8}  {sharpe_b_all:>9.2f}  {sharpe_h_all:>9.2f}")
print(f"  {'最大回撤':>6}  {'':>10}  {'':>12}  {'':>8}  {'':>10}  {'':>10}  {dd_b_all*100:>9.2f}%  {dd_h_all*100:>9.2f}%")

print(f"\n  持仓占比对比:")
print(f"  {'年份':>6}  {'原版(国债)':>40}  {'变体(红利低波)':>40}")
print(f"  {'-'*90}")
for r in results:
    hb = ', '.join(f"{k}({v}%)" for k,v in sorted(r['hold_bond'].items(), key=lambda x:-x[1])[:5])
    hh = ', '.join(f"{k}({v}%)" for k,v in sorted(r['hold_hldb'].items(), key=lambda x:-x[1])[:5])
    print(f"  {r['year']:>6}  {hb:>40}  {hh:>40}")

# ===== 9. 生成HTML =====
print("\n生成HTML报告...")

colors = {
    '上证50': '#e74c3c', '创业板50': '#f39c12', '纳斯达克100': '#3498db',
    '沪深300': '#2ecc71', '中证500': '#9b59b6', '中证1000': '#1abc9c',
    '标普500': '#e67e22', '科创50': '#d35400', '国债': '#95a5a6', '红利低波': '#8e44ad',
}

year_rows = []
for r in results:
    diff_cls = 'pos' if r['diff'] >= 0 else 'neg'
    ret_b_cls = 'pos' if r['ret_bond'] >= 0 else 'neg'
    ret_h_cls = 'pos' if r['ret_hldb'] >= 0 else 'neg'
    dd_b_cls = 'dd-danger' if r['mdd_bond'] < -DD_TRIGGER else ('dd-warn' if r['mdd_bond'] < -DD_RELEASE else 'dd-ok')
    dd_h_cls = 'dd-danger' if r['mdd_hldb'] < -DD_TRIGGER else ('dd-warn' if r['mdd_hldb'] < -DD_RELEASE else 'dd-ok')
    
    # 持仓占比chip
    hb_chips = ''.join(f'<span class="chip" style="background:{colors.get(k,'#888')}">{k} {v}%</span>' 
                       for k,v in sorted(r['hold_bond'].items(), key=lambda x:-x[1])[:4])
    hh_chips = ''.join(f'<span class="chip" style="background:{colors.get(k,'#888')}">{k} {v}%</span>' 
                       for k,v in sorted(r['hold_hldb'].items(), key=lambda x:-x[1])[:4])
    
    year_rows.append(f'''<tr>
        <td class="yr">{r['year']}</td>
        <td class="{ret_b_cls}">{r['ret_bond']*100:+.2f}%</td>
        <td class="{ret_h_cls}">{r['ret_hldb']*100:+.2f}%</td>
        <td class="{diff_cls}">{r['diff']*100:+.2f}%</td>
        <td>{r['sharpe_bond']:.2f}</td>
        <td>{r['sharpe_hldb']:.2f}</td>
        <td class="{dd_b_cls}">{r['mdd_bond']*100:.2f}%</td>
        <td class="{dd_h_cls}">{r['mdd_hldb']*100:.2f}%</td>
        <td class="chips">{hb_chips}</td>
        <td class="chips">{hh_chips}</td>
    </tr>''')

# 总计行
total_diff_cls = 'pos' if total_ret_hldb - total_ret_bond >= 0 else 'neg'
year_rows.append(f'''<tr class="total-row">
    <td class="yr">总计</td>
    <td class="{'pos' if total_ret_bond >= 0 else 'neg'}">{total_ret_bond*100:+.2f}%</td>
    <td class="{'pos' if total_ret_hldb >= 0 else 'neg'}">{total_ret_hldb*100:+.2f}%</td>
    <td class="{total_diff_cls}">{(total_ret_hldb-total_ret_bond)*100:+.2f}%</td>
    <td>{sharpe_b_all:.2f}</td>
    <td>{sharpe_h_all:.2f}</td>
    <td class="{'dd-danger' if dd_b_all < -DD_TRIGGER else 'dd-warn' if dd_b_all < -DD_RELEASE else 'dd-ok'}">{dd_b_all*100:.2f}%</td>
    <td class="{'dd-danger' if dd_h_all < -DD_TRIGGER else 'dd-warn' if dd_h_all < -DD_RELEASE else 'dd-ok'}">{dd_h_all*100:.2f}%</td>
    <td colspan="2"></td>
</tr>''')
year_rows.append(f'''<tr class="total-row">
    <td class="yr">年化</td>
    <td class="{'pos' if ann_ret_bond >= 0 else 'neg'}">{ann_ret_bond*100:+.2f}%</td>
    <td class="{'pos' if ann_ret_hldb >= 0 else 'neg'}">{ann_ret_hldb*100:+.2f}%</td>
    <td class="{total_diff_cls}">{(ann_ret_hldb-ann_ret_bond)*100:+.2f}%</td>
    <td colspan="6"></td>
</tr>''')

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14策略对比 — 国债 vs 红利低波（近10年）</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Microsoft YaHei','Segoe UI',sans-serif; background:#f5f6fa; color:#333; padding:16px; max-width:1300px; margin:0 auto; }}
h1 {{ font-size:22px; margin-bottom:4px; }}
.sub {{ font-size:12px; color:#888; margin-bottom:16px; }}
.summary {{ display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap; }}
.s-card {{ background:#fff; border-radius:8px; padding:10px 16px; box-shadow:0 1px 4px rgba(0,0,0,0.06); }}
.s-card .label {{ font-size:11px; color:#999; }}
.s-card .val {{ font-size:18px; font-weight:700; }}
.s-card .sub-val {{ font-size:12px; color:#666; }}
.card {{ background:#fff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.08); overflow:hidden; overflow-x:auto; margin-bottom:16px; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; min-width:1000px; }}
th {{ background:#f8f9fa; padding:10px 8px; text-align:center; font-weight:600; border-bottom:2px solid #e0e0e0; white-space:nowrap; }}
td {{ padding:8px; text-align:center; border-bottom:1px solid #eee; }}
tr:hover td {{ background:#f8f9ff; }}
.total-row td {{ font-weight:700; background:#f0f4ff; border-top:2px solid #d0d8f0; }}
.yr {{ font-weight:600; }}
.pos {{ color:#e74c3c; font-weight:600; }}
.neg {{ color:#27ae60; font-weight:600; }}
.dd-ok {{ color:#27ae60; }}
.dd-warn {{ color:#f39c12; }}
.dd-danger {{ color:#e74c3c; font-weight:600; }}
.chips {{ text-align:left; }}
.chip {{ display:inline-block; padding:1px 5px; border-radius:3px; color:#fff; font-size:10px; margin:1px; white-space:nowrap; }}
.rules {{ padding:12px 16px; background:#fff; border-radius:8px; font-size:11px; color:#888; line-height:1.6; }}
</style>
</head>
<body>
<h1>V14策略对比 — 国债 vs 红利低波（近10年）</h1>
<div class="sub">决策日期=T日 · 决策bf=(T-1收盘/T-1的MA20)-1 · T日开盘执行 · 5%熔断/4%解除 · 手续费0.02% · {start_10y.date()} ~ {end_date.date()} · {len(df_10y)}天</div>

<div class="summary">
    <div class="s-card"><div class="label">原版总收益（国债）</div><div class="val {'pos' if total_ret_bond>=0 else 'neg'}">{total_ret_bond*100:+.2f}%</div><div class="sub-val">年化 {ann_ret_bond*100:+.2f}%</div></div>
    <div class="s-card"><div class="label">变体总收益（红利低波）</div><div class="val {'pos' if total_ret_hldb>=0 else 'neg'}">{total_ret_hldb*100:+.2f}%</div><div class="sub-val">年化 {ann_ret_hldb*100:+.2f}%</div></div>
    <div class="s-card"><div class="label">收益差值</div><div class="val {total_diff_cls}">{(total_ret_hldb-total_ret_bond)*100:+.2f}%</div><div class="sub-val">年化差 {(ann_ret_hldb-ann_ret_bond)*100:+.2f}%</div></div>
    <div class="s-card"><div class="label">夏普（国债）</div><div class="val">{sharpe_b_all:.2f}</div></div>
    <div class="s-card"><div class="label">夏普（红利低波）</div><div class="val">{sharpe_h_all:.2f}</div></div>
    <div class="s-card"><div class="label">最大回撤（国债）</div><div class="val dd-danger">{dd_b_all*100:.2f}%</div></div>
    <div class="s-card"><div class="label">最大回撤（红利低波）</div><div class="val dd-danger">{dd_h_all*100:.2f}%</div></div>
</div>

<div class="card">
<table>
<thead><tr>
    <th>年份</th>
    <th>原版收益<br>(国债)</th>
    <th>变体收益<br>(红利低波)</th>
    <th>差值</th>
    <th>夏普<br>(国债)</th>
    <th>夏普<br>(红利低波)</th>
    <th>最大回撤<br>(国债)</th>
    <th>最大回撤<br>(红利低波)</th>
    <th>持仓占比(原版)</th>
    <th>持仓占比(变体)</th>
</tr></thead>
<tbody>
{''.join(year_rows)}
</tbody>
</table>
</div>

<div class="rules">
    <b>说明：</b>将V14策略中买入国债的时段（全bf&lt;0信号 + 熔断期）替换为买入红利低波指数，对比近10年逐年收益。<br>
    <b>原版：</b>避险时段持有国债（上证国债指数 sh000012）<br>
    <b>变体：</b>避险时段持有红利低波指数（同花顺数据，2013-12-19起）<br>
    <b>注意：</b>红利低波数据始于2013-12-19，2016年之前无数据的日期仍用国债收益填充。熔断触发线5%，解除线4%。<br>
    <b>差值</b> = 变体收益 - 原版收益，正值表示红利低波优于国债。
</div>
</body></html>'''

html_path = os.path.join(BASE_DIR, 'v14_hldb_compare.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"HTML报告已生成: {html_path}")

# 保存JSON
json_data = {
    'start': start_10y.strftime('%Y-%m-%d'),
    'end': end_date.strftime('%Y-%m-%d'),
    'n_days': len(df_10y),
    'total_ret_bond': total_ret_bond,
    'total_ret_hldb': total_ret_hldb,
    'ann_ret_bond': ann_ret_bond,
    'ann_ret_hldb': ann_ret_hldb,
    'sharpe_bond': sharpe_b_all,
    'sharpe_hldb': sharpe_h_all,
    'mdd_bond': dd_b_all,
    'mdd_hldb': dd_h_all,
    'yearly': results,
}
json_path = os.path.join(BASE_DIR, 'v14_hldb_compare.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
print(f"JSON数据已保存: {json_path}")
