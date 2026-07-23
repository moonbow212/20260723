# -*- coding: utf-8 -*-
"""V14策略三方案近20年对比
方案A: V14原版 — 熔断(5%/4%)转国债，全bf<0持国债
方案B: V14国债换标普500 — 熔断(5%/4%)转标普500，全bf<0持标普500
方案C: V14不熔断+标普500 — 无熔断，全bf<0持标普500

标普500数据源：Desktop/美国标准普尔500指数历史数据.csv（2006-07~2026-05）
            + data/7_标普500.csv比率调整补充（2026-05-19~2026-07-20）
"""
import pandas as pd
import numpy as np
import json, os

FEE = 0.0002
DD_TRIGGER = 0.05
DD_RELEASE = 0.04

STOCK_ALL = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9
SP500 = 7
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}
all_names = {0:'空仓', 1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== 1. 读取数据 =====
print("读取数据...")
dfs = {}

# 标普500：先读新CSV
print("  读取标普500（新CSV）...")
new_sp = pd.read_csv('C:/Users/wbl/Desktop/美国标准普尔500指数历史数据.csv', encoding='utf-8')
new_sp['date'] = pd.to_datetime(new_sp['日期'])
new_sp['open'] = new_sp['开盘'].str.replace(',', '').astype(float)
new_sp['close'] = new_sp['收盘'].str.replace(',', '').astype(float)
new_sp = new_sp[['date', 'open', 'close']].sort_values('date').reset_index(drop=True)
print(f"    新CSV: {new_sp['date'].iloc[0].date()} ~ {new_sp['date'].iloc[-1].date()}, {len(new_sp)}条")

# 补充旧数据（2026-05-19之后），用比率调整
old_sp = pd.read_csv(os.path.join(BASE_DIR, 'data', '7_标普500.csv'), parse_dates=['date'])
old_sp = old_sp[['date', 'open', 'close']].sort_values('date').reset_index(drop=True)

# 计算最近比率
merged_check = pd.merge(
    new_sp[['date', 'close']].rename(columns={'close': 'new_c'}),
    old_sp[['date', 'close']].rename(columns={'close': 'old_c'}),
    on='date', how='inner'
)
ratio_factor = (merged_check['new_c'] / merged_check['old_c']).iloc[-20:].mean()  # 最后20天平均比率
print(f"    比率调整因子: {ratio_factor:.4f}")

# 旧数据中日期不在新CSV中的，用比率调整
old_only = old_sp[~old_sp['date'].isin(new_sp['date'])].copy()
old_only['open'] *= ratio_factor
old_only['close'] *= ratio_factor
print(f"    补充旧数据: {len(old_only)}条, {old_only['date'].iloc[0].date()} ~ {old_only['date'].iloc[-1].date()}")

# 合并标普500数据
sp500_full = pd.concat([new_sp, old_only], ignore_index=True)
sp500_full = sp500_full.drop_duplicates(subset='date').sort_values('date').reset_index(drop=True)
print(f"    标普500合并: {sp500_full['date'].iloc[0].date()} ~ {sp500_full['date'].iloc[-1].date()}, {len(sp500_full)}条")

# 存入dfs
dfs[7] = sp500_full.rename(columns={'open': 'open_7', 'close': 'close_7'})

# 读取其他标的
for i in STOCK_ALL + [BOND]:
    if i == 7:
        continue  # 标普500已读取
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

# 标普500也要算ma20/bf/ratio
dfs[7][f'ma20_7'] = dfs[7][f'close_7'].rolling(20).mean()
dfs[7][f'bf_7'] = dfs[7][f'close_7'] / dfs[7][f'ma20_7'] - 1
dfs[7][f'ratio_7'] = dfs[7][f'close_7'] / dfs[7][f'ma20_7']
print(f"  标普500(含MA20): {dfs[7]['date'].iloc[0].date()} ~ {dfs[7]['date'].iloc[-1].date()}, {len(dfs[7])}条")

# ===== 2. 构建合并数据 =====
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

# ===== 3. 策略信号 =====
def get_signal(row):
    available = {}
    for i in STOCK_ALL:
        bf_val = row[f'bf_{i}']
        ratio_val = row[f'ratio_{i}']
        if pd.notna(bf_val) and pd.notna(ratio_val):
            available[i] = (bf_val, ratio_val)
    if not available:
        return BOND  # 无数据→标记为国债信号
    if all(v[1] < 1 for v in available.values()):
        return BOND  # 全部跌破MA20→标记为国债信号
    return max(available, key=lambda k: available[k][0])

df['raw_signal'] = df.apply(get_signal, axis=1)
df['raw_position'] = df['raw_signal'].shift(1)
df.loc[df.index[0], 'raw_position'] = 0
df['raw_prev_position'] = df['raw_position'].shift(1)
df.loc[df.index[0], 'raw_prev_position'] = df.loc[df.index[0], 'raw_position']

# ===== 4. 计算三种策略 =====
n = len(df)

# --- 方案A: V14原版（国债+熔断）---
print("\n计算方案A: V14原版（国债+熔断）...")

def compute_v8_ret(row, safe_haven_id):
    """计算V8基线日收益，safe_haven_id为避险资产id"""
    pos = int(row['raw_position'])
    if pos == 0:
        gross = 0.0
    elif pos == BOND:
        ret_val = row[f'ret_{safe_haven_id}']
        gross = ret_val if pd.notna(ret_val) else 0.0
    else:
        ret_val = row[f'ret_{pos}']
        gross = ret_val if pd.notna(ret_val) else 0.0
    prev = int(row['raw_prev_position'])
    cost = 0.0
    if prev != pos:
        # 换仓成本
        prev_actual = safe_haven_id if prev == BOND else prev
        pos_actual = safe_haven_id if pos == BOND else pos
        if prev_actual in all_ids: cost += FEE
        if pos_actual in all_ids: cost += FEE
    return (1 + gross) * (1 - cost) - 1

# 方案A的V8（国债避险）
df['v8_ret_a'] = df.apply(lambda r: compute_v8_ret(r, BOND), axis=1)
df['v8_nav_a'] = (1 + df['v8_ret_a']).cumprod()
df['v8_dd_a'] = df['v8_nav_a'] / df['v8_nav_a'].cummax() - 1

# 方案B的V8（标普500避险）
print("计算方案B: V14国债换标普500（标普500+熔断）...")
df['v8_ret_b'] = df.apply(lambda r: compute_v8_ret(r, SP500), axis=1)
df['v8_nav_b'] = (1 + df['v8_ret_b']).cumprod()
df['v8_dd_b'] = df['v8_nav_b'] / df['v8_nav_b'].cummax() - 1

# 方案C = V8（标普500避险，无熔断）= 方案B的V8
print("计算方案C: V14不熔断+标普500（标普500无熔断）...")

# 应用熔断
def apply_circuit_breaker(raw_pos, raw_dd, n, safe_haven_id):
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
                final_position.append(safe_haven_id if sig == BOND else sig)
        else:
            if dd > -DD_RELEASE:
                in_cb = False
                final_position.append(safe_haven_id if sig == BOND else sig)
            else:
                final_position.append(safe_haven_id)
    return np.array(final_position)

# 方案A：熔断转国债
final_pos_a = apply_circuit_breaker(df['raw_position'].values, df['v8_dd_a'].values, n, BOND)

# 方案B：熔断转标普500
final_pos_b = apply_circuit_breaker(df['raw_position'].values, df['v8_dd_b'].values, n, SP500)

# 方案C：无熔断，直接用raw_position，BOND→SP500
final_pos_c = np.array([SP500 if int(p) == BOND else int(p) for p in df['raw_position'].values])

# 计算V14收益
def compute_v14_ret(final_pos, n):
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
            if p in all_ids: cost += FEE
            if pos in all_ids: cost += FEE
        rets[i] = (1 + gross) * (1 - cost) - 1
    return rets

df['v14_ret_a'] = compute_v14_ret(final_pos_a, n)
df['v14_nav_a'] = (1 + df['v14_ret_a']).cumprod()

df['v14_ret_b'] = compute_v14_ret(final_pos_b, n)
df['v14_nav_b'] = (1 + df['v14_ret_b']).cumprod()

df['v14_ret_c'] = compute_v14_ret(final_pos_c, n)
df['v14_nav_c'] = (1 + df['v14_ret_c']).cumprod()

# ===== 5. 近20年逐年统计 =====
print("\n计算近20年逐年统计...")

end_date = df['date'].iloc[-1]
start_20y = end_date - pd.DateOffset(years=20)

mask_20y = df['date'] >= start_20y
df_20y = df[mask_20y].copy().reset_index(drop=True)
start_idx_orig = df.index[mask_20y][0]
final_pos_a_20y = final_pos_a[start_idx_orig:]
final_pos_b_20y = final_pos_b[start_idx_orig:]
final_pos_c_20y = final_pos_c[start_idx_orig:]

df_20y['year'] = df_20y['date'].dt.year

results = []
for year in sorted(df_20y['year'].unique()):
    yr_mask = df_20y['year'] == year
    yr = df_20y[yr_mask]
    yr_idx = yr.index.values
    
    def calc_stats(nav_col, ret_col, final_pos_arr):
        nav_start = yr[nav_col].iloc[0]
        nav_end = yr[nav_col].iloc[-1]
        ret = nav_end / nav_start - 1
        daily = yr[ret_col].values
        sharpe = np.mean(daily) / np.std(daily) * np.sqrt(252) if np.std(daily) > 0 else 0
        cummax = yr[nav_col].cummax()
        mdd = (yr[nav_col] / cummax - 1).min()
        hold = {}
        for pos_val in np.unique(final_pos_arr[yr_idx]):
            name = all_names[int(pos_val)]
            pct = np.mean(final_pos_arr[yr_idx] == pos_val) * 100
            hold[name] = round(pct, 1)
        return ret, sharpe, mdd, hold
    
    ret_a, sh_a, mdd_a, hold_a = calc_stats('v14_nav_a', 'v14_ret_a', final_pos_a_20y)
    ret_b, sh_b, mdd_b, hold_b = calc_stats('v14_nav_b', 'v14_ret_b', final_pos_b_20y)
    ret_c, sh_c, mdd_c, hold_c = calc_stats('v14_nav_c', 'v14_ret_c', final_pos_c_20y)
    
    results.append({
        'year': int(year),
        'ret_a': ret_a, 'ret_b': ret_b, 'ret_c': ret_c,
        'diff_ba': ret_b - ret_a, 'diff_ca': ret_c - ret_a,
        'sharpe_a': sh_a, 'sharpe_b': sh_b, 'sharpe_c': sh_c,
        'mdd_a': mdd_a, 'mdd_b': mdd_b, 'mdd_c': mdd_c,
        'hold_a': hold_a, 'hold_b': hold_b, 'hold_c': hold_c,
        'days': len(yr),
    })

# 总体统计
def calc_overall(nav_col, ret_col):
    total_ret = df_20y[nav_col].iloc[-1] / df_20y[nav_col].iloc[0] - 1
    n_yr = len(results)
    ann_ret = (1 + total_ret) ** (1 / n_yr) - 1
    daily = df_20y[ret_col].values
    sharpe = np.mean(daily) / np.std(daily) * np.sqrt(252) if np.std(daily) > 0 else 0
    vol = np.std(daily) * np.sqrt(252)
    cummax = df_20y[nav_col].cummax()
    mdd = (df_20y[nav_col] / cummax - 1).min()
    return total_ret, ann_ret, sharpe, vol, mdd

tot_a, ann_a, sh_a_all, vol_a, mdd_a_all = calc_overall('v14_nav_a', 'v14_ret_a')
tot_b, ann_b, sh_b_all, vol_b, mdd_b_all = calc_overall('v14_nav_b', 'v14_ret_b')
tot_c, ann_c, sh_c_all, vol_c, mdd_c_all = calc_overall('v14_nav_c', 'v14_ret_c')

# ===== 6. 打印结果 =====
print(f"\n{'='*120}")
print(f"  近20年 ({start_20y.date()} ~ {end_date.date()}, {len(df_20y)}天)")
print(f"{'='*120}")
print(f"  {'年份':>6}  {'A原版(国债)':>12}  {'B国债换标普':>12}  {'C不熔断+标普':>13}  {'B-A差':>10}  {'C-A差':>10}  {'夏普A':>6}  {'夏普B':>6}  {'夏普C':>6}  {'回撤A':>8}  {'回撤B':>8}  {'回撤C':>8}")
print(f"  {'-'*115}")
for r in results:
    print(f"  {r['year']:>6}  {r['ret_a']*100:>+11.2f}%  {r['ret_b']*100:>+11.2f}%  {r['ret_c']*100:>+12.2f}%  {r['diff_ba']*100:>+9.2f}%  {r['diff_ca']*100:>+9.2f}%  {r['sharpe_a']:>5.2f}  {r['sharpe_b']:>5.2f}  {r['sharpe_c']:>5.2f}  {r['mdd_a']*100:>7.2f}%  {r['mdd_b']*100:>7.2f}%  {r['mdd_c']*100:>7.2f}%")

print(f"  {'-'*115}")
print(f"  {'总计':>6}  {tot_a*100:>+11.2f}%  {tot_b*100:>+11.2f}%  {tot_c*100:>+12.2f}%  {(tot_b-tot_a)*100:>+9.2f}%  {(tot_c-tot_a)*100:>+9.2f}%")
print(f"  {'年化':>6}  {ann_a*100:>+11.2f}%  {ann_b*100:>+11.2f}%  {ann_c*100:>+12.2f}%  {(ann_b-ann_a)*100:>+9.2f}%  {(ann_c-ann_a)*100:>+9.2f}%")
print(f"  {'夏普':>6}  {'':>12}  {'':>12}  {'':>13}  {'':>10}  {'':>10}  {sh_a_all:>5.2f}  {sh_b_all:>5.2f}  {sh_c_all:>5.2f}")
print(f"  {'波动':>6}  {'':>12}  {'':>12}  {'':>13}  {'':>10}  {'':>10}  {vol_a*100:>5.2f}%  {vol_b*100:>5.2f}%  {vol_c*100:>5.2f}%")
print(f"  {'最大回撤':>6}  {'':>12}  {'':>12}  {'':>13}  {'':>10}  {'':>10}  {'':>6}  {'':>6}  {'':>6}  {mdd_a_all*100:>7.2f}%  {mdd_b_all*100:>7.2f}%  {mdd_c_all*100:>7.2f}%")

# ===== 7. 生成HTML =====
print("\n生成HTML报告...")

year_rows = []
for r in results:
    ret_a_cls = 'pos' if r['ret_a'] >= 0 else 'neg'
    ret_b_cls = 'pos' if r['ret_b'] >= 0 else 'neg'
    ret_c_cls = 'pos' if r['ret_c'] >= 0 else 'neg'
    diff_ba_cls = 'pos' if r['diff_ba'] >= 0 else 'neg'
    diff_ca_cls = 'pos' if r['diff_ca'] >= 0 else 'neg'
    mdd_a_cls = 'dd-danger' if r['mdd_a'] < -DD_TRIGGER else ('dd-warn' if r['mdd_a'] < -DD_RELEASE else 'dd-ok')
    mdd_b_cls = 'dd-danger' if r['mdd_b'] < -DD_TRIGGER else ('dd-warn' if r['mdd_b'] < -DD_RELEASE else 'dd-ok')
    mdd_c_cls = 'dd-danger' if r['mdd_c'] < -DD_TRIGGER else ('dd-warn' if r['mdd_c'] < -DD_RELEASE else 'dd-ok')
    
    year_rows.append(f'''<tr>
        <td class="yr">{r['year']}</td>
        <td class="{ret_a_cls}">{r['ret_a']*100:+.2f}%</td>
        <td class="{ret_b_cls}">{r['ret_b']*100:+.2f}%</td>
        <td class="{ret_c_cls}">{r['ret_c']*100:+.2f}%</td>
        <td class="{diff_ba_cls}">{r['diff_ba']*100:+.2f}%</td>
        <td class="{diff_ca_cls}">{r['diff_ca']*100:+.2f}%</td>
        <td>{r['sharpe_a']:.2f}</td>
        <td>{r['sharpe_b']:.2f}</td>
        <td>{r['sharpe_c']:.2f}</td>
        <td class="{mdd_a_cls}">{r['mdd_a']*100:.2f}%</td>
        <td class="{mdd_b_cls}">{r['mdd_b']*100:.2f}%</td>
        <td class="{mdd_c_cls}">{r['mdd_c']*100:.2f}%</td>
    </tr>''')

# 总计行
year_rows.append(f'''<tr class="total-row">
    <td class="yr">总计</td>
    <td class="{'pos' if tot_a>=0 else 'neg'}">{tot_a*100:+.2f}%</td>
    <td class="{'pos' if tot_b>=0 else 'neg'}">{tot_b*100:+.2f}%</td>
    <td class="{'pos' if tot_c>=0 else 'neg'}">{tot_c*100:+.2f}%</td>
    <td class="{'pos' if tot_b-tot_a>=0 else 'neg'}">{(tot_b-tot_a)*100:+.2f}%</td>
    <td class="{'pos' if tot_c-tot_a>=0 else 'neg'}">{(tot_c-tot_a)*100:+.2f}%</td>
    <td colspan="6"></td>
</tr>''')
year_rows.append(f'''<tr class="total-row">
    <td class="yr">年化</td>
    <td class="{'pos' if ann_a>=0 else 'neg'}">{ann_a*100:+.2f}%</td>
    <td class="{'pos' if ann_b>=0 else 'neg'}">{ann_b*100:+.2f}%</td>
    <td class="{'pos' if ann_c>=0 else 'neg'}">{ann_c*100:+.2f}%</td>
    <td class="{'pos' if ann_b-ann_a>=0 else 'neg'}">{(ann_b-ann_a)*100:+.2f}%</td>
    <td class="{'pos' if ann_c-ann_a>=0 else 'neg'}">{(ann_c-ann_a)*100:+.2f}%</td>
    <td colspan="6"></td>
</tr>''')
year_rows.append(f'''<tr class="total-row">
    <td class="yr">夏普</td>
    <td colspan="6"></td>
    <td>{sh_a_all:.2f}</td>
    <td>{sh_b_all:.2f}</td>
    <td>{sh_c_all:.2f}</td>
    <td class="{'dd-danger' if mdd_a_all < -DD_TRIGGER else 'dd-warn' if mdd_a_all < -DD_RELEASE else 'dd-ok'}">{mdd_a_all*100:.2f}%</td>
    <td class="{'dd-danger' if mdd_b_all < -DD_TRIGGER else 'dd-warn' if mdd_b_all < -DD_RELEASE else 'dd-ok'}">{mdd_b_all*100:.2f}%</td>
    <td class="{'dd-danger' if mdd_c_all < -DD_TRIGGER else 'dd-warn' if mdd_c_all < -DD_RELEASE else 'dd-ok'}">{mdd_c_all*100:.2f}%</td>
</tr>''')

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14三方案对比 — 近20年逐年收益</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Microsoft YaHei','Segoe UI',sans-serif; background:#f5f6fa; color:#333; padding:16px; max-width:1400px; margin:0 auto; }}
h1 {{ font-size:22px; margin-bottom:4px; }}
.sub {{ font-size:12px; color:#888; margin-bottom:16px; }}
.summary {{ display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap; }}
.s-card {{ background:#fff; border-radius:8px; padding:10px 16px; box-shadow:0 1px 4px rgba(0,0,0,0.06); min-width:140px; }}
.s-card .label {{ font-size:11px; color:#999; }}
.s-card .val {{ font-size:18px; font-weight:700; }}
.s-card .sub-val {{ font-size:12px; color:#666; }}
.s-card.a {{ border-left:4px solid #95a5a6; }}
.s-card.b {{ border-left:4px solid #e67e22; }}
.s-card.c {{ border-left:4px solid #3498db; }}
.card {{ background:#fff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.08); overflow:hidden; overflow-x:auto; margin-bottom:16px; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; min-width:1100px; }}
th {{ background:#f8f9fa; padding:10px 6px; text-align:center; font-weight:600; border-bottom:2px solid #e0e0e0; white-space:nowrap; }}
td {{ padding:8px 6px; text-align:center; border-bottom:1px solid #eee; }}
tr:hover td {{ background:#f8f9ff; }}
.total-row td {{ font-weight:700; background:#f0f4ff; border-top:2px solid #d0d8f0; }}
.yr {{ font-weight:600; }}
.pos {{ color:#e74c3c; font-weight:600; }}
.neg {{ color:#27ae60; font-weight:600; }}
.dd-ok {{ color:#27ae60; }}
.dd-warn {{ color:#f39c12; }}
.dd-danger {{ color:#e74c3c; font-weight:600; }}
.col-a {{ background:#f8f8f8; }}
.col-b {{ background:#fef9f5; }}
.col-c {{ background:#f5f9ff; }}
.rules {{ padding:12px 16px; background:#fff; border-radius:8px; font-size:11px; color:#888; line-height:1.8; }}
</style>
</head>
<body>
<h1>V14三方案对比 — 近20年逐年收益</h1>
<div class="sub">决策日期=T日 · 决策bf=(T-1收盘/T-1的MA20)-1 · T日开盘执行 · 手续费0.02% · {start_20y.date()} ~ {end_date.date()} · {len(df_20y)}天</div>

<div class="summary">
    <div class="s-card a">
        <div class="label">方案A：V14原版（国债+熔断）</div>
        <div class="val {'pos' if tot_a>=0 else 'neg'}">{tot_a*100:+.2f}%</div>
        <div class="sub-val">年化{ann_a*100:+.2f}% · 夏普{sh_a_all:.2f} · 回撤{mdd_a_all*100:.2f}%</div>
    </div>
    <div class="s-card b">
        <div class="label">方案B：国债换标普500（+熔断）</div>
        <div class="val {'pos' if tot_b>=0 else 'neg'}">{tot_b*100:+.2f}%</div>
        <div class="sub-val">年化{ann_b*100:+.2f}% · 夏普{sh_b_all:.2f} · 回撤{mdd_b_all*100:.2f}%</div>
    </div>
    <div class="s-card c">
        <div class="label">方案C：不熔断+标普500</div>
        <div class="val {'pos' if tot_c>=0 else 'neg'}">{tot_c*100:+.2f}%</div>
        <div class="sub-val">年化{ann_c*100:+.2f}% · 夏普{sh_c_all:.2f} · 回撤{mdd_c_all*100:.2f}%</div>
    </div>
</div>

<div class="card">
<table>
<thead><tr>
    <th rowspan="2">年份</th>
    <th colspan="3">年收益</th>
    <th colspan="2">差值（vs原版）</th>
    <th colspan="3">夏普率</th>
    <th colspan="3">最大回撤</th>
</tr>
<tr>
    <th class="col-a">A原版<br>(国债+熔断)</th>
    <th class="col-b">B国债换标普<br>(+熔断)</th>
    <th class="col-c">C不熔断<br>+标普500</th>
    <th>B-A</th>
    <th>C-A</th>
    <th class="col-a">A</th>
    <th class="col-b">B</th>
    <th class="col-c">C</th>
    <th class="col-a">A</th>
    <th class="col-b">B</th>
    <th class="col-c">C</th>
</tr></thead>
<tbody>
{''.join(year_rows)}
</tbody>
</table>
</div>

<div class="rules">
    <b>三方案说明：</b><br>
    <b>方案A（原版）：</b>全bf&lt;0持国债，V8回撤>5%触发熔断转国债，恢复<4%解除。避险资产=国债<br>
    <b>方案B（国债换标普500）：</b>全bf&lt;0持标普500，V8回撤>5%触发熔断转标普500，恢复<4%解除。避险资产=标普500<br>
    <b>方案C（不熔断+标普500）：</b>无熔断机制，全bf&lt;0持标普500。相当于V8基线+标普500避险<br>
    <b>差值</b>正值表示优于原版。标普500数据源：Desktop/美国标准普尔500指数历史数据.csv（2006-07~2026-05）+ data/7_标普500.csv比率调整补充（2026-05~2026-07）。
</div>
</body></html>'''

html_path = os.path.join(BASE_DIR, 'v14_three_way_compare.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"HTML报告已生成: {html_path}")

# 保存JSON
json_data = {
    'start': start_20y.strftime('%Y-%m-%d'),
    'end': end_date.strftime('%Y-%m-%d'),
    'n_days': len(df_20y),
    'total_a': tot_a, 'total_b': tot_b, 'total_c': tot_c,
    'ann_a': ann_a, 'ann_b': ann_b, 'ann_c': ann_c,
    'sharpe_a': sh_a_all, 'sharpe_b': sh_b_all, 'sharpe_c': sh_c_all,
    'mdd_a': mdd_a_all, 'mdd_b': mdd_b_all, 'mdd_c': mdd_c_all,
    'yearly': results,
}
json_path = os.path.join(BASE_DIR, 'v14_three_way_compare.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
print(f"JSON数据已保存: {json_path}")
