# -*- coding: utf-8 -*-
"""
V14策略晨间推送
================
每天早晨7点运行，用最新数据生成精简的晨间推送报告。
重点展示：近一个月实际持仓、信号标的、每个成分的决策bf及明细、V8回撤。
手机友好的HTML格式，部署到云端。

运行方式：
  python v14_morning_push.py
  （依赖data/目录下的CSV数据，由fetch_data.py生成）
"""
import pandas as pd
import numpy as np
import json, os, sys
from datetime import datetime

# ===== 报告类型（盘前版/盘后版） =====
report_type = 'morning'  # 默认盘前
if '--type' in sys.argv:
    idx = sys.argv.index('--type')
    if idx + 1 < len(sys.argv):
        report_type = sys.argv[idx + 1]
report_type_label = '盘前版' if report_type == 'morning' else '盘后版'
gen_time = datetime.now()
gen_time_str = gen_time.strftime('%Y-%m-%d %H:%M')
# 操作时点标签：盘前="今日开盘"，盘后="下一交易日开盘"
action_time_label = '今日开盘' if report_type == 'morning' else '下一交易日开盘'

FEE = 0.00005  # 万0.5
DD_TRIGGER = 0.05
DD_RELEASE = 0.04
GOLD_START = pd.Timestamp('2013-07-29')

STOCK_ALL = [2, 3, 5, 6, 7, 8, 11, 12, 13]
BOND = 9
GOLD = 10
names = {2:'创业板50',3:'纳斯达克100',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债',10:'黄金ETF',11:'中证A500',12:'北证50',13:'中证A50'}
all_names = {0:'空仓',2:'创业板50',3:'纳斯达克100',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',9:'国债',10:'黄金ETF',11:'中证A500',12:'北证50',13:'中证A50'}

colors = {
    '创业板50': '#f39c12', '纳斯达克100': '#3498db',
    '中证500': '#9b59b6', '中证1000': '#1abc9c',
    '标普500': '#e67e22', '科创50': '#d35400', '国债': '#95a5a6', '黄金ETF': '#d4a017', '空仓': '#bdc3c7',
    '中证A500': '#e74c3c', '北证50': '#2ecc71', '中证A50': '#3498db',
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== 1. 读取数据 =====
print("读取数据...")
dfs = {}
for i in STOCK_ALL + [BOND, GOLD]:
    name = names[i]
    csv_path = os.path.join(BASE_DIR, 'data', f'{i}_{name}.csv')
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"未找到 {name} 数据文件 {csv_path}，请先运行 fetch_data.py")
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

# ===== 2. 构建合并数据（近20年，动态join）=====
start_date = last_date - pd.DateOffset(years=20)
df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
df = df.sort_values('date').reset_index(drop=True)
df = df[(df['date'] >= start_date) & (df['date'] <= last_date)].reset_index(drop=True)

for i in STOCK_ALL:
    cols = ['date', f'open_{i}', f'close_{i}', f'ma20_{i}', f'bf_{i}', f'ratio_{i}']
    df = pd.merge(df, dfs[i][cols], on='date', how='left')

# 合并黄金ETF数据
gold_cols = ['date', f'open_{GOLD}', f'close_{GOLD}']
df = pd.merge(df, dfs[GOLD][gold_cols], on='date', how='left')

# 避险资产：黄金收盘价>20日均线→黄金ETF，≤20日均线→国债
df['gold_ma20'] = df[f'close_{GOLD}'].rolling(20).mean()
df['safe_haven'] = BOND  # 默认国债
mask_gold_available = df['date'] >= GOLD_START
mask_ma_available = df['gold_ma20'].notna()
mask_above_ma = df[f'close_{GOLD}'] > df['gold_ma20']
df.loc[mask_gold_available & mask_ma_available & mask_above_ma, 'safe_haven'] = GOLD

all_ids = STOCK_ALL + [BOND, GOLD]

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
df['raw_peak_1y'] = df['raw_strat_nav'].rolling(252, min_periods=1).max()
df['raw_dd'] = df['raw_strat_nav'] / df['raw_peak_1y'] - 1

# ===== 4. 应用5%/4%熔断 =====
raw_pos = df['raw_position'].values
raw_dd = df['raw_dd'].values
safe_havens = df['safe_haven'].values
n = len(df)
in_cb = False
final_position = []
cb_events = []

for i in range(n):
    sig = int(raw_pos[i])
    dd = raw_dd[i]
    safe = int(safe_havens[i])
    if not in_cb:
        if dd < -DD_TRIGGER and sig != safe:
            in_cb = True
            cb_events.append({
                'idx': i,
                'date': df['date'].iloc[i],
                'event': 'TRIGGER',
                'dd': float(dd),
                'from': sig, 'to': safe,
            })
            final_position.append(safe)
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
                'from': safe, 'to': sig,
            })
            final_position.append(sig)
        else:
            final_position.append(safe)

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
# 信号数据日期 = 所有在交易的标的都有数据的最后一个交易日（T-1日）
# 决策日期 = T日（下一个交易日），即执行日
# 盘后版：直接用数据最新日期作为信号日（当日收盘已出，美股缺数据则自动不参与选股）
if report_type == 'afternoon':
    signal_idx = df.index[-1]
