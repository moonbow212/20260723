# -*- coding: utf-8 -*-
"""V14策略变体：国债替换为标普500
当策略信号为国债（全bf<0）或熔断时，持有标普500而非国债
对比原V14（持国债）的近20年逐年收益

注意：标普500数据始于2010-09-09，之前无数据时仍用国债收益填充
"""
import pandas as pd
import numpy as np
import json, os

FEE = 0.0002
DD_TRIGGER = 0.05
DD_RELEASE = 0.04

STOCK_ALL = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9
SP500 = 7  # 标普500（同时是股票候选和避险替代品）
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
        d[f'ma20_{i}'] = d[f'close_{i}'].rolling(20).mean()
        d[f'bf_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}'] - 1
        d[f'ratio_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}']
    dfs[i] = d
    print(f"  {names[i]}: {d['date'].iloc[0].date()} ~ {d['date'].iloc[-1].date()}, {len(d)}条")

# ===== 2. 构建合并数据（全历史，动态join）=====
print("\n构建合并数据...")
df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
df = df.sort_values('date').reset_index(drop=True)

for i in STOCK_ALL:
    cols = ['date', f'open_{i}', f'close_{i}', f'ma20_{i}', f'bf_{i}', f'ratio_{i}']
    df = pd.merge(df, dfs[i][cols], on='date', how='left')

# 计算各标的ret（open-to-open）
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

# ===== 3. 策略信号（共用）=====
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

# ===== 4. V8基线 =====
def get_raw_strat_ret(row, safe_haven_id, ids_list):
    """计算V8基线收益
    safe_haven_id: 避险资产id（原版=BOND=9, 变体=SP500=7）
    当position为BOND(9)时，使用safe_haven_id的收益
    """
    pos = int(row['raw_position'])
    if pos == 0:
        gross = 0.0
    elif pos == BOND:
        # 避险时段：原版用国债，变体用标普500
        ret_val = row[f'ret_{safe_haven_id}']
        gross = ret_val if pd.notna(ret_val) else 0.0
    else:
        ret_val = row[f'ret_{pos}']
        gross = ret_val if pd.notna(ret_val) else 0.0
    prev = int(row['raw_prev_position'])
    cost = 0.0
    if prev != pos:
        # 换仓成本：根据实际持有的资产计算
        if prev == BOND:
            if safe_haven_id in ids_list: cost += FEE
        elif prev in ids_list: cost += FEE
        if pos == BOND:
            if safe_haven_id in ids_list: cost += FEE
        elif pos in ids_list: cost += FEE
    return (1 + gross) * (1 - cost) - 1

# 原版V8（国债避险）
print("计算V8基线（原版-国债）...")
df['raw_strat_ret_bond'] = df.apply(lambda r: get_raw_strat_ret(r, BOND, all_ids), axis=1)
df['raw_strat_nav_bond'] = (1 + df['raw_strat_ret_bond']).cumprod()
df['raw_cummax_bond'] = df['raw_strat_nav_bond'].cummax()
df['raw_dd_bond'] = df['raw_strat_nav_bond'] / df['raw_cummax_bond'] - 1

# 变体V8（标普500避险）
print("计算V8基线（变体-标普500）...")
df['raw_strat_ret_sp500'] = df.apply(lambda r: get_raw_strat_ret(r, SP500, all_ids), axis=1)
df['raw_strat_nav_sp500'] = (1 + df['raw_strat_ret_sp500']).cumprod()
df['raw_cummax_sp500'] = df['raw_strat_nav_sp500'].cummax()
df['raw_dd_sp500'] = df['raw_strat_nav_sp500'] / df['raw_cummax_sp500'] - 1

