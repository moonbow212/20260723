# -*- coding: utf-8 -*-
"""V14-止损策略(个持仓5%止损/4%回升) 近1/3/5/10/20年逐年统计（动态标的池）
机制：持有股票从买入价下跌5%→清仓转国债；直到bf排行改变或该标的回升至亏损4%以内再买入。
所有时段均用全部8股+国债，各标的独立计算MA20/bf后left join到国债日历。
"""
import pandas as pd
import numpy as np
import json, os

FEE = 0.0002
SL_TRIGGER = 0.05   # 从买入价下跌5%触发止损
SL_RELEASE = 0.04   # 回升至亏损4%以内解除止损

def find_file(name):
    for p in [f'C:/Users/wbl/Desktop/同花顺历史数据/{name}.xlsx',
              f'C:/Users/wbl/Desktop/{name}.xlsx']:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"未找到 {name}.xlsx")

files = {
    1: find_file('上证50'), 2: find_file('创业板50'), 3: find_file('纳斯达克100'),
    4: find_file('沪深300'), 5: find_file('中证500'), 6: find_file('中证1000'),
    7: find_file('标普500'), 8: find_file('科创50'), 9: find_file('国债'),
}
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}
all_names = {0:'空仓', 1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}
STOCK_ALL = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9

# ===== 1. 读取数据 + 各标的独立计算MA20/bf =====
dfs = {}
for i, path in files.items():
    d = pd.read_csv(path, sep='\t', encoding='gbk')
    d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
    d = d[['date','开盘','收盘']].rename(columns={'开盘':f'open_{i}','收盘':f'close_{i}'})
    for c in [f'open_{i}',f'close_{i}']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d.dropna(subset=[f'open_{i}', f'close_{i}']).sort_values('date').reset_index(drop=True)
    if i != BOND:
        d[f'ma20_{i}'] = d[f'close_{i}'].rolling(20).mean()
        d[f'bf_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}'] - 1
        d[f'ratio_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}']
    dfs[i] = d

last_date = dfs[BOND]['date'].max()
print(f"数据最新日期: {last_date.date()}")

# ===== 2. 以国债交易日历为基准，left join所有股票 =====
def build_merged_data(start_date, end_date):
    df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)

    for i in STOCK_ALL:
        cols = ['date', f'open_{i}', f'close_{i}', f'ma20_{i}', f'bf_{i}', f'ratio_{i}']
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
    return df, all_ids

# ===== 3. 个持仓止损机制 =====
def apply_stoploss(df, stock_ids, bond_id):
    """个持仓止损：从买入价下跌5%→国债；
    bf排行改变(不同标的成为最高bf) 或 该标的回升至亏损4%以内 → 再买入"""
    n = len(df)
    raw_sig = df['raw_signal'].values.astype(int)

    final_pos = np.zeros(n, dtype=int)
    entry_price = np.nan
    stopped_stock = -1
    in_stoploss = False
    stoploss_count = 0  # 统计止损触发次数

    final_pos[0] = 0  # 起始空仓

    for i in range(1, n):
        sig = int(raw_sig[i-1])  # 正常信号（前日收盘决策，今日开盘执行）
        held_yesterday = int(final_pos[i-1])

        # ---- 检查止损触发（仅正常模式）----
        if not in_stoploss and held_yesterday in stock_ids:
            close_prev = df[f'close_{held_yesterday}'].iloc[i-1]
            if pd.notna(close_prev) and pd.notna(entry_price) and entry_price > 0:
                loss = close_prev / entry_price - 1
                if loss < -SL_TRIGGER:
                    in_stoploss = True
                    stopped_stock = held_yesterday
                    stoploss_count += 1

        # ---- 决定今日持仓 ----
        if in_stoploss:
            if sig in stock_ids and sig != stopped_stock:
                # bf排行改变 → 买入新标的，解除止损
                final_pos[i] = sig
                entry_price = df[f'open_{sig}'].iloc[i]
                in_stoploss = False
                stopped_stock = -1
            elif sig == stopped_stock:
                # 同一标的仍是最高bf → 检查回升
                close_prev = df[f'close_{stopped_stock}'].iloc[i-1]
                if pd.notna(close_prev) and pd.notna(entry_price) and entry_price > 0:
                    loss = close_prev / entry_price - 1
                    if loss >= -SL_RELEASE:
                        # 回升至亏损4%以内 → 买回
                        final_pos[i] = sig
                        entry_price = df[f'open_{sig}'].iloc[i]
                        in_stoploss = False
                        stopped_stock = -1
                    else:
                        final_pos[i] = bond_id
                else:
                    final_pos[i] = bond_id
            else:
                # 信号为国债（全部标的低于MA20）→ 继续持国债
                final_pos[i] = bond_id
        else:
            # 正常模式
            final_pos[i] = sig
            if sig in stock_ids and held_yesterday != sig:
                # 切换到新标的 → 更新买入价
                entry_price = df[f'open_{sig}'].iloc[i]

    return final_pos, stoploss_count