else:
    second_last_idx = df.index[-2]
    currently_trading = [i for i in STOCK_ALL if pd.notna(df[f'bf_{i}'].iloc[second_last_idx])]
    if currently_trading:
        complete_mask = df[[f'bf_{i}' for i in currently_trading]].notna().all(axis=1)
        signal_idx = df[complete_mask].index[-1]
    else:
        signal_idx = df.index[-1]
signal_date = df['date'].iloc[signal_idx]  # T-1日（信号数据日）
data_latest_date = df['date'].iloc[-1]  # 数据库中最新日期

# 决策日期 = T日（signal_idx的下一个交易日）
future_mask = df['date'] > signal_date
if future_mask.any():
    decision_date = df.loc[future_mask, 'date'].iloc[0]
else:
    # 数据中没有下一天，估算下一个工作日
    decision_date = signal_date + pd.Timedelta(days=1)
    while decision_date.dayofweek >= 5:
        decision_date += pd.Timedelta(days=1)

# 信号基于T-1日（signal_idx）的收盘数据
today_signal = int(df['raw_signal'].iloc[signal_idx])
# 今日（T日）持仓 = final_position[signal_idx] 的下一个，由熔断逻辑决定
today_position = int(df['final_position'].iloc[signal_idx])
yesterday_position = int(df['final_position'].iloc[signal_idx - 1]) if signal_idx > 0 else 0

cb_active = in_cb
v8_nav = float(df['raw_strat_nav'].iloc[signal_idx])
v8_peak = float(df['raw_peak_1y'].iloc[signal_idx])
v8_dd = float(df['raw_dd'].iloc[signal_idx])
v14_nav = float(df['v14_nav'].iloc[signal_idx])
v14_dd = float(df['v14_dd'].iloc[signal_idx])
v14_peak = float(df['v14_cummax'].iloc[signal_idx])

# 判断下一交易日操作
current_safe = int(df['safe_haven'].iloc[signal_idx])
safe_name = names[current_safe]
# 黄金ETF避险状态
gold_close = df[f'close_{GOLD}'].iloc[signal_idx]
gold_ma20 = df['gold_ma20'].iloc[signal_idx]
gold_above = pd.notna(gold_ma20) and gold_close > gold_ma20
gold_status_text = f"收盘{gold_close:.3f} | 20日MA{gold_ma20:.3f} | {'高于MA20→选黄金ETF' if gold_above else '低于MA20→选国债'}" if pd.notna(gold_ma20) else "黄金20日MA不可用→选国债"
if cb_active:
    if v8_dd > -DD_RELEASE:
        next_position = today_signal
        if today_signal != current_safe:
            action_text = f"熔断解除！{action_time_label}买入「{names[today_signal]}」"
            action_type = "release_buy"
        else:
            action_text = f"熔断解除，但无标的站上MA20，继续持{safe_name}"
            action_type = "release_hold_bond"
    else:
        next_position = current_safe
        gap_to_release = abs(v8_dd) - DD_RELEASE
        action_text = f"熔断中，继续持{safe_name}（距解除还需恢复{gap_to_release*100:.2f}%）"
        action_type = "cb_hold"
else:
    next_position = today_signal
    if today_position == today_signal:
        action_text = f"继续持有「{names[today_signal]}」"
        action_type = "hold"
    elif today_position == current_safe and today_signal != current_safe:
        action_text = f"{action_time_label}买入「{names[today_signal]}」"
        action_type = "buy"
    elif today_position != current_safe and today_signal == current_safe:
        action_text = f"{action_time_label}卖出「{names[today_position]}」，转入{safe_name}"
        action_type = "sell_to_bond"
    else:
        action_text = f"{action_time_label}卖出「{names[today_position]}」，买入「{names[today_signal]}」"
        action_type = "switch"

# ===== 6. bf排名（基于T-1日signal_idx的收盘数据）=====
bf_ranking = []
for i in STOCK_ALL:
    bf_val = df[f'bf_{i}'].iloc[signal_idx]
    ratio_val = df[f'ratio_{i}'].iloc[signal_idx]
    close_val = df[f'close_{i}'].iloc[signal_idx]
    ma20_val = df[f'ma20_{i}'].iloc[signal_idx]
    open_val = df[f'open_{i}'].iloc[signal_idx]
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

