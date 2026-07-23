# -*- coding: utf-8 -*-
"""V14策略中连续持仓国债>10天的时段分析"""
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

# ===== 3. 策略信号 =====
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

# ===== 4. 应用5%/4%熔断 =====
print("应用熔断...")
raw_pos = df['raw_position'].values
raw_dd = df['raw_dd'].values
n = len(df)
in_cb = False
final_position = []
cb_events = []  # 记录熔断事件
for i in range(n):
    sig = int(raw_pos[i])
    dd = raw_dd[i]
    if not in_cb:
        if dd < -DD_TRIGGER and sig != BOND:
            in_cb = True
            cb_events.append({'trigger_idx': i, 'trigger_date': df['date'].iloc[i], 'trigger_dd': dd})
            final_position.append(BOND)
        else:
            final_position.append(sig)
    else:
        if dd > -DD_RELEASE:
            in_cb = False
            if cb_events:
                cb_events[-1]['release_idx'] = i
                cb_events[-1]['release_date'] = df['date'].iloc[i]
                cb_events[-1]['release_dd'] = dd
            final_position.append(sig)
        else:
            final_position.append(BOND)

final_position = np.array(final_position)
df['final_position'] = final_position

# ===== 5. 计算V14收益 =====
prev_pos = np.concatenate([[final_position[0]], final_position[:-1]])
v14_rets = np.zeros(n)
for i in range(n):
    pos = int(final_position[i])
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
    v14_rets[i] = (1 + gross) * (1 - cost) - 1

df['v14_ret'] = v14_rets
df['v14_nav'] = (1 + df['v14_ret']).cumprod()

# ===== 6. 找连续持仓国债>10天的时段 =====
print("\n分析连续持仓国债时段...")
periods = []
i = 0
while i < n:
    if int(final_position[i]) == BOND:
        start_i = i
        while i < n and int(final_position[i]) == BOND:
            i += 1
        end_i = i - 1
        length = end_i - start_i + 1
        if length > 10:
            # 判断原因
            start_date = df['date'].iloc[start_i]
            end_date = df['date'].iloc[end_i]

            # 看start_i的信号是什么（被熔断覆盖的信号）
            start_signal = int(df['raw_signal'].iloc[start_i - 1]) if start_i > 0 else 0

            # 检查是否处于熔断中
            in_circuit = False
            for ev in cb_events:
                trig = ev['trigger_idx']
                rel = ev.get('release_idx', n)
                if trig <= start_i < rel:
                    in_circuit = True
                    break

            # 看国债期间各日的信号
            bond_signal_counts = {}
            for j in range(start_i, end_i + 1):
                sig = int(df['raw_signal'].iloc[j])
                bond_signal_counts[all_names[sig]] = bond_signal_counts.get(all_names[sig], 0) + 1

            # 国债期间V14收益
            period_ret = 1.0
            for j in range(start_i, end_i + 1):
                period_ret *= (1 + v14_rets[j])
            period_ret -= 1

            # 国债期间V8回撤范围
            v8_dd_start = float(df['raw_dd'].iloc[start_i])
            v8_dd_end = float(df['raw_dd'].iloc[end_i])
            v8_dd_min = float(df['raw_dd'].iloc[start_i:end_i+1].min())

            # 前一个持仓标的
            prev_holding = all_names[int(final_position[start_i - 1])] if start_i > 0 else '空仓(起始)'

            # 后一个持仓标的
            next_holding = all_names[int(final_position[end_i + 1])] if end_i + 1 < n else '仍持国债(至今)'

            periods.append({
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'days': length,
                'prev_holding': prev_holding,
                'next_holding': next_holding,
                'in_circuit': in_circuit,
                'start_signal': all_names[start_signal] if start_i > 0 else '---',
                'v8_dd_start': v8_dd_start,
                'v8_dd_end': v8_dd_end,
                'v8_dd_min': v8_dd_min,
                'period_ret': period_ret,
                'signal_dist': bond_signal_counts,
            })
    else:
        i += 1

print(f"共找到 {len(periods)} 个连续持仓国债>10天的时段")