# ===== 5. 应用5%/4%熔断 =====
def apply_circuit_breaker(raw_pos, raw_dd, n, safe_haven_id):
    """应用熔断
    safe_haven_id: 熔断时转向的资产（原版=BOND=9, 变体=SP500=7）
    """
    in_cb = False
    final_position = []
    for i in range(n):
        sig = int(raw_pos[i])
        dd = raw_dd[i]
        if not in_cb:
            if dd < -DD_TRIGGER and sig != BOND:
                in_cb = True
                final_position.append(safe_haven_id)
            else:
                # 正常信号：如果是BOND，用safe_haven_id替代
                final_position.append(safe_haven_id if sig == BOND else sig)
        else:
            if dd > -DD_RELEASE:
                in_cb = False
                final_position.append(safe_haven_id if sig == BOND else sig)
            else:
                final_position.append(safe_haven_id)
    return np.array(final_position)

n = len(df)

# 原版：熔断转国债
print("应用熔断（原版-国债）...")
final_pos_bond = apply_circuit_breaker(
    df['raw_position'].values, df['raw_dd_bond'].values, n, BOND
)

# 变体：熔断转标普500
print("应用熔断（变体-标普500）...")
final_pos_sp500 = apply_circuit_breaker(
    df['raw_position'].values, df['raw_dd_sp500'].values, n, SP500
)

# ===== 6. 计算V14收益 =====
def compute_v14_ret(df, final_pos, safe_haven_id, ids_list, n):
    prev_pos = np.concatenate([[final_pos[0]], final_pos[:-1]])
    rets = np.zeros(n)
    for i in range(n):
        pos = int(final_pos[i])
        if pos == 0:
            gross = 0.0
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

df['v14_ret_bond'] = compute_v14_ret(df, final_pos_bond, BOND, all_ids, n)
df['v14_nav_bond'] = (1 + df['v14_ret_bond']).cumprod()

df['v14_ret_sp500'] = compute_v14_ret(df, final_pos_sp500, SP500, all_ids, n)
df['v14_nav_sp500'] = (1 + df['v14_ret_sp500']).cumprod()

# ===== 7. 近20年逐年统计 =====
print("\n计算近20年逐年统计...")

end_date = df['date'].iloc[-1]
start_20y = end_date - pd.DateOffset(years=20)

mask_20y = df['date'] >= start_20y
df_20y = df[mask_20y].copy().reset_index(drop=True)

# 找到起始日在原df中的索引
start_idx_orig = df.index[mask_20y][0]
final_pos_bond_20y = final_pos_bond[start_idx_orig:]
final_pos_sp500_20y = final_pos_sp500[start_idx_orig:]

df_20y['year'] = df_20y['date'].dt.year

results = []
for year in sorted(df_20y['year'].unique()):
    yr_mask = df_20y['year'] == year
    yr = df_20y[yr_mask]
    yr_idx = yr.index.values
    
    # 年初年末净值
    nav_b_start = yr['v14_nav_bond'].iloc[0]
    nav_b_end = yr['v14_nav_bond'].iloc[-1]
    nav_s_start = yr['v14_nav_sp500'].iloc[0]
    nav_s_end = yr['v14_nav_sp500'].iloc[-1]
    
    ret_bond = nav_b_end / nav_b_start - 1
    ret_sp500 = nav_s_end / nav_s_start - 1
    
    daily_b = yr['v14_ret_bond'].values
    daily_s = yr['v14_ret_sp500'].values
    
    sharpe_b = np.mean(daily_b) / np.std(daily_b) * np.sqrt(252) if np.std(daily_b) > 0 else 0
    sharpe_s = np.mean(daily_s) / np.std(daily_s) * np.sqrt(252) if np.std(daily_s) > 0 else 0
    
    nav_b_cummax = yr['v14_nav_bond'].cummax()
    dd_b = (yr['v14_nav_bond'] / nav_b_cummax - 1).min()
    nav_s_cummax = yr['v14_nav_sp500'].cummax()
    dd_s = (yr['v14_nav_sp500'] / nav_s_cummax - 1).min()
    
    # 持仓占比
    hold_b = {}
    hold_s = {}
    for pos_val in np.unique(final_pos_bond_20y[yr_idx]):
        name = all_names[int(pos_val)]
        pct = np.mean(final_pos_bond_20y[yr_idx] == pos_val) * 100
        hold_b[name] = round(pct, 1)
    for pos_val in np.unique(final_pos_sp500_20y[yr_idx]):
        name = all_names[int(pos_val)]
        pct = np.mean(final_pos_sp500_20y[yr_idx] == pos_val) * 100
        hold_s[name] = round(pct, 1)
    
    # 国债/避险占比
    bond_pct_b = hold_b.get('国债', 0)
    sp500_pct_s = hold_s.get('标普500', 0)
    
    results.append({
        'year': int(year),
        'ret_bond': ret_bond,
        'ret_sp500': ret_sp500,
        'diff': ret_sp500 - ret_bond,
        'sharpe_bond': sharpe_b,
        'sharpe_sp500': sharpe_s,
        'mdd_bond': dd_b,
        'mdd_sp500': dd_s,
        'hold_bond': hold_b,
        'hold_sp500': hold_s,
        'bond_pct': bond_pct_b,
        'sp500_pct': sp500_pct_s,
        'days': len(yr),
    })

