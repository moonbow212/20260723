# -*- coding: utf-8 -*-
"""V14(5%/4%) + 股债利差豁免熔断 近1/3/5/10/20年逐年统计

策略定义：
  - 决策日期 = T日（执行日）
  - 决策bf = (T-1日收盘价 / T-1日MA20) - 1
  - T日开盘执行，收益口径 open-to-open
  - 5%回撤触发熔断转国债，4%解除
  - ★新增：沪深300股债利差 > 7%时，熔断机制不生效（不触发熔断，已熔断则解除）
数据源：data/目录CSV + 桌面Excel利差数据
"""
import pandas as pd
import numpy as np
import json, os

FEE = 0.0002
DD_TRIGGER = 0.05
DD_RELEASE = 0.04
SPREAD_THRESHOLD = 7.0  # 股债利差阈值(%)

STOCK_ALL = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}
all_names = {0:'空仓', 1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPREAD_FILE = 'C:/Users/wbl/Desktop/操作明细_近20年.xlsx'

# ===== 0. 读取股债利差数据 =====
print("读取股债利差数据...")
spread_df = pd.read_excel(SPREAD_FILE, sheet_name='操作明细', skiprows=2)
spread_df = spread_df.dropna(subset=['操作日期'])
spread_df['操作日期'] = pd.to_datetime(spread_df['操作日期'])
spread_df = spread_df[['操作日期', '股债利差(%)']].rename(columns={'操作日期': 'date', '股债利差(%)': 'spread'})
spread_df = spread_df.sort_values('date').reset_index(drop=True)
print(f"  利差数据: {spread_df['date'].iloc[0].date()} ~ {spread_df['date'].iloc[-1].date()}, {len(spread_df)}条")
print(f"  利差范围: {spread_df['spread'].min():.2f}% ~ {spread_df['spread'].max():.2f}%")
print(f"  利差>7%的记录数: {len(spread_df[spread_df['spread'] > SPREAD_THRESHOLD])}")

# ===== 1. 读取行情数据 =====
print("\n读取行情数据...")
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

last_date = dfs[BOND]['date'].max()
print(f"\n数据最新日期: {last_date.date()}")

# ===== 2. 构建合并数据 =====
def build_merged_data(start_date, end_date):
    """国债日历为基准，各股票left join，利差前向填充"""
    df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)

    for i in STOCK_ALL:
        cols = ['date', f'open_{i}', f'close_{i}', f'ma20_{i}', f'bf_{i}', f'ratio_{i}']
        df = pd.merge(df, dfs[i][cols], on='date', how='left')

    # 前向填充利差数据
    df = pd.merge_asof(df, spread_df, on='date', direction='backward')
    # 对于利差数据开始之前的日期，用第一个利差值填充
    first_spread_idx = df['spread'].first_valid_index()
    if first_spread_idx is not None and first_spread_idx > 0:
        df.loc[:first_spread_idx-1, 'spread'] = df.loc[first_spread_idx, 'spread']

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

# ===== 3. 熔断逻辑 =====
def apply_circuit_breaker_original(df, all_ids, bond_id):
    """原版V14熔断：5%触发/4%解除"""
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

def apply_circuit_breaker_spread(df, all_ids, bond_id):
    """修改版V14熔断：利差>7%时熔断不生效"""
    raw_pos = df['raw_position'].values
    raw_dd = df['raw_dd'].values
    spread_arr = df['spread'].values
    n = len(df)
    in_cb = False
    final_position = []
    cb_exempt_count = 0
    cb_release_by_spread = 0
    for i in range(n):
        sig = int(raw_pos[i])
        dd = raw_dd[i]
        spread_val = spread_arr[i]
        spread_exempt = pd.notna(spread_val) and spread_val > SPREAD_THRESHOLD

        if not in_cb:
            if dd < -DD_TRIGGER and sig != bond_id and not spread_exempt:
                in_cb = True
                final_position.append(bond_id)
            else:
                # 利差>7%时即使dd<-5%也不熔断
                if spread_exempt and dd < -DD_TRIGGER and sig != bond_id:
                    cb_exempt_count += 1
                final_position.append(sig)
        else:
            if dd > -DD_RELEASE or spread_exempt:
                # 利差>7%时强制解除熔断
                if spread_exempt and dd <= -DD_RELEASE:
                    cb_release_by_spread += 1
                in_cb = False
                final_position.append(sig)
            else:
                final_position.append(bond_id)
    print(f"    利差豁免熔断触发: {cb_exempt_count}次, 利差强制解除熔断: {cb_release_by_spread}次")
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