# ===== 7. 输出结果 =====
# 控制台打印
print(f"\n{'='*100}")
print(f"V14策略 — 连续持仓国债>10天时段（共{len(periods)}个）")
print(f"{'='*100}")
print(f"{'#':>3} {'起止日期':25s} {'天数':>4} {'前一持仓':12s} {'后一持仓':12s} {'熔断':4s} {'V8回撤起':>8s} {'V8回撤止':>8s} {'V8最深':>8s} {'期间收益':>8s}")
print(f"{'-'*100}")
for idx, p in enumerate(periods):
    cb = '⚡是' if p['in_circuit'] else '否'
    print(f"{idx+1:>3} {p['start_date']}~{p['end_date']:>10s} {p['days']:>4} {p['prev_holding']:12s} {p['next_holding']:12s} {cb:4s} {p['v8_dd_start']*100:+7.2f}% {p['v8_dd_end']*100:+7.2f}% {p['v8_dd_min']*100:+7.2f}% {p['period_ret']*100:+7.2f}%")

# 按天数排序
periods_sorted = sorted(periods, key=lambda x: x['days'], reverse=True)
print(f"\n{'='*100}")
print(f"按天数降序排列")
print(f"{'='*100}")
for idx, p in enumerate(periods_sorted):
    cb = '⚡熔断' if p['in_circuit'] else '全bf<0'
    sig_str = ', '.join(f"{k}({v}天)" for k, v in sorted(p['signal_dist'].items(), key=lambda x: -x[1]))
    print(f"{idx+1:>3} {p['start_date']}~{p['end_date']:>10s} {p['days']:>4}天 {p['prev_holding']:>10s}→{p['next_holding']:>10s} [{cb}] V8最深={p['v8_dd_min']*100:+.2f}% 收益={p['period_ret']*100:+.2f}%")
    print(f"     期间信号分布: {sig_str}")

# ===== 8. 生成HTML =====
print("\n生成HTML报告...")

colors = {
    '上证50': '#e74c3c', '创业板50': '#f39c12', '纳斯达克100': '#3498db',
    '沪深300': '#2ecc71', '中证500': '#9b59b6', '中证1000': '#1abc9c',
    '标普500': '#e67e22', '科创50': '#d35400', '国债': '#95a5a6', '空仓': '#bdc3c7',
    '空仓(起始)': '#bdc3c7', '仍持国债(至今)': '#95a5a6',
}