# 总体统计
total_ret_bond = df_20y['v14_nav_bond'].iloc[-1] / df_20y['v14_nav_bond'].iloc[0] - 1
total_ret_sp500 = df_20y['v14_nav_sp500'].iloc[-1] / df_20y['v14_nav_sp500'].iloc[0] - 1
n_years = len(results)
ann_ret_bond = (1 + total_ret_bond) ** (1 / n_years) - 1
ann_ret_sp500 = (1 + total_ret_sp500) ** (1 / n_years) - 1

daily_b_all = df_20y['v14_ret_bond'].values
daily_s_all = df_20y['v14_ret_sp500'].values
sharpe_b_all = np.mean(daily_b_all) / np.std(daily_b_all) * np.sqrt(252) if np.std(daily_b_all) > 0 else 0
sharpe_s_all = np.mean(daily_s_all) / np.std(daily_s_all) * np.sqrt(252) if np.std(daily_s_all) > 0 else 0

nav_b_cummax_all = df_20y['v14_nav_bond'].cummax()
dd_b_all = (df_20y['v14_nav_bond'] / nav_b_cummax_all - 1).min()
nav_s_cummax_all = df_20y['v14_nav_sp500'].cummax()
dd_s_all = (df_20y['v14_nav_sp500'] / nav_s_cummax_all - 1).min()

# 年化波动率
ann_vol_b = np.std(daily_b_all) * np.sqrt(252)
ann_vol_s = np.std(daily_s_all) * np.sqrt(252)

# ===== 8. 打印结果 =====
print(f"\n{'='*100}")
print(f"  近20年 ({start_20y.date()} ~ {end_date.date()}, {len(df_20y)}天)")
print(f"{'='*100}")
print(f"  {'年份':>6}  {'原版(国债)':>12}  {'变体(标普500)':>14}  {'差值':>10}  {'夏普(国债)':>10}  {'夏普(标普)':>10}  {'回撤(国债)':>10}  {'回撤(标普)':>10}  {'国债占比':>8}  {'标普占比':>8}")
print(f"  {'-'*95}")
for r in results:
    print(f"  {r['year']:>6}  {r['ret_bond']*100:>+11.2f}%  {r['ret_sp500']*100:>+13.2f}%  {r['diff']*100:>+9.2f}%  {r['sharpe_bond']:>9.2f}  {r['sharpe_sp500']:>9.2f}  {r['mdd_bond']*100:>9.2f}%  {r['mdd_sp500']*100:>9.2f}%  {r['bond_pct']:>7.1f}%  {r['sp500_pct']:>7.1f}%")

print(f"  {'-'*95}")
print(f"  {'总计':>6}  {total_ret_bond*100:>+11.2f}%  {total_ret_sp500*100:>+13.2f}%  {(total_ret_sp500-total_ret_bond)*100:>+9.2f}%")
print(f"  {'年化':>6}  {ann_ret_bond*100:>+11.2f}%  {ann_ret_sp500*100:>+13.2f}%  {(ann_ret_sp500-ann_ret_bond)*100:>+9.2f}%")
print(f"  {'夏普':>6}  {'':>12}  {'':>14}  {'':>10}  {sharpe_b_all:>9.2f}  {sharpe_s_all:>9.2f}")
print(f"  {'波动':>6}  {'':>12}  {'':>14}  {'':>10}  {ann_vol_b*100:>9.2f}%  {ann_vol_s*100:>9.2f}%")
print(f"  {'最大回撤':>6}  {'':>12}  {'':>14}  {'':>10}  {'':>10}  {'':>10}  {dd_b_all*100:>9.2f}%  {dd_s_all*100:>9.2f}%")