all_period_results = {}
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    sd = periods_config[pname]
    df, all_ids = build_merged_data(sd, last_date)

    # 原版V14
    pos_orig = apply_circuit_breaker_original(df, all_ids, BOND)
    rets_orig = compute_v14_ret(df, all_ids, BOND, pos_orig)
    df['pos_orig'] = pos_orig
    df['ret_orig'] = rets_orig

    # 修改版（利差豁免）
    print(f"\n{pname}:")
    pos_spread = apply_circuit_breaker_spread(df, all_ids, BOND)
    rets_spread = compute_v14_ret(df, all_ids, BOND, pos_spread)
    df['pos_spread'] = pos_spread
    df['ret_spread'] = rets_spread
    df['year'] = df['date'].dt.year

    # 利差>7%的天数统计
    spread_above = int((df['spread'] > SPREAD_THRESHOLD).sum())
    print(f"  利差>7%天数: {spread_above}/{len(df)} ({spread_above/len(df)*100:.1f}%)")

    years = sorted(df['year'].unique())
    yearly_list = []
    for y in years:
        sub = df[df['year'] == y].copy()
        ny = len(sub)

        # 原版
        year_ret_orig = (1 + sub['ret_orig']).prod() - 1
        nav_orig = (1 + sub['ret_orig']).cumprod()
        mdd_orig = ((nav_orig - nav_orig.cummax()) / nav_orig.cummax()).min()

        # 修改版
        year_ret_spread = (1 + sub['ret_spread']).prod() - 1
        nav_spread = (1 + sub['ret_spread']).cumprod()
        mdd_spread = ((nav_spread - nav_spread.cummax()) / nav_spread.cummax()).min()

        # 当年利差>7%天数
        spread_days = int((sub['spread'] > SPREAD_THRESHOLD).sum())

        # 差异
        diff = year_ret_spread - year_ret_orig

        # 持仓差异天数
        pos_diff_days = int((sub['pos_orig'] != sub['pos_spread']).sum())

        yearly_list.append({
            'year': int(y),
            'n_days': int(ny),
            'spread_days': spread_days,
            'ret_orig': round(float(year_ret_orig)*100, 2),
            'ret_spread': round(float(year_ret_spread)*100, 2),
            'diff': round(float(diff)*100, 2),
            'mdd_orig': round(float(mdd_orig)*100, 2),
            'mdd_spread': round(float(mdd_spread)*100, 2),
            'pos_diff_days': pos_diff_days,
        })

    # 整体统计
    total_ret_orig = (1 + df['ret_orig']).prod() - 1
    total_ret_spread = (1 + df['ret_spread']).prod() - 1
    nav_o = (1 + df['ret_orig']).cumprod()
    nav_s = (1 + df['ret_spread']).cumprod()
    mdd_o = ((nav_o - nav_o.cummax()) / nav_o.cummax()).min()
    mdd_s = ((nav_s - nav_s.cummax()) / nav_s.cummax()).min()
    std_o = df['ret_orig'].std()
    std_s = df['ret_spread'].std()
    sharpe_o = np.sqrt(252) * df['ret_orig'].mean() / std_o if std_o > 0 else 0
    sharpe_s = np.sqrt(252) * df['ret_spread'].mean() / std_s if std_s > 0 else 0
    ann_o = (1 + total_ret_orig) ** (252/len(df)) - 1
    ann_s = (1 + total_ret_spread) ** (252/len(df)) - 1

    all_period_results[pname] = {
        'start': df['date'].iloc[0].strftime('%Y-%m-%d'),
        'end': df['date'].iloc[-1].strftime('%Y-%m-%d'),
        'n_days': int(len(df)),
        'spread_days': spread_above,
        'yearly': yearly_list,
        'overall': {
            'ret_orig': round(float(total_ret_orig)*100, 2),
            'ret_spread': round(float(total_ret_spread)*100, 2),
            'diff': round(float(total_ret_spread - total_ret_orig)*100, 2),
            'ann_orig': round(float(ann_o)*100, 2),
            'ann_spread': round(float(ann_s)*100, 2),
            'mdd_orig': round(float(mdd_o)*100, 2),
            'mdd_spread': round(float(mdd_s)*100, 2),
            'sharpe_orig': round(float(sharpe_o), 2),
            'sharpe_spread': round(float(sharpe_s), 2),
        },
    }
    print(f"  原版: 总收益={float(total_ret_orig)*100:+.2f}%, 夏普={sharpe_o:.2f}, 回撤={float(mdd_o)*100:.2f}%")
    print(f"  利差版: 总收益={float(total_ret_spread)*100:+.2f}%, 夏普={sharpe_s:.2f}, 回撤={float(mdd_s)*100:.2f}%")
    print(f"  差异: {float(total_ret_spread - total_ret_orig)*100:+.2f}%")