def compute_ret(df, all_ids, bond_id, pos):
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
    pos_sl, sl_count = apply_stoploss(df, STOCK_ALL, BOND)
    sl_rets = compute_ret(df, all_ids, BOND, pos_sl)
    df['sl_pos'] = pos_sl
    df['sl_ret'] = sl_rets
    df['year'] = df['date'].dt.year

    # 统计各标的可用情况
    avail_info = {}
    for i in STOCK_ALL:
        first_date = df.loc[df[f'bf_{i}'].notna(), 'date'].min()
        last_dt = df.loc[df[f'bf_{i}'].notna(), 'date'].max()
        n_avail = int(df[f'bf_{i}'].notna().sum())
        avail_info[names[i]] = {
            'first': first_date.strftime('%Y-%m-%d') if pd.notna(first_date) else 'N/A',
            'last': last_dt.strftime('%Y-%m-%d') if pd.notna(last_dt) else 'N/A',
            'n_days': n_avail,
            'pct': round(n_avail / len(df) * 100, 1),
        }

    years = sorted(df['year'].unique())
    yearly_list = []
    for y in years:
        sub = df[df['year'] == y].copy()
        ny = len(sub)
        year_ret = (1 + sub['sl_ret']).prod() - 1
        year_nav = (1 + sub['sl_ret']).cumprod()
        year_mdd = ((year_nav - year_nav.cummax()) / year_nav.cummax()).min()
        std = sub['sl_ret'].std()
        sharpe = np.sqrt(252) * sub['sl_ret'].mean() / std if std > 0 else 0
        ann_vol = std * np.sqrt(252)
        # 年内止损次数
        year_sl_count = 0
        in_sl = False
        for j in sub.index:
            p = int(sub.loc[j, 'sl_pos'])
            prev_p = int(sub.loc[j-1, 'sl_pos']) if j > sub.index[0] else 0
            # 止损触发检测：从股票切到国债且不是正常信号
            # 更准确：检查pos序列中从stock到bond的切换
        # 简化：统计从股票直接切换到国债的次数
        pos_vals = sub['sl_pos'].values
        for j in range(1, len(pos_vals)):
            if pos_vals[j-1] in STOCK_ALL and pos_vals[j] == BOND:
                # 检查是否是止损（raw_signal仍是该股票但持仓变为国债）
                raw_sig_val = sub['raw_signal'].iloc[j-1] if j > 0 else BOND
                if int(raw_sig_val) == int(pos_vals[j-1]):
                    year_sl_count += 1

        holding = {}
        for a in STOCK_ALL + [BOND, 0]:
            cnt = int((sub['sl_pos'] == a).sum())
            if cnt > 0:
                holding[all_names[a]] = {'days': cnt, 'pct': round(cnt/ny*100, 2)}
        yearly_list.append({
            'year': int(y),
            'n_days': int(ny),
            'start': sub['date'].iloc[0].strftime('%Y-%m-%d'),
            'end': sub['date'].iloc[-1].strftime('%Y-%m-%d'),
            'ret': round(float(year_ret)*100, 2),
            'sharpe': round(float(sharpe), 2),
            'mdd': round(float(year_mdd)*100, 2),
            'ann_vol': round(float(ann_vol)*100, 2),
            'holding': holding,
            'switches': int(np.sum(np.diff(sub['sl_pos'].values) != 0)),
            'stoploss_count': int(year_sl_count),
        })

    total_ret = (1 + df['sl_ret']).prod() - 1
    nav_all = (1 + df['sl_ret']).cumprod()
    mdd_all = ((nav_all - nav_all.cummax()) / nav_all.cummax()).min()
    std_all = df['sl_ret'].std()
    sharpe_all = np.sqrt(252) * df['sl_ret'].mean() / std_all if std_all > 0 else 0
    ann_all = (1 + total_ret) ** (252/len(df)) - 1
    overall_holding = {}
    for a in STOCK_ALL + [BOND, 0]:
        cnt = int((df['sl_pos'] == a).sum())
        if cnt > 0:
            overall_holding[all_names[a]] = {'days': cnt, 'pct': round(cnt/len(df)*100, 2)}

    all_period_results[pname] = {
        'start': df['date'].iloc[0].strftime('%Y-%m-%d'),
        'end': df['date'].iloc[-1].strftime('%Y-%m-%d'),
        'n_days': int(len(df)),
        'avail_info': avail_info,
        'yearly': yearly_list,
        'overall': {
            'total_ret': round(float(total_ret)*100, 2),
            'ann_ret': round(float(ann_all)*100, 2),
            'mdd': round(float(mdd_all)*100, 2),
            'sharpe': round(float(sharpe_all), 2),
            'ann_vol': round(float(std_all * np.sqrt(252))*100, 2),
            'holding': overall_holding,
            'stoploss_count': int(sl_count),
        },
    }
    print(f"{pname}: {df['date'].iloc[0].date()}~{df['date'].iloc[-1].date()}, {len(df)}天, {len(years)}年, 止损{sl_count}次")
    for sname, info in avail_info.items():
        if info['pct'] < 100:
            print(f"  {sname}: {info['first']}~{info['last']} ({info['pct']}%可用)")