# ===== 9. 生成HTML =====
print("\n生成HTML报告...")

colors = {
    '上证50': '#e74c3c', '创业板50': '#f39c12', '纳斯达克100': '#3498db',
    '沪深300': '#2ecc71', '中证500': '#9b59b6', '中证1000': '#1abc9c',
    '标普500': '#e67e22', '科创50': '#d35400', '国债': '#95a5a6',
}

year_rows = []
for r in results:
    diff_cls = 'pos' if r['diff'] >= 0 else 'neg'
    ret_b_cls = 'pos' if r['ret_bond'] >= 0 else 'neg'
    ret_s_cls = 'pos' if r['ret_sp500'] >= 0 else 'neg'
    dd_b_cls = 'dd-danger' if r['mdd_bond'] < -DD_TRIGGER else ('dd-warn' if r['mdd_bond'] < -DD_RELEASE else 'dd-ok')
    dd_s_cls = 'dd-danger' if r['mdd_sp500'] < -DD_TRIGGER else ('dd-warn' if r['mdd_sp500'] < -DD_RELEASE else 'dd-ok')
    
    hb_chips = ''.join(f'<span class="chip" style="background:{colors.get(k,'#888')}">{k} {v}%</span>' 
                       for k,v in sorted(r['hold_bond'].items(), key=lambda x:-x[1])[:4])
    hs_chips = ''.join(f'<span class="chip" style="background:{colors.get(k,'#888')}">{k} {v}%</span>' 
                       for k,v in sorted(r['hold_sp500'].items(), key=lambda x:-x[1])[:4])
    
    year_rows.append(f'''<tr>
        <td class="yr">{r['year']}</td>
        <td class="{ret_b_cls}">{r['ret_bond']*100:+.2f}%</td>
        <td class="{ret_s_cls}">{r['ret_sp500']*100:+.2f}%</td>
        <td class="{diff_cls}">{r['diff']*100:+.2f}%</td>
        <td>{r['sharpe_bond']:.2f}</td>
        <td>{r['sharpe_sp500']:.2f}</td>
        <td class="{dd_b_cls}">{r['mdd_bond']*100:.2f}%</td>
        <td class="{dd_s_cls}">{r['mdd_sp500']*100:.2f}%</td>
        <td class="chips">{hb_chips}</td>
        <td class="chips">{hs_chips}</td>
    </tr>''')

# 总计行
total_diff_cls = 'pos' if total_ret_sp500 - total_ret_bond >= 0 else 'neg'
year_rows.append(f'''<tr class="total-row">
    <td class="yr">总计</td>
    <td class="{'pos' if total_ret_bond >= 0 else 'neg'}">{total_ret_bond*100:+.2f}%</td>
    <td class="{'pos' if total_ret_sp500 >= 0 else 'neg'}">{total_ret_sp500*100:+.2f}%</td>
    <td class="{total_diff_cls}">{(total_ret_sp500-total_ret_bond)*100:+.2f}%</td>
    <td>{sharpe_b_all:.2f}</td>
    <td>{sharpe_s_all:.2f}</td>
    <td class="{'dd-danger' if dd_b_all < -DD_TRIGGER else 'dd-warn' if dd_b_all < -DD_RELEASE else 'dd-ok'}">{dd_b_all*100:.2f}%</td>
    <td class="{'dd-danger' if dd_s_all < -DD_TRIGGER else 'dd-warn' if dd_s_all < -DD_RELEASE else 'dd-ok'}">{dd_s_all*100:.2f}%</td>
    <td colspan="2"></td>
</tr>''')
year_rows.append(f'''<tr class="total-row">
    <td class="yr">年化</td>
    <td class="{'pos' if ann_ret_bond >= 0 else 'neg'}">{ann_ret_bond*100:+.2f}%</td>
    <td class="{'pos' if ann_ret_sp500 >= 0 else 'neg'}">{ann_ret_sp500*100:+.2f}%</td>
    <td class="{total_diff_cls}">{(ann_ret_sp500-ann_ret_bond)*100:+.2f}%</td>
    <td colspan="6"></td>
</tr>''')