# 导出JSON
with open(os.path.join(BASE_DIR, 'v14_yearly_spread.json'), 'w', encoding='utf-8') as f:
    json.dump(all_period_results, f, ensure_ascii=False, indent=2)
print("\n数据已保存到 v14_yearly_spread.json")

# ===== 5. 生成HTML =====
html_parts = []
html_parts.append('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14策略 股债利差豁免熔断 逐年统计</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Microsoft YaHei','Segoe UI',sans-serif; background:#f5f6fa; color:#333; padding:20px; }
h1 { text-align:center; font-size:22px; margin-bottom:5px; }
.sub { text-align:center; font-size:13px; color:#666; margin-bottom:8px; }
.note { background:#fff3cd; border:1px solid #ffeaa7; border-radius:6px; padding:10px 16px; margin-bottom:16px; font-size:13px; color:#856404; line-height:1.6; }
.period-card { background:#fff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.08); margin-bottom:24px; overflow:hidden; }
.period-header { background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; padding:14px 20px; }
.period-header h2 { font-size:18px; margin-bottom:4px; }
.period-header .info { font-size:13px; opacity:0.9; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th { background:#f8f9fa; padding:8px 6px; text-align:center; font-weight:600; border-bottom:2px solid #e0e0e0; white-space:nowrap; }
td { padding:7px 6px; text-align:center; border-bottom:1px solid #eee; }
tr:hover td { background:#f8f9ff; }
.pos { color:#e74c3c; font-weight:600; }
.neg { color:#27ae60; font-weight:600; }
.diff-pos { color:#e74c3c; font-weight:600; }
.diff-neg { color:#27ae60; font-weight:600; }
.diff-zero { color:#999; }
.mdd-val { color:#e74c3c; }
.sharpe-pos { color:#e74c3c; font-weight:600; }
.sharpe-neg { color:#27ae60; }
.overall-row { background:#fffde7 !important; font-weight:600; }
.overall-row td { border-top:2px solid #f0e68c; border-bottom:2px solid #f0e68c; }
.summary-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:24px; }
.summary-card { background:#fff; border-radius:8px; padding:14px; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.06); }
.summary-card h3 { font-size:14px; color:#666; margin-bottom:8px; }
.summary-card .val { font-size:18px; font-weight:700; }
.summary-card .sub-val { font-size:11px; color:#888; margin-top:3px; }
.summary-card .diff-val { font-size:14px; font-weight:700; margin-top:4px; }
.spread-badge { display:inline-block; padding:1px 5px; border-radius:3px; background:#e8f5e9; color:#2e7d32; font-size:10px; }
</style>
</head>
<body>
<h1>V14策略 股债利差豁免熔断 逐年统计</h1>
<div class="sub">MA20轮动 · 决策bf=(T-1收盘/T-1的MA20)-1 · T日开盘执行 · 5%回撤熔断/4%解除 · 手续费0.02%</div>
<div class="note">
<b>策略规则：</b>原版V14基础上，当沪深300股债利差 &gt; 7%时，熔断机制不生效（不触发熔断，已在熔断中则强制解除）。<br>
<b>利差数据来源：</b>桌面Excel「操作明细_近20年.xlsx」，半月频（每月1日和16日左右），前向填充到日频。<br>
<b>对比说明：</b>原版 = V14标准5%/4%熔断；利差版 = 利差>7%时豁免熔断。收益口径open-to-open。
</div>
''')

# 汇总卡片
html_parts.append('<div class="summary-grid">')
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = all_period_results[pname]
    o = r['overall']
    ret_cls_o = 'pos' if o['ret_orig'] >= 0 else 'neg'
    ret_cls_s = 'pos' if o['ret_spread'] >= 0 else 'neg'
    diff_cls = 'diff-pos' if o['diff'] > 0 else ('diff-neg' if o['diff'] < 0 else 'diff-zero')
    html_parts.append(f'''<div class="summary-card">
    <h3>{pname}</h3>
    <div style="font-size:11px;color:#888;">原版</div>
    <div class="val {ret_cls_o}">{o["ret_orig"]:+.2f}%</div>
    <div class="sub-val">夏普 {o["sharpe_orig"]:.2f} · 回撤 {o["mdd_orig"]:.2f}%</div>
    <div style="font-size:11px;color:#888;margin-top:6px;">利差版</div>
    <div class="val {ret_cls_s}">{o["ret_spread"]:+.2f}%</div>
    <div class="sub-val">夏普 {o["sharpe_spread"]:.2f} · 回撤 {o["mdd_spread"]:.2f}%</div>
    <div class="diff-val {diff_cls}">差异 {o["diff"]:+.2f}%</div>
    <div class="sub-val">利差>7%: {r["spread_days"]}天</div>
    </div>''')
html_parts.append('</div>')

# 各时段表格
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = all_period_results[pname]
    html_parts.append(f'''<div class="period-card">
    <div class="period-header">
        <h2>{pname}</h2>
        <div class="info">{r["start"]} ~ {r["end"]} · {r["n_days"]}天 · 利差>7%天数: {r["spread_days"]} ({r["spread_days"]/r["n_days"]*100:.1f}%)</div>
    </div>
    <table>
    <thead><tr>
        <th>年份</th><th>交易日</th><th>利差>7%天数</th>
        <th>原版收益</th><th>利差版收益</th><th>差异</th>
        <th>原版回撤</th><th>利差版回撤</th>
        <th>持仓差异天数</th>
    </tr></thead><tbody>''')

    for yd in r['yearly']:
        ret_cls_o = 'pos' if yd['ret_orig'] >= 0 else 'neg'
        ret_cls_s = 'pos' if yd['ret_spread'] >= 0 else 'neg'
        diff_cls = 'diff-pos' if yd['diff'] > 0 else ('diff-neg' if yd['diff'] < 0 else 'diff-zero')
        spread_badge = f'<span class="spread-badge">{yd["spread_days"]}天</span>' if yd['spread_days'] > 0 else '0'
        html_parts.append(f'''<tr>
            <td>{yd["year"]}</td>
            <td>{yd["n_days"]}</td>
            <td>{spread_badge}</td>
            <td class="{ret_cls_o}">{yd["ret_orig"]:+.2f}%</td>
            <td class="{ret_cls_s}">{yd["ret_spread"]:+.2f}%</td>
            <td class="{diff_cls}">{yd["diff"]:+.2f}%</td>
            <td class="mdd-val">{yd["mdd_orig"]:.2f}%</td>
            <td class="mdd-val">{yd["mdd_spread"]:.2f}%</td>
            <td>{yd["pos_diff_days"]}</td>
        </tr>''')

    o = r['overall']
    ret_cls_o = 'pos' if o['ret_orig'] >= 0 else 'neg'
    ret_cls_s = 'pos' if o['ret_spread'] >= 0 else 'neg'
    diff_cls = 'diff-pos' if o['diff'] > 0 else ('diff-neg' if o['diff'] < 0 else 'diff-zero')
    html_parts.append(f'''<tr class="overall-row">
        <td>整体</td>
        <td>{r["n_days"]}</td>
        <td>{r["spread_days"]}</td>
        <td class="{ret_cls_o}">{o["ret_orig"]:+.2f}%</td>
        <td class="{ret_cls_s}">{o["ret_spread"]:+.2f}%</td>
        <td class="{diff_cls}">{o["diff"]:+.2f}%</td>
        <td class="mdd-val">{o["mdd_orig"]:.2f}%</td>
        <td class="mdd-val">{o["mdd_spread"]:.2f}%</td>
        <td>-</td>
    </tr>''')

    html_parts.append('</tbody></table></div>')

html_parts.append('''
<div style="text-align:center;font-size:12px;color:#999;margin-top:20px;">
收益口径: open-to-open · 差异 = 利差版收益 - 原版收益 · 持仓差异天数 = 两版持仓不同的交易日数<br>
决策bf=(T-1收盘/T-1的MA20)-1 · T-1日收盘信号→T日开盘执行 · 利差数据半月频前向填充到日频
</div>
</body></html>''')

html = '\n'.join(html_parts)
out_path = os.path.join(BASE_DIR, 'v14_yearly_spread.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nHTML报告已生成: {out_path}")