# ===== 7. 近30天操作记录（决策日期=T日，bf基于T-1日）=====
recent_ops = []
start_op_idx = max(1, signal_idx - 28)  # 从1开始，因为需要i-1的数据
for i in range(start_op_idx, signal_idx + 1):
    pos = int(df['final_position'].iloc[i])
    prev_p = int(df['final_position'].iloc[i-1]) if i > 0 else 0
    # 决策日期T=i，信号基于T-1=i-1的收盘数据
    sig_src = i - 1
    signal = int(df['raw_signal'].iloc[sig_src])
    date_str = df['date'].iloc[i].strftime('%Y-%m-%d')
    weekday = df['date'].iloc[i].dayofweek
    
    # 决策依据bf（T-1日收盘的bf）
    if signal in STOCK_ALL:
        signal_bf = df[f'bf_{signal}'].iloc[sig_src]
        signal_bf = float(signal_bf) if pd.notna(signal_bf) else None
    else:
        signal_bf = None
    
    # 各成分bf明细（T-1日收盘）
    component_bfs = {}
    for j in STOCK_ALL:
        bf_j = df[f'bf_{j}'].iloc[sig_src]
        ratio_j = df[f'ratio_{j}'].iloc[sig_src]
        close_j = df[f'close_{j}'].iloc[sig_src]
        ma20_j = df[f'ma20_{j}'].iloc[sig_src]
        if pd.notna(bf_j):
                component_bfs[names[j]] = {
                    'bf': float(bf_j),
                    'ratio': float(ratio_j),
                    'close': float(close_j),
                    'ma20': float(ma20_j),
                    'above': ratio_j >= 1,
                }
    
    v8_dd_val = float(df['raw_dd'].iloc[i])
    v14_ret_val = float(df['v14_ret'].iloc[i])
    v14_nav_val = float(df['v14_nav'].iloc[i])
    
    was_cb = (pos == int(df['safe_haven'].iloc[i]) and signal != int(df['safe_haven'].iloc[i]))
    
    recent_ops.append({
        'date': date_str,
        'weekday': ['一','二','三','四','五','六','日'][weekday],
        'position': pos,
        'position_name': all_names[pos],
        'prev_position': prev_p,
        'signal': signal,
        'signal_name': all_names[signal],
        'signal_bf': signal_bf,
        'component_bfs': component_bfs,
        'v8_dd': v8_dd_val,
        'v14_ret': v14_ret_val,
        'v14_nav': v14_nav_val,
        'changed': pos != prev_p,
        'was_cb': was_cb,
        'is_today': False,
    })

# 添加今日决策行（T日=decision_date，基于T-1=signal_idx的收盘数据）
today_component_bfs = {}
today_signal_bf = None
if today_signal in STOCK_ALL:
    bf_val = df[f'bf_{today_signal}'].iloc[signal_idx]
    today_signal_bf = float(bf_val) if pd.notna(bf_val) else None
for j in STOCK_ALL:
    bf_j = df[f'bf_{j}'].iloc[signal_idx]
    ratio_j = df[f'ratio_{j}'].iloc[signal_idx]
    close_j = df[f'close_{j}'].iloc[signal_idx]
    ma20_j = df[f'ma20_{j}'].iloc[signal_idx]
    if pd.notna(bf_j):
        today_component_bfs[names[j]] = {
            'bf': float(bf_j),
            'ratio': float(ratio_j),
            'close': float(close_j),
            'ma20': float(ma20_j),
            'above': ratio_j >= 1,
        }

recent_ops.append({
    'date': decision_date.strftime('%Y-%m-%d'),
    'weekday': ['一','二','三','四','五','六','日'][decision_date.dayofweek],
    'position': next_position,
    'position_name': all_names[next_position],
    'prev_position': today_position,
    'signal': today_signal,
    'signal_name': all_names[today_signal],
    'signal_bf': today_signal_bf,
    'component_bfs': today_component_bfs,
    'v8_dd': v8_dd,
    'v14_ret': None,
    'v14_nav': None,
    'changed': next_position != today_position,
    'was_cb': (next_position == current_safe and today_signal != current_safe),
    'is_today': True,
})

# ===== 8. 策略整体表现 =====
total_ret = float(df['v14_nav'].iloc[-1] - 1)
ann_ret = (1 + total_ret) ** (252 / n) - 1
mdd_val = float(df['v14_dd'].min())
std_all = float(df['v14_ret'].std())
sharpe_all = np.sqrt(252) * df['v14_ret'].mean() / std_all if std_all > 0 else 0
ann_vol = std_all * np.sqrt(252)