# 净值曲线对比图（简易SVG）
# 取每年末净值
yearly_nav_b = []
yearly_nav_s = []
year_labels = []
for r in results:
    yr = df_20y[df_20y['year'] == r['year']]
    yearly_nav_b.append(yr['v14_nav_bond'].iloc[-1])
    yearly_nav_s.append(yr['v14_nav_sp500'].iloc[-1])
    year_labels.append(str(r['year']))

# SVG净值曲线
max_nav = max(max(yearly_nav_b), max(yearly_nav_s))
chart_w = 700
chart_h = 250
pad_l = 50
pad_b = 30
pad_t = 20
plot_w = chart_w - pad_l - 20
plot_h = chart_h - pad_b - pad_t

def nav_to_y(nav):
    return pad_t + plot_h - (nav / max_nav) * plot_h

def idx_to_x(idx):
    return pad_l + (idx / (len(year_labels) - 1)) * plot_w

pts_b = ' '.join(f'{idx_to_x(i):.1f},{nav_to_y(yearly_nav_b[i]):.1f}' for i in range(len(yearly_nav_b)))
pts_s = ' '.join(f'{idx_to_x(i):.1f},{nav_to_y(yearly_nav_s[i]):.1f}' for i in range(len(yearly_nav_s)))

x_labels = ''
for i, label in enumerate(year_labels):
    if i % 2 == 0 or i == len(year_labels) - 1:
        x_labels += f'<text x="{idx_to_x(i):.0f}" y="{chart_h - 8}" font-size="9" fill="#888" text-anchor="middle">{label}</text>'