rows_html = []
for idx, p in enumerate(periods_sorted):
    cb_badge = '<span class="cb-tag">⚡熔断</span>' if p['in_circuit'] else '<span class="nb-tag">全bf&lt;0</span>'
    prev_c = colors.get(p['prev_holding'], '#888')
    next_c = colors.get(p['next_holding'], '#888')
    ret_cls = 'pos' if p['period_ret'] >= 0 else 'neg'
    dd_cls = 'dd-danger' if p['v8_dd_min'] < -DD_TRIGGER else ('dd-warn' if p['v8_dd_min'] < -DD_RELEASE else 'dd-ok')

    sig_chips = []
    for sname, cnt in sorted(p['signal_dist'].items(), key=lambda x: -x[1]):
        sc = colors.get(sname, '#888')
        sig_chips.append(f'<span class="sig-chip" style="background:{sc}">{sname} {cnt}</span>')

    rows_html.append(f'''<tr>
        <td class="num">{idx+1}</td>
        <td class="date-col">{p['start_date']}<br>~ {p['end_date']}</td>
        <td class="days">{p['days']}</td>
        <td><span class="tag" style="background:{prev_c}">{p['prev_holding']}</span></td>
        <td><span class="tag" style="background:{next_c}">{p['next_holding']}</span></td>
        <td>{cb_badge}</td>
        <td class="{dd_cls}">{p['v8_dd_min']*100:+.2f}%</td>
        <td class="dd-sub">{p['v8_dd_start']*100:+.2f}% → {p['v8_dd_end']*100:+.2f}%</td>
        <td class="{ret_cls}">{p['period_ret']*100:+.2f}%</td>
        <td class="sig-dist">{''.join(sig_chips)}</td>
    </tr>''')

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14策略 — 连续持仓国债>10天时段</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Microsoft YaHei','Segoe UI',sans-serif; background:#f5f6fa; color:#333; padding:16px; max-width:1200px; margin:0 auto; }}
h1 {{ font-size:22px; margin-bottom:4px; }}
.sub {{ font-size:12px; color:#888; margin-bottom:16px; }}
.summary {{ display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap; }}
.s-card {{ background:#fff; border-radius:8px; padding:10px 16px; box-shadow:0 1px 4px rgba(0,0,0,0.06); }}
.s-card .label {{ font-size:11px; color:#999; }}
.s-card .val {{ font-size:18px; font-weight:700; }}
.card {{ background:#fff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.08); overflow:hidden; overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; min-width:900px; }}
th {{ background:#f8f9fa; padding:10px 8px; text-align:center; font-weight:600; border-bottom:2px solid #e0e0e0; white-space:nowrap; }}
td {{ padding:8px; text-align:center; border-bottom:1px solid #eee; }}
tr:hover td {{ background:#f8f9ff; }}
.num {{ font-weight:600; color:#666; }}
.date-col {{ white-space:nowrap; font-weight:500; line-height:1.5; }}
.days {{ font-size:14px; font-weight:700; color:#e67e22; }}
.tag {{ display:inline-block; padding:2px 8px; border-radius:4px; color:#fff; font-size:11px; white-space:nowrap; }}
.cb-tag {{ background:#e74c3c; color:#fff; padding:2px 6px; border-radius:3px; font-size:10px; font-weight:600; }}
.nb-tag {{ background:#95a5a6; color:#fff; padding:2px 6px; border-radius:3px; font-size:10px; }}
.pos {{ color:#e74c3c; font-weight:600; }}
.neg {{ color:#27ae60; font-weight:600; }}
.dd-ok {{ color:#27ae60; }}
.dd-warn {{ color:#f39c12; }}
.dd-danger {{ color:#e74c3c; font-weight:600; }}
.dd-sub {{ font-size:11px; color:#999; }}
.sig-dist {{ text-align:left; }}
.sig-chip {{ display:inline-block; padding:1px 5px; border-radius:3px; color:#fff; font-size:10px; margin:1px; white-space:nowrap; }}
.rules {{ margin-top:16px; padding:12px 16px; background:#fff; border-radius:8px; font-size:11px; color:#888; line-height:1.6; }}
</style>
</head>
<body>
<h1>V14策略 — 连续持仓国债&gt;10天时段</h1>
<div class="sub">决策日期=T日 · 决策bf=(T-1收盘/T-1的MA20)-1 · T日开盘执行 · 5%熔断/4%解除 · 按天数降序排列</div>

<div class="summary">
    <div class="s-card"><div class="label">总时段数</div><div class="val">{len(periods)}</div></div>
    <div class="s-card"><div class="label">最长天数</div><div class="val">{max(p['days'] for p in periods)}</div></div>
    <div class="s-card"><div class="label">熔断触发</div><div class="val">{sum(1 for p in periods if p['in_circuit'])}</div></div>
    <div class="s-card"><div class="label">全bf&lt;0</div><div class="val">{sum(1 for p in periods if not p['in_circuit'])}</div></div>
    <div class="s-card"><div class="label">国债总天数</div><div class="val">{sum(p['days'] for p in periods)}</div></div>
</div>

<div class="card">
<table>
<thead><tr>
    <th>#</th><th>起止日期</th><th>天数</th><th>前一持仓</th><th>后一持仓</th><th>原因</th><th>V8最深回撤</th><th>V8回撤区间</th><th>期间收益</th><th>期间信号分布</th>
</tr></thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</div>

<div class="rules">
    <b>说明：</b>连续持仓国债>10天的时段，按天数降序排列。<br>
    <b>原因：</b>⚡熔断 = V8基线回撤>5%触发熔断转国债（至回撤恢复<4%解除）；全bf&lt;0 = 所有标的均跌破MA20，信号自动选国债。<br>
    <b>期间信号分布：</b>国债持仓期间，每日基于T-1收盘计算的信号标的分布（即使因熔断未执行，信号仍计算）。<br>
    <b>期间收益：</b>该时段持有国债的累计收益率（含国债收益和手续费）。
</div>
</body></html>'''

html_path = os.path.join(BASE_DIR, 'v14_bond_periods.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"HTML报告已生成: {html_path}")

# 保存JSON
json_path = os.path.join(BASE_DIR, 'v14_bond_periods.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(periods_sorted, f, ensure_ascii=False, indent=2, default=str)
print(f"JSON数据已保存: {json_path}")