# 持仓统计
holding_stats = {}
for a in STOCK_ALL + [BOND, GOLD, 0]:
    cnt = int((df['final_position'] == a).sum())
    if cnt > 0:
        holding_stats[all_names[a]] = {'days': cnt, 'pct': round(cnt / n * 100, 2)}

# ===== 9. 控制台输出 =====
print(f"\n{'='*70}")
print(f"  V14策略晨报【{report_type_label}】 — 决策日期 {decision_date.strftime('%Y-%m-%d')}")
print(f"  (决策bf基于{signal_date.strftime('%m月%d日')}收盘，数据库最新{data_latest_date.strftime('%m月%d日')})")
print(f"  生成时间: {gen_time_str}")
print(f"{'='*70}")

action_emoji = {'hold': '✅', 'buy': '🟢', 'sell_to_bond': '🔴', 'switch': '🟡', 'cb_hold': '⚡', 'release_buy': '🟢', 'release_hold_bond': '⚡'}
print(f"\n  {action_emoji.get(action_type, '▶')} {action_text}")
print(f"\n  当前持仓: {all_names[today_position]}")
print(f"  下一交易日持仓: {all_names[next_position]}")
print(f"  熔断状态: {'⚡ 熔断中' if cb_active else '✓ 正常'}")
print(f"  V8回撤(近1年): {v8_dd*100:.2f}%")
print(f"  V14净值: {v14_nav:.4f}")
print(f"\n  近30天操作记录数: {len(recent_ops)}")
print(f"{'='*70}")

# ===== 10. 生成HTML报告 =====
print("\n生成晨间推送HTML报告...")

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

# 近30天操作表行
ops_rows = []
for op in recent_ops:
    change_icon = '<span class="chg">→</span>' if op['changed'] else '<span class="hold-dot">·</span>'
    pos_color = colors.get(op['position_name'], '#888')
    signal_color = colors.get(op['signal_name'], '#888')
    bf_str = f"{op['signal_bf']:+.4f}" if op['signal_bf'] is not None else '---'
    cb_badge = '<span class="cb-tag">⚡</span>' if op['was_cb'] else ''
    if op['v14_ret'] is not None:
        ret_class = 'pos' if op['v14_ret'] >= 0 else 'neg'
        ret_str = f"{op['v14_ret']*100:+.2f}%"
    else:
        ret_class = ''
        ret_str = '---'
    dd_class = 'dd-ok' if op['v8_dd'] > -DD_RELEASE else ('dd-warn' if op['v8_dd'] > -DD_TRIGGER else 'dd-danger')
    today_class = ' class="today-row"' if op.get('is_today') else ''
    today_badge = '<span class="today-tag">今日</span>' if op.get('is_today') else ''
    
    ops_rows.append(f'''<tr{today_class}>
        <td class="date-col">{op['date']}<span class="wd">周{op['weekday']}</span>{today_badge}</td>
        <td>{change_icon}</td>
        <td><span class="tag" style="background:{pos_color}">{op['position_name']}</span>{cb_badge}</td>
        <td><span class="tag sig" style="background:{signal_color}">{op['signal_name']}</span></td>
        <td class="bf-val">{bf_str}</td>
        <td class="{dd_class}">{op['v8_dd']*100:+.2f}%</td>
        <td class="{ret_class}">{ret_str}</td>
    </tr>''')

# bf排名表行
bf_rows = []
for rank, item in enumerate(bf_ranking_available, 1):
    is_selected = item['id'] == today_signal
    row_class = 'sel-row' if is_selected else ''
    above_badge = '<span class="up-badge">↑站上</span>' if item['above'] else '<span class="dn-badge">↓跌破</span>'
    daily_class = 'pos' if item['daily_ret'] and item['daily_ret'] >= 0 else 'neg'
    daily_str = f"{item['daily_ret']*100:+.2f}%" if item['daily_ret'] is not None else '---'
    selected_badge = '<span class="sel-badge">◀ 选中</span>' if is_selected else ''
    color = colors.get(item['name'], '#888')
    
    bf_rows.append(f'''<tr class="{row_class}">
        <td class="rank-col">{rank}</td>
        <td><span class="tag" style="background:{color}">{item['name']}</span></td>
        <td class="num">{item['close']:.2f}</td>
        <td class="num">{item['ma20']:.2f}</td>
        <td class="num">{item['ratio']:.4f}</td>
        <td class="bf-val">{item['bf']:+.4f}</td>
        <td class="{daily_class}">{daily_str}</td>
        <td>{above_badge}</td>
        <td>{selected_badge}</td>
    </tr>''')

for item in bf_ranking:
    if not item['available']:
        bf_rows.append(f'''<tr class="na-row">
            <td class="rank-col">--</td>
            <td><span class="tag" style="background:{colors.get(item['name'], '#888')}">{item['name']}</span></td>
            <td colspan="7" class="na-text">当日无数据</td>
        </tr>''')