y_max_val = max_nav
y_ticks = ''
for tick in [0, 0.25, 0.5, 0.75, 1.0]:
    val = tick * y_max_val
    y_pos = nav_to_y(val)
    y_ticks += f'<line x1="{pad_l-4}" y1="{y_pos:.0f}" x2="{chart_w-20}" y2="{y_pos:.0f}" stroke="#eee" stroke-width="1"/>'
    label_str = f'{val:.0f}x' if val >= 1 else f'{val:.1f}'
    y_ticks += f'<text x="{pad_l-8}" y="{y_pos+3:.0f}" font-size="9" fill="#888" text-anchor="end">{label_str}</text>'

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14策略对比 — 国债 vs 标普500（近20年）</title>
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
.chart-card {{ background:#fff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.08); padding:16px; margin-bottom:16px; }}
.legend {{ display:flex; gap:16px; margin-top:8px; font-size:12px; }}
.legend-item {{ display:flex; align-items:center; gap:4px; }}
.legend-line {{ width:20px; height:3px; border-radius:2px; }}
</style>
</head>
<body>
<h1>V14策略对比 — 国债 vs 标普500（近20年）</h1>
<div class="sub">决策日期=T日 · 决策bf=(T-1收盘/T-1的MA20)-1 · T日开盘执行 · 5%熔断/4%解除 · 手续费0.02% · {start_20y.date()} ~ {end_date.date()} · {len(df_20y)}天</div>

<div class="summary">
    <div class="s-card"><div class="label">原版总收益（国债避险）</div><div class="val {'pos' if total_ret_bond>=0 else 'neg'}">{total_ret_bond*100:+.2f}%</div><div class="sub-val">年化 {ann_ret_bond*100:+.2f}%</div></div>
    <div class="s-card"><div class="label">变体总收益（标普500避险）</div><div class="val {'pos' if total_ret_sp500>=0 else 'neg'}">{total_ret_sp500*100:+.2f}%</div><div class="sub-val">年化 {ann_ret_sp500*100:+.2f}%</div></div>
    <div class="s-card"><div class="label">收益差值</div><div class="val {total_diff_cls}">{(total_ret_sp500-total_ret_bond)*100:+.2f}%</div><div class="sub-val">年化差 {(ann_ret_sp500-ann_ret_bond)*100:+.2f}%</div></div>
    <div class="s-card"><div class="label">夏普（国债）</div><div class="val">{sharpe_b_all:.2f}</div><div class="sub-val">波动 {ann_vol_b*100:.2f}%</div></div>
    <div class="s-card"><div class="label">夏普（标普500）</div><div class="val">{sharpe_s_all:.2f}</div><div class="sub-val">波动 {ann_vol_s*100:.2f}%</div></div>
    <div class="s-card"><div class="label">最大回撤（国债）</div><div class="val {'dd-danger' if dd_b_all < -DD_TRIGGER else 'dd-warn'}">{dd_b_all*100:.2f}%</div></div>
    <div class="s-card"><div class="label">最大回撤（标普500）</div><div class="val {'dd-danger' if dd_s_all < -DD_TRIGGER else 'dd-warn'}">{dd_s_all*100:.2f}%</div></div>
</div>

<div class="chart-card">
    <h3 style="font-size:14px;margin-bottom:8px;">年末净值曲线对比</h3>
    <svg width="{chart_w}" height="{chart_h}" viewBox="0 0 {chart_w} {chart_h}">
        {y_ticks}
        <polyline points="{pts_b}" fill="none" stroke="#95a5a6" stroke-width="2.5"/>
        <polyline points="{pts_s}" fill="none" stroke="#e67e22" stroke-width="2.5"/>
        {x_labels}
    </svg>
    <div class="legend">
        <div class="legend-item"><div class="legend-line" style="background:#95a5a6;"></div>原版（国债避险）</div>
        <div class="legend-item"><div class="legend-line" style="background:#e67e22;"></div>变体（标普500避险）</div>
    </div>
</div>

<div class="card">
<table>
<thead><tr>
    <th>年份</th>
    <th>原版收益<br>(国债)</th>
    <th>变体收益<br>(标普500)</th>
    <th>差值</th>
    <th>夏普<br>(国债)</th>
    <th>夏普<br>(标普500)</th>
    <th>最大回撤<br>(国债)</th>
    <th>最大回撤<br>(标普500)</th>
    <th>持仓占比(原版)</th>
    <th>持仓占比(变体)</th>
</tr></thead>
<tbody>
{''.join(year_rows)}
</tbody>
</table>
</div>

<div class="rules">
    <b>说明：</b>将V14策略中买入国债的时段（全bf&lt;0信号 + 熔断期）替换为买入标普500，对比近20年逐年收益。<br>
    <b>原版：</b>避险时段持有国债（上证国债指数 sh000012）<br>
    <b>变体：</b>避险时段持有标普500（data/7_标普500.csv）<br>
    <b>注意：</b>标普500数据始于2010-09-09，2010年之前无数据时该时段收益为0%（未持仓）。熔断触发线5%，解除线4%。<br>
    <b>差值</b> = 变体收益 - 原版收益，正值表示标普500优于国债。
</div>
</body></html>'''

html_path = os.path.join(BASE_DIR, 'v14_sp500_compare.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"HTML报告已生成: {html_path}")

# 保存JSON
json_data = {
    'start': start_20y.strftime('%Y-%m-%d'),
    'end': end_date.strftime('%Y-%m-%d'),
    'n_days': len(df_20y),
    'total_ret_bond': total_ret_bond,
    'total_ret_sp500': total_ret_sp500,
    'ann_ret_bond': ann_ret_bond,
    'ann_ret_sp500': ann_ret_sp500,
    'sharpe_bond': sharpe_b_all,
    'sharpe_sp500': sharpe_s_all,
    'mdd_bond': dd_b_all,
    'mdd_sp500': dd_s_all,
    'yearly': results,
}
json_path = os.path.join(BASE_DIR, 'v14_sp500_compare.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
print(f"JSON数据已保存: {json_path}")