# 导出JSON
with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_stoploss_yearly.json', 'w', encoding='utf-8') as f:
    json.dump(all_period_results, f, ensure_ascii=False, indent=2)
print("\n数据已保存到 v14_stoploss_yearly.json")

# ===== 5. 生成HTML =====
def gen_holding_cell(holding):
    colors = {
        '上证50': '#e74c3c', '创业板50': '#f39c12', '纳斯达克100': '#3498db',
        '沪深300': '#2ecc71', '中证500': '#9b59b6', '中证1000': '#1abc9c',
        '标普500': '#e67e22', '科创50': '#d35400', '国债': '#95a5a6', '空仓': '#bdc3c7',
    }
    parts = []
    for name in ['上证50','创业板50','纳斯达克100','沪深300','中证500','中证1000','标普500','科创50','国债','空仓']:
        if name in holding:
            pct = holding[name]['pct']
            if pct > 0:
                color = colors.get(name, '#888')
                label = name if pct >= 5 else ''
                parts.append(f'<span class="hb" style="width:{pct}%;background:{color}"><span class="hb-l">{label}</span></span>')
    return f'<div class="hbar">{"".join(parts)}</div>'

html_parts = []
html_parts.append('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>V14-止损策略(个持仓5%止损/4%回升) 逐年统计</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Microsoft YaHei','Segoe UI',sans-serif; background:#f5f6fa; color:#333; padding:20px; }
h1 { text-align:center; font-size:22px; margin-bottom:5px; }
.sub { text-align:center; font-size:13px; color:#666; margin-bottom:20px; }
.note { background:#e3f2fd; border:1px solid #90caf9; border-radius:6px; padding:10px 16px; margin-bottom:16px; font-size:13px; color:#1565c0; }
.period-card { background:#fff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.08); margin-bottom:24px; overflow:hidden; }
.period-header { background:linear-gradient(135deg,#e65100,#f57c00); color:#fff; padding:14px 20px; }
.period-header h2 { font-size:18px; margin-bottom:4px; }
.period-header .info { font-size:13px; opacity:0.9; }
.avail-box { background:#f8f9fa; padding:10px 16px; font-size:12px; color:#555; border-bottom:1px solid #eee; }
.avail-item { display:inline-block; margin-right:12px; }
.avail-partial { color:#e67e22; font-weight:600; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th { background:#f8f9fa; padding:10px 8px; text-align:center; font-weight:600; border-bottom:2px solid #e0e0e0; white-space:nowrap; }
td { padding:8px; text-align:center; border-bottom:1px solid #eee; }
tr:hover td { background:#fff8e1; }
.pos { color:#e74c3c; font-weight:600; }
.neg { color:#27ae60; font-weight:600; }
.mdd-val { color:#e74c3c; }
.sharpe-pos { color:#e74c3c; font-weight:600; }
.sharpe-neg { color:#27ae60; }
.hbar { display:flex; width:200px; height:20px; border-radius:4px; overflow:hidden; margin:0 auto; }
.hb { display:inline-flex; align-items:center; justify-content:center; height:100%; font-size:10px; color:#fff; white-space:nowrap; overflow:hidden; }
.hb-l { font-size:9px; }
.overall-row { background:#fffde7 !important; font-weight:600; }
.overall-row td { border-top:2px solid #f0e68c; border-bottom:2px solid #f0e68c; }
.legend { display:flex; gap:12px; justify-content:center; flex-wrap:wrap; margin-bottom:16px; }
.legend-item { display:flex; align-items:center; gap:4px; font-size:12px; }
.legend-color { width:14px; height:14px; border-radius:3px; }
.summary-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:24px; }
.summary-card { background:#fff; border-radius:8px; padding:14px; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.06); }
.summary-card h3 { font-size:14px; color:#666; margin-bottom:8px; }
.summary-card .val { font-size:20px; font-weight:700; }
.summary-card .sub-val { font-size:12px; color:#888; margin-top:4px; }
.sl-badge { display:inline-block; background:#ffe0b2; color:#e65100; border-radius:10px; padding:1px 8px; font-size:11px; margin-left:4px; }
.compare-box { background:#fff; border-radius:8px; padding:16px 20px; margin-bottom:20px; box-shadow:0 2px 6px rgba(0,0,0,0.06); }
.compare-box h3 { font-size:15px; margin-bottom:10px; color:#333; }
.compare-table { width:100%; border-collapse:collapse; font-size:13px; }
.compare-table th { background:#f0f0f0; padding:8px; text-align:center; }
.compare-table td { padding:8px; text-align:center; border-bottom:1px solid #eee; }
</style>
</head>
<body>
<h1>V14-止损策略 (个持仓5%止损/4%回升) 逐年统计</h1>
<div class="sub">MA20轮动 · 个持仓从买入价下跌5%止损→国债 · bf改变或回升至-4%再买入 · T日收盘信号→T+1开盘执行 · 手续费0.02%</div>
<div class="note">
<b>机制说明：</b>与原V14(组合净值回撤5%/4%熔断)不同，本策略采用<b>个持仓止损</b>机制：<br>
1. 买入股票后，如果该股票收盘价相对买入价下跌≥5%，次日开盘清仓转入国债<br>
2. 止损后持续持国债，直到以下任一条件满足再买入：<br>
&nbsp;&nbsp;&nbsp;a) <b>买入因子改变</b>：bf排行最高的标的变为其他股票 → 买入新标的<br>
&nbsp;&nbsp;&nbsp;b) <b>回升解除</b>：原标的收盘价回升至买入价亏损4%以内 → 买回原标的<br>
3. 所有时段均用全部8股+国债（动态join），各标的有数据时参与选股
</div>
''')

# 图例
html_parts.append('<div class="legend">')
legend_colors = {
    '上证50': '#e74c3c', '创业板50': '#f39c12', '纳斯达克100': '#3498db',
    '沪深300': '#2ecc71', '中证500': '#9b59b6', '中证1000': '#1abc9c',
    '标普500': '#e67e22', '科创50': '#d35400', '国债': '#95a5a6', '空仓': '#bdc3c7',
}
for name, color in legend_colors.items():
    html_parts.append(f'<div class="legend-item"><div class="legend-color" style="background:{color}"></div>{name}</div>')
html_parts.append('</div>')

# 各时段汇总卡片
html_parts.append('<div class="summary-grid">')
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = all_period_results[pname]
    o = r['overall']
    ret_class = 'pos' if o['total_ret'] >= 0 else 'neg'
    sharpe_class = 'sharpe-pos' if o['sharpe'] >= 0 else 'sharpe-neg'
    html_parts.append(f'''<div class="summary-card">
    <h3>{pname}</h3>
    <div class="val {ret_class}">{o["total_ret"]:+.2f}%</div>
    <div class="sub-val">年化 {o["ann_ret"]:+.2f}% · 夏普 {o["sharpe"]:.2f}</div>
    <div class="sub-val">回撤 {o["mdd"]:.2f}% · 波动 {o["ann_vol"]:.2f}%</div>
    <div class="sub-val">{r["n_days"]}天 · 止损{o["stoploss_count"]}次</div>
    </div>''')
html_parts.append('</div>')

# 各时段表格
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = all_period_results[pname]
    avail_parts = []
    for sname in ['上证50','创业板50','纳斯达克100','沪深300','中证500','中证1000','标普500','科创50']:
        info = r['avail_info'][sname]
        if info['pct'] < 100:
            avail_parts.append(f'<span class="avail-item">{sname}: <span class="avail-partial">{info["first"]}起({info["pct"]}%)</span></span>')
        else:
            avail_parts.append(f'<span class="avail-item">{sname}: 全程</span>')
    avail_html = ' '.join(avail_parts)

    html_parts.append(f'''<div class="period-card">
    <div class="period-header">
        <h2>{pname}</h2>
        <div class="info">{r["start"]} ~ {r["end"]} · {r["n_days"]}天 · 标的池: 8股+国债（动态join） · 止损{r["overall"]["stoploss_count"]}次</div>
    </div>
    <div class="avail-box"><b>标的可用情况:</b> {avail_html}</div>
    <table>
    <thead><tr>
        <th>年份</th><th>交易日</th><th>年度收益</th><th>夏普率</th><th>最大回撤</th><th>年化波动</th><th>切换</th><th>止损</th><th>持仓占比</th>
    </tr></thead><tbody>''')

    for yd in r['yearly']:
        ret_cls = 'pos' if yd['ret'] >= 0 else 'neg'
        sharpe_cls = 'sharpe-pos' if yd['sharpe'] >= 0 else 'sharpe-neg'
        holding_html = gen_holding_cell(yd['holding'])
        sl_badge = f'<span class="sl-badge">{yd["stoploss_count"]}</span>' if yd['stoploss_count'] > 0 else '0'
        html_parts.append(f'''<tr>
            <td>{yd["year"]}</td>
            <td>{yd["n_days"]}</td>
            <td class="{ret_cls}">{yd["ret"]:+.2f}%</td>
            <td class="{sharpe_cls}">{yd["sharpe"]:.2f}</td>
            <td class="mdd-val">{yd["mdd"]:.2f}%</td>
            <td>{yd["ann_vol"]:.2f}%</td>
            <td>{yd["switches"]}</td>
            <td>{sl_badge}</td>
            <td>{holding_html}</td>
        </tr>''')

    o = r['overall']
    ret_cls = 'pos' if o['total_ret'] >= 0 else 'neg'
    sharpe_cls = 'sharpe-pos' if o['sharpe'] >= 0 else 'sharpe-neg'
    holding_html = gen_holding_cell(o['holding'])
    html_parts.append(f'''<tr class="overall-row">
        <td>整体</td>
        <td>{r["n_days"]}</td>
        <td class="{ret_cls}">{o["total_ret"]:+.2f}%</td>
        <td class="{sharpe_cls}">{o["sharpe"]:.2f}</td>
        <td class="mdd-val">{o["mdd"]:.2f}%</td>
        <td>{o["ann_vol"]:.2f}%</td>
        <td>-</td>
        <td>{o["stoploss_count"]}</td>
        <td>{holding_html}</td>
    </tr>''')

    html_parts.append('</tbody></table></div>')

html_parts.append('''
<div style="text-align:center;font-size:12px;color:#999;margin-top:20px;">
收益口径: open-to-open · 夏普率: 年化(√252) · 最大回撤: 年内峰值回撤 · 持仓占比: 按交易日天数统计<br>
止损机制: 个持仓从买入价下跌≥5%→国债；bf排行改变或回升至亏损≤4%→再买入 · 动态标的池: 各标的独立计算MA20/bf后left join
</div>
</body></html>''')

html = '\n'.join(html_parts)
out_path = 'C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_stoploss_yearly.html'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nHTML报告已生成: {out_path}")