# 近30天各成分bf明细（可展开）
detail_rows = []
for op in reversed(recent_ops):  # 最新的在上面
    if not op['component_bfs']:
        continue
    # 按bf排序
    sorted_bfs = sorted(op['component_bfs'].items(), key=lambda x: x[1]['bf'], reverse=True)
    bf_details = []
    for sname, sdata in sorted_bfs:
        above_icon = '↑' if sdata['above'] else '↓'
        is_sig = sname == op['signal_name']
        sig_mark = '<span class="sel-badge">◀</span>' if is_sig else ''
        bf_details.append(f'<span class="bf-item {"sig-item" if is_sig else ""}">{sname} {above_icon} {sdata["bf"]:+.4f}{sig_mark}</span>')
    
    today_class = ' class="today-row"' if op.get('is_today') else ''
    today_badge = '<span class="today-tag">今日</span>' if op.get('is_today') else ''
    detail_rows.append(f'''<tr class="detail-row"{today_class}>
        <td class="date-col">{op['date']}<span class="wd">周{op['weekday']}</span>{today_badge}</td>
        <td><span class="tag sig" style="background:{colors.get(op['signal_name'], '#888')}">{op['signal_name']}</span></td>
        <td class="bf-detail-cell">{''.join(bf_details)}</td>
        <td class="{'dd-ok' if op['v8_dd'] > -DD_RELEASE else 'dd-warn' if op['v8_dd'] > -DD_TRIGGER else 'dd-danger'}">{op['v8_dd']*100:+.2f}%</td>
    </tr>''')

# 计算近30天持仓占比
recent_30 = df.iloc[start_op_idx:signal_idx+1]
recent_holding = {}
for a in STOCK_ALL + [BOND, GOLD, 0]:
    cnt = int((recent_30['final_position'] == a).sum())
    if cnt > 0:
        recent_holding[all_names[a]] = {'days': cnt, 'pct': round(cnt / len(recent_30) * 100, 1)}

# 近期熔断事件
recent_cb_events = cb_events[-3:] if len(cb_events) >= 3 else cb_events
cb_events_html = ''
if recent_cb_events:
    cb_rows = []
    for ev in recent_cb_events:
        ev_type = '触发' if ev['event'] == 'TRIGGER' else '解除'
        ev_class = 'cb-trig' if ev['event'] == 'TRIGGER' else 'cb-rel'
        from_color = colors.get(all_names[ev['from']], '#888')
        to_color = colors.get(all_names[ev['to']], '#888')
        cb_rows.append(f'''<tr>
            <td>{ev['date'].strftime('%Y-%m-%d')}</td>
            <td class="{ev_class}">{ev_type}</td>
            <td class="num">{ev['dd']*100:.2f}%</td>
            <td><span class="tag" style="background:{from_color}">{all_names[ev['from']]}</span> → <span class="tag" style="background:{to_color}">{all_names[ev['to']]}</span></td>
        </tr>''')
    cb_events_html = f'''<div class="card">
        <h3>近期熔断事件</h3>
        <table><thead><tr><th>日期</th><th>事件</th><th>V8回撤(近1年)</th><th>操作</th></tr></thead><tbody>{''.join(cb_rows)}</tbody></table>
    </div>'''

# 近30天持仓占比条
holding_bar_parts = []
for hn in ['创业板50','纳斯达克100','中证500','中证1000','标普500','科创50','中证A500','北证50','中证A50','国债','黄金ETF','空仓']:
    if hn in recent_holding:
        pct = recent_holding[hn]['pct']
        if pct > 0:
            color = colors.get(hn, '#888')
            label = hn if pct >= 8 else ''
            holding_bar_parts.append(f'<span class="hb" style="width:{pct}%;background:{color}"><span class="hb-l">{label}</span></span>')

# 操作标签：盘前版是"今日开盘"，盘后版是下一交易日
today_date = pd.Timestamp.now().normalize()
if decision_date <= today_date:
    action_label = '今日开盘操作'
