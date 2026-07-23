# -*- coding: utf-8 -*-
"""
V14策略每日收盘信号生成器
=========================
运行方式：
  1. 自动模式：先运行 fetch_data.py 从akshare获取最新数据，再运行此脚本
  2. 手动模式：从同花顺导出数据到桌面，直接运行此脚本（自动检测）

输出：控制台摘要 + HTML报告（v14_daily_signal.html）

策略规则：
  - 标的池：8股(上证50/创业板50/纳斯达克100/沪深300/中证500/中证1000/标普500/科创50) + 国债
  - 选股：每日收盘后计算各标的 bf = close/MA20 - 1，选bf最高且站上MA20(ratio>=1)的标的
  - 熔断：V8基线(无熔断)净值从高点回撤>5%时转国债，回撤恢复至<4%时解除
  - 执行：T日收盘信号 → T+1开盘执行
  - 手续费：0.02%
"""
import pandas as pd
import numpy as np
import json, os
from datetime import datetime

FEE = 0.0002
DD_TRIGGER = 0.05
DD_RELEASE = 0.04

STOCK_ALL = [1, 2, 3, 4, 5, 6, 7, 8]
BOND = 9
names = {1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}
all_names = {0:'空仓', 1:'上证50',2:'创业板50',3:'纳斯达克100',4:'沪深300',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债'}

colors = {
    '上证50': '#e74c3c', '创业板50': '#f39c12', '纳斯达克100': '#3498db',
    '沪深300': '#2ecc71', '中证500': '#9b59b6', '中证1000': '#1abc9c',
    '标普500': '#e67e22', '科创50': '#d35400', '国债': '#95a5a6', '空仓': '#bdc3c7',
}

def find_csv(sid, name):
    """查找fetch_data.py生成的CSV数据文件"""
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', f'{sid}_{name}.csv')
    return csv_path if os.path.exists(csv_path) else None

def find_ths_file(name):
    """查找同花顺导出的数据文件（后备）"""
    for p in [f'C:/Users/wbl/Desktop/同花顺历史数据/{name}.xlsx',
              f'C:/Users/wbl/Desktop/{name}.xlsx']:
        if os.path.exists(p):
            return p
    return None

# ===== 1. 读取数据 =====
print("读取数据...")
dfs = {}
for i in STOCK_ALL + [BOND]:
    name = names[i]
    csv_path = find_csv(i, name)
    if csv_path:
        # 从CSV文件读取（fetch_data.py生成）
        d = pd.read_csv(csv_path, parse_dates=['date'])
        d = d[['date', 'open', 'close']].rename(columns={'open': f'open_{i}', 'close': f'close_{i}'})
        d = d.sort_values('date').reset_index(drop=True)
        source = 'akshare'
    else:
        # 后备：从同花顺文件读取
        ths_path = find_ths_file(name)
        if ths_path is None:
            raise FileNotFoundError(f"未找到 {name} 数据，请先运行 fetch_data.py 或从同花顺导出数据")
        d = pd.read_csv(ths_path, sep='\t', encoding='gbk')
        d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
        d = d[['date', '开盘', '收盘']].rename(columns={'开盘': f'open_{i}', '收盘': f'close_{i}'})
        for c in [f'open_{i}', f'close_{i}']:
            d[c] = pd.to_numeric(d[c], errors='coerce')
        d = d.dropna(subset=[f'open_{i}', f'close_{i}']).sort_values('date').reset_index(drop=True)
        source = '同花顺'

    if i != BOND:
        d[f'ma20_{i}'] = d[f'close_{i}'].rolling(20).mean()
        d[f'bf_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}'] - 1
        d[f'ratio_{i}'] = d[f'close_{i}'] / d[f'ma20_{i}']
    dfs[i] = d
    print(f"  {names[i]}[{source}]: {d['date'].iloc[0].date()} ~ {d['date'].iloc[-1].date()}, {len(d)}条")

last_date = dfs[BOND]['date'].max()
print(f"\n数据最新日期: {last_date.date()}")

# ===== 2. 构建合并数据（近20年，动态join）=====
start_date = last_date - pd.DateOffset(years=20)
df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
df = df.sort_values('date').reset_index(drop=True)
df = df[(df['date'] >= start_date) & (df['date'] <= last_date)].reset_index(drop=True)

for i in STOCK_ALL:
    cols = ['date', f'open_{i}', f'close_{i}', f'ma20_{i}', f'bf_{i}', f'ratio_{i}']
    df = pd.merge(df, dfs[i][cols], on='date', how='left')

all_ids = STOCK_ALL + [BOND]

# 计算收益率（open-to-open）
for i in all_ids:
    df[f'open_{i}_next'] = df[f'open_{i}'].shift(-1)
last_idx = df.index[-1]
for i in all_ids:
    df[f'ret_{i}'] = np.nan
    mask = df[f'open_{i}_next'].notna() & df[f'open_{i}'].notna()
    df.loc[mask, f'ret_{i}'] = df.loc[mask, f'open_{i}_next'] / df.loc[mask, f'open_{i}'] - 1
    if pd.notna(df.loc[last_idx, f'open_{i}']) and pd.notna(df.loc[last_idx, f'close_{i}']):
        df.loc[last_idx, f'ret_{i}'] = df.loc[last_idx, f'close_{i}'] / df.loc[last_idx, f'open_{i}'] - 1

# ===== 3. 动态选股信号 =====
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
raw_pos = df['raw_position'].values
raw_dd = df['raw_dd'].values
n = len(df)
in_cb = False
final_position = []
cb_events = []

for i in range(n):
    sig = int(raw_pos[i])
    dd = raw_dd[i]
    if not in_cb:
        if dd < -DD_TRIGGER and sig != BOND:
            in_cb = True
            cb_events.append({
                'idx': i,
                'date': df['date'].iloc[i],
                'event': 'TRIGGER',
                'dd': float(dd),
                'from': sig, 'to': BOND,
            })
            final_position.append(BOND)
        else:
            final_position.append(sig)
    else:
        if dd > -DD_RELEASE:
            in_cb = False
            cb_events.append({
                'idx': i,
                'date': df['date'].iloc[i],
                'event': 'RELEASE',
                'dd': float(dd),
                'from': BOND, 'to': sig,
            })
            final_position.append(sig)
        else:
            final_position.append(BOND)

df['final_position'] = final_position

# V14收益率
prev_pos_arr = np.concatenate([[final_position[0]], final_position[:-1]])
v14_rets = np.zeros(n)
for i in range(n):
    p = int(final_position[i])
    if p == 0:
        gross = 0.0
    else:
        ret_val = df[f'ret_{p}'].iloc[i]
        gross = ret_val if pd.notna(ret_val) else 0.0
    cost = 0.0
    if int(prev_pos_arr[i]) != p:
        if int(prev_pos_arr[i]) in all_ids: cost += FEE
        if p in all_ids: cost += FEE
    v14_rets[i] = (1 + gross) * (1 - cost) - 1

df['v14_ret'] = v14_rets
df['v14_nav'] = (1 + df['v14_ret']).cumprod()
df['v14_cummax'] = df['v14_nav'].cummax()
df['v14_dd'] = df['v14_nav'] / df['v14_cummax'] - 1

# ===== 5. 提取当日状态 =====
today_idx = df.index[-1]
today_date = df['date'].iloc[today_idx]
today_signal = int(df['raw_signal'].iloc[today_idx])
today_position = int(df['final_position'].iloc[today_idx])
yesterday_position = int(df['final_position'].iloc[today_idx - 1]) if today_idx > 0 else 0

cb_active = in_cb
v8_nav = float(df['raw_strat_nav'].iloc[today_idx])
v8_peak = float(df['raw_cummax'].iloc[today_idx])
v8_dd = float(df['raw_dd'].iloc[today_idx])
v14_nav = float(df['v14_nav'].iloc[today_idx])
v14_dd = float(df['v14_dd'].iloc[today_idx])
v14_peak = float(df['v14_cummax'].iloc[today_idx])

# 判断下一交易日操作
if cb_active:
    if v8_dd > -DD_RELEASE:
        next_position = today_signal
        if today_signal != BOND:
            action_text = f"熔断解除！下一交易日开盘买入「{names[today_signal]}」"
            action_type = "release_buy"
        else:
            action_text = "熔断解除，但无标的站上MA20，继续持国债"
            action_type = "release_hold_bond"
    else:
        next_position = BOND
        gap_to_release = abs(v8_dd) - DD_RELEASE
        action_text = f"熔断中，继续持国债（V8回撤{v8_dd*100:.2f}%，距解除还需恢复{gap_to_release*100:.2f}%）"
        action_type = "cb_hold"
else:
    next_position = today_signal
    if today_position == today_signal:
        action_text = f"继续持有「{names[today_signal]}」"
        action_type = "hold"
    elif today_position == BOND and today_signal != BOND:
        action_text = f"下一交易日开盘买入「{names[today_signal]}」"
        action_type = "buy"
    elif today_position != BOND and today_signal == BOND:
        action_text = f"下一交易日开盘卖出「{names[today_position]}」，转入国债"
        action_type = "sell_to_bond"
    else:
        action_text = f"下一交易日开盘卖出「{names[today_position]}」，买入「{names[today_signal]}」"
        action_type = "switch"

# ===== 6. bf排名 =====
bf_ranking = []
for i in STOCK_ALL:
    bf_val = df[f'bf_{i}'].iloc[today_idx]
    ratio_val = df[f'ratio_{i}'].iloc[today_idx]
    close_val = df[f'close_{i}'].iloc[today_idx]
    ma20_val = df[f'ma20_{i}'].iloc[today_idx]
    open_val = df[f'open_{i}'].iloc[today_idx]
    if pd.notna(bf_val):
        daily_ret = (close_val / open_val - 1) if pd.notna(open_val) and open_val > 0 else None
        bf_ranking.append({
            'id': i, 'name': names[i],
            'open': float(open_val) if pd.notna(open_val) else None,
            'close': float(close_val),
            'ma20': float(ma20_val),
            'ratio': float(ratio_val),
            'bf': float(bf_val),
            'daily_ret': float(daily_ret) if daily_ret is not None else None,
            'above': ratio_val >= 1,
            'available': True,
        })
    else:
        bf_ranking.append({
            'id': i, 'name': names[i],
            'open': None, 'close': None, 'ma20': None, 'ratio': None, 'bf': None,
            'daily_ret': None, 'above': False, 'available': False,
        })
bf_ranking_available = [x for x in bf_ranking if x['available']]
bf_ranking_available.sort(key=lambda x: x['bf'], reverse=True)

# ===== 7. 近期操作记录（最近30天）=====
recent_ops = []
for i in range(max(0, today_idx - 29), today_idx + 1):
    pos = int(df['final_position'].iloc[i])
    prev_p = int(df['final_position'].iloc[i-1]) if i > 0 else 0
    signal = int(df['raw_signal'].iloc[i])
    date_str = df['date'].iloc[i].strftime('%Y-%m-%d')
    weekday = df['date'].iloc[i].dayofweek  # 0=Monday
    
    # 决策依据bf（当日收盘的bf，与信号同日）
    if signal in STOCK_ALL:
        signal_bf = df[f'bf_{signal}'].iloc[i]
        signal_bf = float(signal_bf) if pd.notna(signal_bf) else None
    else:
        signal_bf = None
    
    v8_dd_val = float(df['raw_dd'].iloc[i])
    v14_ret_val = float(df['v14_ret'].iloc[i])
    v14_nav_val = float(df['v14_nav'].iloc[i])
    
    # 检查当日是否熔断
    was_cb = (pos == BOND and signal != BOND)
    
    recent_ops.append({
        'date': date_str,
        'weekday': ['一','二','三','四','五','六','日'][weekday],
        'position': pos,
        'position_name': all_names[pos],
        'prev_position': prev_p,
        'signal': signal,
        'signal_name': all_names[signal],
        'signal_bf': signal_bf,
        'v8_dd': v8_dd_val,
        'v14_ret': v14_ret_val,
        'v14_nav': v14_nav_val,
        'changed': pos != prev_p,
        'was_cb': was_cb,
    })

# ===== 8. 近期熔断事件 =====
recent_cb_events = cb_events[-5:] if len(cb_events) >= 5 else cb_events

# ===== 9. 策略整体表现 =====
total_ret = float(df['v14_nav'].iloc[-1] - 1)
ann_ret = (1 + total_ret) ** (252 / n) - 1
mdd_val = float(df['v14_dd'].min())
std_all = float(df['v14_ret'].std())
sharpe_all = np.sqrt(252) * df['v14_ret'].mean() / std_all if std_all > 0 else 0
ann_vol = std_all * np.sqrt(252)

# 持仓统计
holding_stats = {}
for a in STOCK_ALL + [BOND, 0]:
    cnt = int((df['final_position'] == a).sum())
    if cnt > 0:
        holding_stats[all_names[a]] = {'days': cnt, 'pct': round(cnt / n * 100, 2)}

# ===== 10. V14净值走势数据（近1年）=====
n_chart = min(252, n)
chart_data = []
for i in range(today_idx - n_chart + 1, today_idx + 1):
    chart_data.append({
        'date': df['date'].iloc[i].strftime('%m-%d'),
        'v14_nav': float(df['v14_nav'].iloc[i]),
        'v8_nav': float(df['raw_strat_nav'].iloc[i]),
        'v8_dd': float(df['raw_dd'].iloc[i]),
        'position': int(df['final_position'].iloc[i]),
    })

# ===== 11. 控制台输出 =====
print(f"\n{'='*70}")
print(f"  V14策略每日信号 — {today_date.strftime('%Y-%m-%d')} 收盘")
print(f"{'='*70}")

action_emoji = {'hold': '✅', 'buy': '🟢', 'sell_to_bond': '🔴', 'switch': '🟡', 'cb_hold': '⚡', 'release_buy': '🟢', 'release_hold_bond': '⚡'}
print(f"\n  {action_emoji.get(action_type, '▶')} {action_text}")
print(f"\n  {'─'*50}")
print(f"  当前持仓: {all_names[today_position]}")
print(f"  下一交易日持仓: {all_names[next_position]}")
print(f"  {'─'*50}")
print(f"\n  【熔断状态】{'⚡ 熔断中' if cb_active else '✓ 正常'}")
print(f"    V8基线净值: {v8_nav:.4f}")
print(f"    V8峰值净值: {v8_peak:.4f}")
print(f"    V8回撤: {v8_dd*100:.2f}%  (触发:-5.00% / 解除:-4.00%)")
print(f"    V14策略净值: {v14_nav:.4f}  (回撤: {v14_dd*100:.2f}%)")

print(f"\n  【bf排名】(收盘价/MA20 - 1)")
print(f"    {'排名':>4s}  {'标的':<10s}  {'收盘':>10s}  {'MA20':>10s}  {'比值':>8s}  {'bf':>8s}  {'涨跌':>7s}  状态")
print(f"    {'─'*75}")
for rank, item in enumerate(bf_ranking_available, 1):
    marker = ' ◀ 选中' if item['id'] == today_signal else ''
    above_str = '↑ 站上' if item['above'] else '↓ 跌破'
    daily_str = f"{item['daily_ret']*100:+.2f}%" if item['daily_ret'] is not None else '  ---  '
    print(f"    {rank:>4d}  {item['name']:<10s}  {item['close']:>10.2f}  {item['ma20']:>10.2f}  {item['ratio']:>8.4f}  {item['bf']:>+8.4f}  {daily_str}  {above_str}{marker}")

# 不可用的标的
for item in bf_ranking:
    if not item['available']:
        print(f"    {'--':>4s}  {item['name']:<10s}  （当日无数据）")

print(f"\n  【近10日操作】")
print(f"    {'日期':>12s}  {'持仓':<10s}  {'信号':<10s}  {'决策bf':>8s}  {'V8回撤':>8s}  {'V14收益':>8s}  {'V14净值':>8s}  事件")
print(f"    {'─'*90}")
for op in recent_ops[-10:]:
    change_mark = '→' if op['changed'] else ' '
    bf_str = f"{op['signal_bf']:+.4f}" if op['signal_bf'] is not None else '  ---   '
    cb_str = '⚡熔断' if op['was_cb'] else ''
    print(f"    {op['date']:>12s}  {op['position_name']:<10s}  {op['signal_name']:<10s}  {bf_str}  {op['v8_dd']*100:>+7.2f}%  {op['v14_ret']*100:>+7.2f}%  {op['v14_nav']:>8.4f}  {cb_str}")

if recent_cb_events:
    print(f"\n  【近期熔断事件】")
    for ev in recent_cb_events:
        ev_type = '触发' if ev['event'] == 'TRIGGER' else '解除'
        print(f"    {ev['date'].strftime('%Y-%m-%d')} {ev_type} V8回撤{ev['dd']*100:.2f}% {all_names[ev['from']]}→{all_names[ev['to']]}")

print(f"\n  【策略整体表现】(近20年)")
print(f"    总收益: {total_ret*100:+.2f}%  年化: {ann_ret*100:+.2f}%  夏普: {sharpe_all:.2f}  最大回撤: {mdd_val*100:.2f}%  波动: {ann_vol*100:.2f}%")
holding_str = ', '.join([f'{k} {v["pct"]}%' for k,v in holding_stats.items()])
print(f"    持仓占比: {holding_str}")
print(f"\n{'='*70}")

# ===== 12. 生成HTML报告 =====
print("\n生成HTML报告...")

# V14净值SVG迷你图
def gen_nav_chart():
    if not chart_data:
        return ''
    navs = [d['v14_nav'] for d in chart_data]
    dds = [d['v8_dd'] for d in chart_data]
    w, h = 680, 120
    nav_min, nav_max = min(navs), max(navs)
    dd_min, dd_max = min(min(dds), -0.06), max(max(dds), 0.01)
    
    def scale_nav(val):
        x = (val - nav_min) / (nav_max - nav_min) if nav_max > nav_min else 0.5
        return h - 10 - x * (h - 30)
    
    def scale_dd(val):
        x = (val - dd_min) / (dd_max - dd_min) if dd_max > dd_min else 0.5
        return 60 - x * 50
    
    n_pts = len(chart_data)
    nav_path = f'M {0},{scale_nav(navs[0]):.1f} '
    for j in range(1, n_pts):
        nav_path += f'L {j * w / (n_pts - 1):.1f},{scale_nav(navs[j]):.1f} '
    
    dd_path = f'M {0},{scale_dd(dds[0]):.1f} '
    for j in range(1, n_pts):
        dd_path += f'L {j * w / (n_pts - 1):.1f},{scale_dd(dds[j]):.1f} '
    
    # 触发线和解除线
    trigger_y = scale_dd(-DD_TRIGGER)
    release_y = scale_dd(-DD_RELEASE)
    
    return f'''<svg viewBox="0 0 {w} {h}" style="width:100%;max-width:680px;">
        <defs><linearGradient id="navGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#667eea" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="#667eea" stop-opacity="0"/>
        </linearGradient></defs>
        <path d="{nav_path} L {w},{h-10} L 0,{h-10} Z" fill="url(#navGrad)"/>
        <path d="{nav_path}" fill="none" stroke="#667eea" stroke-width="1.5"/>
        <line x1="0" y1="{trigger_y:.1f}" x2="{w}" y2="{trigger_y:.1f}" stroke="#e74c3c" stroke-width="1" stroke-dasharray="4,3" opacity="0.5"/>
        <line x1="0" y1="{release_y:.1f}" x2="{w}" y2="{release_y:.1f}" stroke="#f39c12" stroke-width="1" stroke-dasharray="4,3" opacity="0.5"/>
        <text x="5" y="{trigger_y-3:.1f}" fill="#e74c3c" font-size="9">-5%触发</text>
        <text x="5" y="{release_y-3:.1f}" fill="#f39c12" font-size="9">-4%解除</text>
        <text x="5" y="12" fill="#667eea" font-size="10" font-weight="600">V14净值</text>
    </svg>'''

# 构建持仓占比条
def gen_holding_bar():
    parts = []
    for name in ['上证50','创业板50','纳斯达克100','沪深300','中证500','中证1000','标普500','科创50','国债','空仓']:
        if name in holding_stats:
            pct = holding_stats[name]['pct']
            if pct > 0:
                color = colors.get(name, '#888')
                label = name if pct >= 5 else ''
                parts.append(f'<span class="hb" style="width:{pct}%;background:{color}" title="{name}: {pct}%"><span class="hb-l">{label}</span></span>')
    return f'<div class="hbar">{"".join(parts)}</div>'

# 近期操作表行
ops_rows = []
for op in recent_ops[-15:]:
    change_icon = '<span class="change-icon">→</span>' if op['changed'] else '<span class="hold-icon">·</span>'
    pos_color = colors.get(op['position_name'], '#888')
    signal_color = colors.get(op['signal_name'], '#888')
    bf_str = f"{op['signal_bf']:+.4f}" if op['signal_bf'] is not None else '---'
    cb_badge = '<span class="cb-badge">⚡熔断</span>' if op['was_cb'] else ''
    ret_class = 'pos' if op['v14_ret'] >= 0 else 'neg'
    dd_class = 'dd-warn' if op['v8_dd'] < -DD_RELEASE else 'dd-normal'
    if op['v8_dd'] < -DD_TRIGGER:
        dd_class = 'dd-danger'
    
    ops_rows.append(f'''<tr>
        <td>{op['date']}<span class="weekday">周{op['weekday']}</span></td>
        <td>{change_icon}</td>
        <td><span class="pos-tag" style="background:{pos_color}">{op['position_name']}</span>{cb_badge}</td>
        <td><span class="signal-tag" style="background:{signal_color}">{op['signal_name']}</span></td>
        <td class="bf-val">{bf_str}</td>
        <td class="{dd_class}">{op['v8_dd']*100:+.2f}%</td>
        <td class="{ret_class}">{op['v14_ret']*100:+.2f}%</td>
        <td>{op['v14_nav']:.4f}</td>
    </tr>''')

# bf排名表行
bf_rows = []
for rank, item in enumerate(bf_ranking_available, 1):
    is_selected = item['id'] == today_signal
    row_class = 'selected-row' if is_selected else ''
    above_badge = '<span class="above-badge">站上MA20</span>' if item['above'] else '<span class="below-badge">跌破MA20</span>'
    daily_class = 'pos' if item['daily_ret'] and item['daily_ret'] >= 0 else 'neg'
    daily_str = f"{item['daily_ret']*100:+.2f}%" if item['daily_ret'] is not None else '---'
    selected_badge = '<span class="selected-badge">◀ 选中</span>' if is_selected else ''
    color = colors.get(item['name'], '#888')
    
    bf_rows.append(f'''<tr class="{row_class}">
        <td>{rank}</td>
        <td><span class="stock-tag" style="background:{color}">{item['name']}</span></td>
        <td>{item['close']:.2f}</td>
        <td>{item['ma20']:.2f}</td>
        <td>{item['ratio']:.4f}</td>
        <td class="bf-val">{item['bf']:+.4f}</td>
        <td class="{daily_class}">{daily_str}</td>
        <td>{above_badge}</td>
        <td>{selected_badge}</td>
    </tr>''')

# 不可用标的
for item in bf_ranking:
    if not item['available']:
        bf_rows.append(f'''<tr class="unavailable-row">
            <td>--</td>
            <td><span class="stock-tag" style="background:{colors.get(item['name'], '#888')}">{item['name']}</span></td>
            <td colspan="7" class="unavailable-text">当日无数据</td>
        </tr>''')

# 熔断事件
cb_events_html = ''
if recent_cb_events:
    cb_event_rows = []
    for ev in recent_cb_events:
        ev_type = '触发' if ev['event'] == 'TRIGGER' else '解除'
        ev_class = 'cb-trigger' if ev['event'] == 'TRIGGER' else 'cb-release'
        from_color = colors.get(all_names[ev['from']], '#888')
        to_color = colors.get(all_names[ev['to']], '#888')
        cb_event_rows.append(f'''<tr>
            <td>{ev['date'].strftime('%Y-%m-%d')}</td>
            <td class="{ev_class}">{ev_type}</td>
            <td>{ev['dd']*100:.2f}%</td>
            <td><span class="pos-tag" style="background:{from_color}">{all_names[ev['from']]}</span> → <span class="pos-tag" style="background:{to_color}">{all_names[ev['to']]}</span></td>
        </tr>''')
    cb_events_html = f'''<div class="card">
        <h3>近期熔断事件</h3>
        <table class="cb-table"><thead><tr><th>日期</th><th>事件</th><th>V8回撤</th><th>操作</th></tr></thead><tbody>{''.join(cb_event_rows)}</tbody></table>
    </div>'''

# 动作卡片样式
action_styles = {
    'hold': 'action-hold',
    'buy': 'action-buy',
    'sell_to_bond': 'action-sell',
    'switch': 'action-switch',
    'cb_hold': 'action-cb',
    'release_buy': 'action-buy',
    'release_hold_bond': 'action-cb',
}
action_class = action_styles.get(action_type, 'action-hold')

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>V14策略每日信号 — {today_date.strftime('%Y-%m-%d')}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Microsoft YaHei','Segoe UI',sans-serif; background:#f5f6fa; color:#333; padding:20px; max-width:960px; margin:0 auto; }}
h1 {{ text-align:center; font-size:24px; margin-bottom:4px; }}
.sub-title {{ text-align:center; font-size:13px; color:#666; margin-bottom:20px; }}
.data-freshness {{ text-align:center; font-size:12px; color:#999; margin-bottom:16px; }}

.action-card {{ border-radius:12px; padding:24px; margin-bottom:20px; text-align:center; box-shadow:0 4px 12px rgba(0,0,0,0.1); }}
.action-card .action-label {{ font-size:14px; opacity:0.8; margin-bottom:8px; }}
.action-card .action-text {{ font-size:22px; font-weight:700; }}
.action-hold {{ background:linear-gradient(135deg,#2ecc71,#27ae60); color:#fff; }}
.action-buy {{ background:linear-gradient(135deg,#e74c3c,#c0392b); color:#fff; }}
.action-sell {{ background:linear-gradient(135deg,#2ecc71,#27ae60); color:#fff; }}
.action-switch {{ background:linear-gradient(135deg,#f39c12,#e67e22); color:#fff; }}
.action-cb {{ background:linear-gradient(135deg,#9b59b6,#8e44ad); color:#fff; }}

.status-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }}
.status-card {{ background:#fff; border-radius:8px; padding:14px; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.06); }}
.status-card h3 {{ font-size:12px; color:#888; margin-bottom:6px; }}
.status-card .val {{ font-size:18px; font-weight:700; }}
.status-card .sub {{ font-size:11px; color:#999; margin-top:2px; }}
.status-card.cb-active {{ border:2px solid #9b59b6; }}
.status-card.cb-normal {{ border:2px solid #2ecc71; }}

.card {{ background:#fff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.06); margin-bottom:20px; overflow:hidden; }}
.card h3 {{ background:#f8f9fa; padding:12px 16px; font-size:15px; border-bottom:1px solid #eee; }}
.card-body {{ padding:16px; }}

table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ padding:8px 6px; text-align:center; font-weight:600; color:#666; border-bottom:2px solid #e0e0e0; white-space:nowrap; }}
td {{ padding:7px 6px; text-align:center; border-bottom:1px solid #f0f0f0; }}
tr:hover td {{ background:#f8f9ff; }}

.pos {{ color:#e74c3c; font-weight:600; }}
.neg {{ color:#27ae60; font-weight:600; }}
.bf-val {{ font-family:Consolas,monospace; font-weight:600; }}
.dd-normal {{ color:#888; }}
.dd-warn {{ color:#f39c12; font-weight:600; }}
.dd-danger {{ color:#e74c3c; font-weight:700; }}

.selected-row {{ background:#fffde7 !important; }}
.selected-row:hover td {{ background:#fff9c4 !important; }}
.unavailable-row td {{ color:#ccc; }}
.unavailable-text {{ font-style:italic; }}

.stock-tag, .pos-tag, .signal-tag {{ display:inline-block; padding:2px 8px; border-radius:4px; color:#fff; font-size:12px; font-weight:500; }}
.signal-tag {{ opacity:0.7; }}

.above-badge {{ display:inline-block; padding:1px 6px; border-radius:3px; background:#e8f5e9; color:#2e7d32; font-size:11px; }}
.below-badge {{ display:inline-block; padding:1px 6px; border-radius:3px; background:#fbe9e7; color:#c62828; font-size:11px; }}
.selected-badge {{ color:#e74c3c; font-weight:700; font-size:12px; }}

.change-icon {{ color:#f39c12; font-weight:700; }}
.hold-icon {{ color:#ccc; }}
.cb-badge {{ display:inline-block; margin-left:4px; padding:1px 5px; border-radius:3px; background:#9b59b6; color:#fff; font-size:10px; }}
.weekday {{ color:#aaa; font-size:11px; margin-left:3px; }}

.cb-trigger {{ color:#e74c3c; font-weight:700; }}
.cb-release {{ color:#2ecc71; font-weight:700; }}
.cb-table td:nth-child(3) {{ font-family:Consolas,monospace; }}

.hbar {{ display:flex; width:100%; height:24px; border-radius:4px; overflow:hidden; margin:8px 0; }}
.hb {{ display:inline-flex; align-items:center; justify-content:center; height:100%; font-size:10px; color:#fff; white-space:nowrap; overflow:hidden; }}
.hb-l {{ font-size:9px; }}

.legend {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; }}
.legend-item {{ display:flex; align-items:center; gap:3px; font-size:11px; }}
.legend-color {{ width:12px; height:12px; border-radius:2px; }}

.chart-container {{ padding:16px; }}
.rules-box {{ background:#fff3cd; border:1px solid #ffeaa7; border-radius:8px; padding:12px 16px; margin-bottom:20px; font-size:12px; color:#856404; line-height:1.6; }}

@media (max-width: 768px) {{
    .status-grid {{ grid-template-columns:repeat(2,1fr); }}
    table {{ font-size:12px; }}
}}
</style>
</head>
<body>
<h1>V14策略每日信号</h1>
<div class="sub-title">MA20轮动 · 5%回撤熔断/4%解除 · T日收盘信号→T+1开盘执行 · 手续费0.02%</div>
<div class="data-freshness">数据更新至 <b>{today_date.strftime('%Y-%m-%d')}</b>（周{['一','二','三','四','五','六','日'][today_date.dayofweek]}）| 策略起始: {df['date'].iloc[0].strftime('%Y-%m-%d')} | 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>

<div class="action-card {action_class}">
    <div class="action-label">下一交易日操作</div>
    <div class="action-text">{action_text}</div>
</div>

<div class="status-grid">
    <div class="status-card {'cb-active' if cb_active else 'cb-normal'}">
        <h3>当前持仓</h3>
        <div class="val" style="color:{colors.get(all_names[today_position], '#333')}">{all_names[today_position]}</div>
        <div class="sub">下一交易日: {all_names[next_position]}</div>
    </div>
    <div class="status-card {'cb-active' if cb_active else 'cb-normal'}">
        <h3>熔断状态</h3>
        <div class="val">{'⚡ 熔断中' if cb_active else '✓ 正常'}</div>
        <div class="sub">V8回撤 {v8_dd*100:.2f}%</div>
    </div>
    <div class="status-card">
        <h3>V8基线净值</h3>
        <div class="val">{v8_nav:.4f}</div>
        <div class="sub">峰值 {v8_peak:.4f}</div>
    </div>
    <div class="status-card">
        <h3>V14策略净值</h3>
        <div class="val">{v14_nav:.4f}</div>
        <div class="sub">回撤 {v14_dd*100:.2f}%</div>
    </div>
</div>

<div class="card">
    <h3>bf排名（收盘价/MA20 - 1）</h3>
    <table>
        <thead><tr>
            <th>排名</th><th>标的</th><th>收盘价</th><th>MA20</th><th>比值</th><th>bf</th><th>当日涨跌</th><th>状态</th><th></th>
        </tr></thead>
        <tbody>{''.join(bf_rows)}</tbody>
    </table>
</div>

<div class="card">
    <h3>近15日操作明细</h3>
    <table>
        <thead><tr>
            <th>日期</th><th></th><th>实际持仓</th><th>信号标的</th><th>决策bf</th><th>V8回撤</th><th>V14收益</th><th>V14净值</th>
        </tr></thead>
        <tbody>{''.join(ops_rows)}</tbody>
    </table>
    <div style="padding:8px 16px;font-size:11px;color:#999;">
        决策bf = 当日收盘的bf值（T日收盘信号→T+1开盘执行） | V8回撤 = V8基线净值从高点的回撤
    </div>
</div>

<div class="card chart-container">
    <h3 style="margin:-16px -16px 12px -16px;">V14净值走势（近1年）</h3>
    {gen_nav_chart()}
</div>

{cb_events_html}

<div class="card">
    <h3>策略整体表现（近20年: {df['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['date'].iloc[-1].strftime('%Y-%m-%d')}）</h3>
    <div class="card-body">
        <div class="status-grid" style="margin-bottom:12px;">
            <div class="status-card"><h3>总收益</h3><div class="val {'pos' if total_ret >= 0 else 'neg'}">{total_ret*100:+.2f}%</div></div>
            <div class="status-card"><h3>年化收益</h3><div class="val {'pos' if ann_ret >= 0 else 'neg'}">{ann_ret*100:+.2f}%</div></div>
            <div class="status-card"><h3>夏普率</h3><div class="val">{sharpe_all:.2f}</div></div>
            <div class="status-card"><h3>最大回撤</h3><div class="val" style="color:#e74c3c">{mdd_val*100:.2f}%</div></div>
        </div>
        <h4 style="font-size:13px;color:#666;margin-bottom:6px;">持仓占比</h4>
        {gen_holding_bar()}
        <div class="legend">
            {''.join([f'<div class="legend-item"><div class="legend-color" style="background:{colors.get(k,'#888')}"></div>{k} {v["pct"]}%</div>' for k,v in holding_stats.items()])}
        </div>
    </div>
</div>

<div class="rules-box">
    <b>策略规则：</b><br>
    1. <b>选股</b>：每日收盘后计算8个股指的 bf = 收盘价/MA20 - 1。选bf最高且站上MA20(比值≥1)的标的持有；若全部跌破MA20则持国债。<br>
    2. <b>熔断</b>：V8基线（无熔断版策略）净值从历史高点回撤超过5%时，强制转入国债避险；回撤恢复至4%以内时解除熔断，恢复正常选股。<br>
    3. <b>执行</b>：T日收盘计算信号 → T+1日开盘执行买卖。手续费0.02%。<br>
    4. <b>动态标的池</b>：各标的在有数据时参与选股（如创业板50从2014年起、科创50从2020年起），无数据时不参与。<br>
    <b>使用方法：</b>每日收盘后从同花顺导出最新数据 → 运行本脚本 → 按报告操作。
</div>

</body>
</html>'''

out_path = 'C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_daily_signal.html'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"HTML报告已生成: {out_path}")

# 保存JSON数据
json_data = {
    'date': today_date.strftime('%Y-%m-%d'),
    'current_position': all_names[today_position],
    'next_position': all_names[next_position],
    'action': action_text,
    'action_type': action_type,
    'cb_active': cb_active,
    'v8_nav': v8_nav,
    'v8_peak': v8_peak,
    'v8_dd': v8_dd,
    'v14_nav': v14_nav,
    'v14_dd': v14_dd,
    'bf_ranking': [{k: (bool(v) if isinstance(v, (np.bool_,)) else (float(v) if isinstance(v, (np.floating,)) else (int(v) if isinstance(v, (np.integer,)) else v))) for k, v in item.items() if k != 'id'} for item in bf_ranking_available],
    'overall': {
        'total_ret': total_ret,
        'ann_ret': ann_ret,
        'sharpe': sharpe_all,
        'mdd': mdd_val,
        'ann_vol': ann_vol,
    },
}
with open('C:/Users/wbl/WorkBuddy/2026-07-20-20-22-46/v14_daily_signal.json', 'w', encoding='utf-8') as f:
    json.dump(json_data, f, ensure_ascii=False, indent=2)
print("数据已保存到 v14_daily_signal.json")