else:
    action_label = f'{decision_date.strftime("%m月%d日")}开盘操作'

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14晨报【{report_type_label}】 — 决策{decision_date.strftime('%m月%d日')}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Microsoft YaHei','PingFang SC','Segoe UI',sans-serif; background:#f0f2f5; color:#333; padding:16px; max-width:720px; margin:0 auto; }}
h1 {{ text-align:center; font-size:20px; margin-bottom:2px; }}
.sub {{ text-align:center; font-size:12px; color:#888; margin-bottom:12px; }}
.fresh {{ text-align:center; font-size:11px; color:#aaa; margin-bottom:16px; }}

.act {{ border-radius:12px; padding:20px; margin-bottom:16px; text-align:center; box-shadow:0 3px 10px rgba(0,0,0,0.12); }}
.act .lbl {{ font-size:13px; opacity:0.85; margin-bottom:6px; }}
.act .txt {{ font-size:20px; font-weight:700; line-height:1.4; }}
.act-hold {{ background:linear-gradient(135deg,#2ecc71,#27ae60); color:#fff; }}
.act-buy {{ background:linear-gradient(135deg,#e74c3c,#c0392b); color:#fff; }}
.act-sell {{ background:linear-gradient(135deg,#2ecc71,#27ae60); color:#fff; }}
.act-switch {{ background:linear-gradient(135deg,#f39c12,#e67e22); color:#fff; }}
.act-cb {{ background:linear-gradient(135deg,#9b59b6,#8e44ad); color:#fff; }}

.grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-bottom:16px; }}
.gcard {{ background:#fff; border-radius:8px; padding:10px 6px; text-align:center; box-shadow:0 1px 4px rgba(0,0,0,0.06); }}
.gcard h3 {{ font-size:10px; color:#999; margin-bottom:4px; }}
.gcard .v {{ font-size:15px; font-weight:700; }}
.gcard .s {{ font-size:10px; color:#bbb; margin-top:1px; }}
.gcard.cb-on {{ border:2px solid #9b59b6; }}
.gcard.cb-off {{ border:2px solid #2ecc71; }}

.card {{ background:#fff; border-radius:10px; box-shadow:0 1px 6px rgba(0,0,0,0.06); margin-bottom:16px; overflow:hidden; }}
.card h3 {{ background:#f8f9fa; padding:10px 14px; font-size:14px; border-bottom:1px solid #eee; }}
.card-body {{ padding:14px; }}

table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ padding:6px 4px; text-align:center; font-weight:600; color:#777; border-bottom:2px solid #e0e0e0; white-space:nowrap; }}
td {{ padding:6px 4px; text-align:center; border-bottom:1px solid #f0f0f0; }}
tr:hover td {{ background:#f8f9ff; }}

.pos {{ color:#e74c3c; font-weight:600; }}
.neg {{ color:#27ae60; font-weight:600; }}
.bf-val {{ font-family:Consolas,monospace; font-weight:600; }}
.num {{ font-family:Consolas,monospace; }}
.dd-ok {{ color:#888; }}
.dd-warn {{ color:#f39c12; font-weight:600; }}
.dd-danger {{ color:#e74c3c; font-weight:700; }}

.sel-row {{ background:#fffde7 !important; }}
.sel-row:hover td {{ background:#fff9c4 !important; }}
.na-row td {{ color:#ccc; }}
.na-text {{ font-style:italic; }}

.tag {{ display:inline-block; padding:2px 6px; border-radius:3px; color:#fff; font-size:11px; font-weight:500; white-space:nowrap; }}
.tag.sig {{ opacity:0.75; }}
.up-badge {{ display:inline-block; padding:1px 5px; border-radius:3px; background:#e8f5e9; color:#2e7d32; font-size:10px; }}
.dn-badge {{ display:inline-block; padding:1px 5px; border-radius:3px; background:#fbe9e7; color:#c62828; font-size:10px; }}
.sel-badge {{ color:#e74c3c; font-weight:700; font-size:11px; }}

.chg {{ color:#f39c12; font-weight:700; }}
.hold-dot {{ color:#ccc; }}
.cb-tag {{ display:inline-block; margin-left:2px; padding:0 3px; border-radius:3px; background:#9b59b6; color:#fff; font-size:9px; }}
.wd {{ color:#aaa; font-size:10px; margin-left:2px; display:block; }}
.date-col {{ white-space:nowrap; font-size:11px; }}
.rank-col {{ font-weight:600; color:#999; }}

.cb-trig {{ color:#e74c3c; font-weight:700; }}
.cb-rel {{ color:#2ecc71; font-weight:700; }}
.today-row {{ background:#e3f2fd !important; }}
.today-row:hover td {{ background:#bbdefb !important; }}
.today-tag {{ display:inline-block; margin-left:2px; padding:0 4px; border-radius:3px; background:#2196f3; color:#fff; font-size:9px; }}

.hbar {{ display:flex; width:100%; height:22px; border-radius:4px; overflow:hidden; margin:6px 0; }}
.hb {{ display:inline-flex; align-items:center; justify-content:center; height:100%; font-size:9px; color:#fff; white-space:nowrap; overflow:hidden; }}
.hb-l {{ font-size:8px; }}
.legend {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:6px; }}
.li {{ display:flex; align-items:center; gap:2px; font-size:10px; }}
.lc {{ width:10px; height:10px; border-radius:2px; }}

.bf-item {{ display:inline-block; margin:2px 4px; padding:2px 5px; border-radius:3px; background:#f5f5f5; font-size:10px; white-space:nowrap; }}
.sig-item {{ background:#fff3cd; font-weight:600; }}
.bf-detail-cell {{ text-align:left; line-height:1.8; }}
.detail-row td {{ padding:5px 4px; }}

.rules {{ background:#fff3cd; border:1px solid #ffeaa7; border-radius:8px; padding:10px 14px; margin-bottom:16px; font-size:11px; color:#856404; line-height:1.5; }}

@media (max-width: 480px) {{
    .grid {{ grid-template-columns:repeat(2,1fr); }}
    table {{ font-size:11px; }}
    .act .txt {{ font-size:18px; }}
}}
</style>
</head>
<body>
<h1>V14策略晨报 <span style="font-size:14px;color:#fff;background:{'#e74c3c' if report_type == 'morning' else '#2980b9'};padding:2px 8px;border-radius:4px;vertical-align:middle;">{report_type_label}</span></h1>
<div class="sub">标的池: 创业板50·纳斯达克100·中证500·中证1000·标普500·科创50·中证A500·北证50·中证A50 | MA20轮动 · 5%熔断(近1年峰值)/4%解除 · 动态避险(金>20日MA→黄金ETF,金≤20日MA→国债) · T-1日收盘bf→T日开盘执行</div>
<div class="fresh">决策日期: {decision_date.strftime('%Y-%m-%d')}（周{['一','二','三','四','五','六','日'][decision_date.dayofweek]}）· 决策bf基于{signal_date.strftime('%m月%d日')}收盘{' · 数据库最新: ' + data_latest_date.strftime('%m月%d日') if data_latest_date != signal_date else ''} | <b style="color:#666;">{report_type_label}</b> 生成于 {gen_time_str}</div>

<div class="act {action_class}">
    <div class="lbl">{action_label}</div>
    <div class="txt">{action_text}</div>
</div>

<div class="grid">
    <div class="gcard {'cb-on' if cb_active else 'cb-off'}">
        <h3>当前持仓</h3>
        <div class="v" style="color:{colors.get(all_names[today_position], '#333')}">{all_names[today_position]}</div>
        <div class="s">→ {all_names[next_position]}</div>
    </div>
    <div class="gcard {'cb-on' if cb_active else 'cb-off'}">
        <h3>熔断状态</h3>
        <div class="v">{'⚡熔断中' if cb_active else '✓正常'}</div>
        <div class="s">V8回撤(近1年){v8_dd*100:.2f}%</div>
    </div>
    <div class="gcard">
        <h3>V8基线净值</h3>
        <div class="v">{v8_nav:.2f}</div>
        <div class="s">近1年峰值{v8_peak:.2f}</div>
    </div>
    <div class="gcard">
        <h3>V14策略净值</h3>
        <div class="v">{v14_nav:.2f}</div>
        <div class="s">回撤{v14_dd*100:.2f}%</div>
    </div>
</div>

<div class="card" style="padding:12px 14px;">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;font-size:12px;">
        <div style="display:flex;align-items:center;gap:6px;">
            <span style="font-weight:600;color:#666;">避险资产：</span>
            <span class="tag" style="background:{colors.get(safe_name, '#888')}">{safe_name}</span>
        </div>
        <div style="display:flex;align-items:center;gap:10px;">
            <span style="color:#888;">黄金ETF收盘</span>
            <span style="font-family:Consolas,monospace;font-weight:700;color:{'#e74c3c' if gold_above else '#27ae60'};">{gold_close:.3f}</span>
            <span style="color:#aaa;">|</span>
            <span style="color:#888;">20日MA</span>
            <span style="font-family:Consolas,monospace;font-weight:600;color:#666;">{gold_ma20:.3f}</span>
            <span style="color:#aaa;">|</span>
            <span style="padding:2px 6px;border-radius:3px;background:{'#fce4ec' if gold_above else '#e8f5e9'};color:{'#c62828' if gold_above else '#2e7d32'};font-size:11px;font-weight:600;">{'↑高于' if gold_above else '↓低于'}</span>
        </div>
    </div>
</div>

<div class="card">
    <h3>决策bf排名明细（{signal_date.strftime('%m月%d日')}收盘价/MA20 - 1）</h3>
    <table>
        <thead><tr>
            <th>#</th><th>标的</th><th>收盘</th><th>MA20</th><th>比值</th><th>决策bf</th><th>涨跌</th><th>状态</th><th></th>
        </tr></thead>
        <tbody>{''.join(bf_rows)}</tbody>
    </table>
</div>

<div class="card">
    <h3>近30天实际持仓与信号</h3>
    <table>
        <thead><tr>
            <th>决策日期</th><th></th><th>实际持仓</th><th>信号标的</th><th>决策bf</th><th>V8回撤(近1年)</th><th>V14收益</th>
        </tr></thead>
        <tbody>{''.join(reversed(ops_rows))}</tbody>
    </table>
    <div style="padding:6px 14px;font-size:10px;color:#aaa;">
        决策日期=T日（执行日），决策bf基于T-1日收盘价/MA20-1
    </div>
</div>

<div class="card">
    <h3>近30天各成分决策bf明细（T-1日收盘）</h3>
    <table>
        <thead><tr>
            <th>决策日期</th><th>信号标的</th><th>各成分决策bf（T-1日收盘）</th><th>V8回撤(近1年)</th>
        </tr></thead>
        <tbody>{''.join(detail_rows)}</tbody>
    </table>
</div>

<div class="card">
    <h3>近30天持仓占比</h3>
    <div class="card-body">
        <div class="hbar">{''.join(holding_bar_parts)}</div>
        <div class="legend">
            {''.join([f'<div class="li"><div class="lc" style="background:{colors.get(k,'#888')}"></div>{k} {v["pct"]}%</div>' for k,v in recent_holding.items()])}
        </div>
    </div>
</div>

{cb_events_html}

<div class="card">
    <h3>策略整体表现（近20年）</h3>
    <div class="card-body">
        <div class="grid" style="margin-bottom:8px;">
            <div class="gcard"><h3>总收益</h3><div class="v {'pos' if total_ret >= 0 else 'neg'}">{total_ret*100:+.1f}%</div></div>
            <div class="gcard"><h3>年化</h3><div class="v {'pos' if ann_ret >= 0 else 'neg'}">{ann_ret*100:+.1f}%</div></div>
            <div class="gcard"><h3>夏普</h3><div class="v">{sharpe_all:.2f}</div></div>
            <div class="gcard"><h3>最大回撤</h3><div class="v" style="color:#e74c3c">{mdd_val*100:.1f}%</div></div>
        </div>
    </div>
</div>

<div class="rules">
    <b>策略规则：</b>决策日期T日早晨，用T-1日收盘价计算各标的 决策bf = (T-1收盘价/T-1日MA20)-1，选bf最高且站上MA20的标的在T日开盘买入；全部跌破则持避险资产。避险资产动态选择：黄金ETF收盘价>20日均线时持黄金ETF，≤20日均线时持国债。V8基线相对近1年(252交易日)最高点回撤>5%触发熔断转避险资产，恢复<4%解除。手续费0.005%。
</div>

</body>
</html>'''

out_path = os.path.join(BASE_DIR, 'v14_morning_push.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"HTML报告已生成: {out_path}")

# 保存JSON数据
json_data = {
    'decision_date': decision_date.strftime('%Y-%m-%d'),
    'signal_date': signal_date.strftime('%Y-%m-%d'),
    'data_latest_date': data_latest_date.strftime('%Y-%m-%d'),
    'generated_at': gen_time_str,
    'report_type': report_type,
    'report_type_label': report_type_label,
    'current_position': all_names[today_position],
    'next_position': all_names[next_position],
    'action': action_text,
    'action_type': action_type,
    'cb_active': cb_active,
    'safe_haven': safe_name,
    'gold_close': float(gold_close) if pd.notna(gold_close) else None,
    'gold_ma20': float(gold_ma20) if pd.notna(gold_ma20) else None,
    'gold_above_ma': bool(gold_above),
    'v8_nav': v8_nav,
    'v8_peak': v8_peak,
    'v8_dd': v8_dd,
    'v14_nav': v14_nav,
    'v14_dd': v14_dd,
    'bf_ranking': [{k: (bool(v) if isinstance(v, (np.bool_,)) else (float(v) if isinstance(v, (np.floating,)) else (int(v) if isinstance(v, (np.integer,)) else v))) for k, v in item.items() if k != 'id'} for item in bf_ranking_available],
    'recent_ops': [{
        'date': op['date'],
        'position': op['position_name'],
        'signal': op['signal_name'],
        'signal_bf': op['signal_bf'],
        'v8_dd': op['v8_dd'],
        'v14_ret': op['v14_ret'],
        'changed': op['changed'],
        'was_cb': op['was_cb'],
    } for op in recent_ops],
    'overall': {
        'total_ret': total_ret,
        'ann_ret': ann_ret,
        'sharpe': sharpe_all,
        'mdd': mdd_val,
        'ann_vol': ann_vol,
    },
}
json_path = os.path.join(BASE_DIR, 'v14_morning_push.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(json_data, f, ensure_ascii=False, indent=2)
print(f"数据已保存到 {json_path}")
