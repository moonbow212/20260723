# -*- coding: utf-8 -*-
"""V14熔断变体对比：原版(5%/4%) vs 新版(-8%触发/-30%强制买入/-7%恢复)
策略定义：
  - 决策日期 = T日（执行日）
  - 决策bf = (T-1日收盘价 / T-1日MA20) - 1
  - T日开盘执行，收益口径 open-to-open
  - 费率万0.5(0.00005)，每次买卖各收一次
  
原版熔断：V8回撤<-5%触发熔断转国债，>-4%解除
新版熔断：V8回撤<-8%触发熔断转国债，<-30%强制重新买入(解除熔断)，>-7%正常解除
"""
import pandas as pd
import numpy as np
import json, os

# 原版熔断参数
DD_TRIGGER_ORIG = 0.05
DD_RELEASE_ORIG = 0.04

# 新版熔断参数
DD_TRIGGER_NEW = 0.08   # -8%触发
DD_RELEASE_NEW = 0.07   # -7%正常解除
DD_FORCE_BUY = 0.30     # -30%强制重新买入

FEE = 0.00005  # 万0.5
MA_PERIOD = 20

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
        d[f'ma{MA_PERIOD}_{i}'] = d[f'close_{i}'].rolling(MA_PERIOD).mean()
        d[f'bf{MA_PERIOD}_{i}'] = d[f'close_{i}'] / d[f'ma{MA_PERIOD}_{i}'] - 1
        d[f'ratio{MA_PERIOD}_{i}'] = d[f'close_{i}'] / d[f'ma{MA_PERIOD}_{i}']
    dfs[i] = d

last_date = dfs[BOND]['date'].max()
print(f"数据最新日期: {last_date.date()}")


# ===== 2. 构建合并数据 =====
def build_merged_data(start_date, end_date):
    df = dfs[BOND][['date', f'open_{BOND}', f'close_{BOND}']].copy()
    df = df.sort_values('date').reset_index(drop=True)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].reset_index(drop=True)

    for i in STOCK_ALL:
        ma_col = f'ma{MA_PERIOD}_{i}'
        bf_col = f'bf{MA_PERIOD}_{i}'
        ratio_col = f'ratio{MA_PERIOD}_{i}'
        cols = ['date', f'open_{i}', f'close_{i}', ma_col, bf_col, ratio_col]
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

    bf_prefix = f'bf{MA_PERIOD}'
    ratio_prefix = f'ratio{MA_PERIOD}'

    def get_signal(row):
        available = {}
        for i in STOCK_ALL:
            bf_val = row[f'{bf_prefix}_{i}']
            ratio_val = row[f'{ratio_prefix}_{i}']
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
            if prev in all_ids: cost += fee
            if pos in all_ids: cost += fee
        return (1 + gross) * (1 - cost) - 1

    df['raw_strat_ret'] = df.apply(lambda r: get_raw_strat_ret(r, FEE), axis=1)
    df['raw_strat_nav'] = (1 + df['raw_strat_ret']).cumprod()
    df['raw_cummax'] = df['raw_strat_nav'].cummax()
    df['raw_dd'] = df['raw_strat_nav'] / df['raw_cummax'] - 1
    return df, all_ids


# ===== 3. 熔断 =====
def apply_circuit_breaker_original(df, all_ids, bond_id):
    """原版：-5%触发，-4%解除"""
    raw_pos = df['raw_position'].values
    raw_dd = df['raw_dd'].values
    n = len(df)
    in_cb = False
    final_position = []
    cb_events = []  # (index, event_type)
    for i in range(n):
        sig = int(raw_pos[i])
        dd = raw_dd[i]
        if not in_cb:
            if dd < -DD_TRIGGER_ORIG and sig != bond_id:
                in_cb = True
                final_position.append(bond_id)
                cb_events.append((i, 'trigger'))
            else:
                final_position.append(sig)
        else:
            if dd > -DD_RELEASE_ORIG:
                in_cb = False
                final_position.append(sig)
                cb_events.append((i, 'release'))
            else:
                final_position.append(bond_id)
    return np.array(final_position), cb_events


def apply_circuit_breaker_new(df, all_ids, bond_id):
    """新版：-8%触发，-7%正常解除，-30%强制重新买入"""
    raw_pos = df['raw_position'].values
    raw_dd = df['raw_dd'].values
    n = len(df)
    in_cb = False
    final_position = []
    cb_events = []  # (index, event_type)
    for i in range(n):
        sig = int(raw_pos[i])
        dd = raw_dd[i]
        if not in_cb:
            if dd < -DD_TRIGGER_NEW and sig != bond_id:
                in_cb = True
                final_position.append(bond_id)
                cb_events.append((i, 'trigger'))
            else:
                final_position.append(sig)
        else:
            # 在熔断中
            if dd < -DD_FORCE_BUY:
                # 强制重新买入
                in_cb = False
                final_position.append(sig)
                cb_events.append((i, 'force_buy'))
            elif dd > -DD_RELEASE_NEW:
                # 正常解除
                in_cb = False
                final_position.append(sig)
                cb_events.append((i, 'release'))
            else:
                final_position.append(bond_id)
    return np.array(final_position), cb_events


def compute_v14_ret(df, all_ids, bond_id, pos, fee):
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
            if int(prev_pos[i]) in all_ids: cost += fee
            if p in all_ids: cost += fee
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
    ('original', '原版(5%/4%)', apply_circuit_breaker_original),
    ('new', '新版(-8%/-30%/-7%)', apply_circuit_breaker_new),
]

results = {}
for vkey, vlabel, cb_func in variants:
    v_results = {}
    for pname in ['近20年','近10年','近5年','近3年','近1年']:
        sd = periods_config[pname]
        df, all_ids = build_merged_data(sd, last_date)
        pos_v14, cb_events = cb_func(df, all_ids, BOND)
        v14_rets = compute_v14_ret(df, all_ids, BOND, pos_v14, FEE)
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
            # 统计该年熔断天数和force_buy天数
            cb_days = int((sub['v14_pos'] == BOND).sum())
            yearly_list.append({
                'year': int(y),
                'n_days': int(ny),
                'ret': round(float(year_ret)*100, 2),
                'mdd': round(float(year_mdd)*100, 2),
                'cb_days': cb_days,
                'switches': int(np.sum(np.diff(sub['v14_pos'].values) != 0)),
            })

        total_ret = (1 + df['v14_ret']).prod() - 1
        nav_all = (1 + df['v14_ret']).cumprod()
        mdd_all = ((nav_all - nav_all.cummax()) / nav_all.cummax()).min()
        std_all = df['v14_ret'].std()
        sharpe_all = np.sqrt(252) * df['v14_ret'].mean() / std_all if std_all > 0 else 0
        ann_all = (1 + total_ret) ** (252/len(df)) - 1
        total_switches = int(np.sum(np.diff(pos_v14) != 0))
        total_cb_days = int((pos_v14 == BOND).sum())
        
        # 统计熔断事件
        n_trigger = sum(1 for _, ev in cb_events if ev == 'trigger')
        n_release = sum(1 for _, ev in cb_events if ev == 'release')
        n_force_buy = sum(1 for _, ev in cb_events if ev == 'force_buy')

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
                'cb_days': total_cb_days,
                'n_trigger': n_trigger,
                'n_release': n_release,
                'n_force_buy': n_force_buy,
            },
        }
        print(f"  {vlabel} {pname}: 总收益={float(total_ret)*100:+.2f}%, 夏普={float(sharpe_all):.2f}, 回撤={float(mdd_all)*100:.2f}%, "
              f"熔断{total_cb_days}天, 触发{n_trigger}次, 解除{n_release}次, 强制买入{n_force_buy}次")
    results[vkey] = v_results

with open(os.path.join(BASE_DIR, 'v14_cb_variant.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\n数据已保存到 v14_cb_variant.json")


# ===== 5. 生成HTML =====
html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14熔断变体对比：原版(5%/4%) vs 新版(-8%/-30%/-7%)</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Microsoft YaHei','Segoe UI',sans-serif; background:#f5f6fa; color:#333; padding:20px; }}
h1 {{ text-align:center; font-size:22px; margin-bottom:5px; }}
.sub {{ text-align:center; font-size:13px; color:#666; margin-bottom:20px; }}
.note {{ background:#e8f4fd; border:1px solid #b3d9f2; border-radius:6px; padding:10px 16px; margin-bottom:16px; font-size:13px; color:#1a5276; }}
.summary-grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:24px; }}
.summary-card {{ background:#fff; border-radius:8px; padding:14px; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.06); }}
.summary-card h3 {{ font-size:14px; color:#666; margin-bottom:8px; }}
.summary-card .v-row {{ display:flex; justify-content:center; gap:8px; margin:3px 0; font-size:13px; }}
.summary-card .v-label {{ font-size:11px; min-width:80px; text-align:right; color:#888; }}
.summary-card .v-val {{ font-weight:700; min-width:65px; text-align:left; }}
.period-card {{ background:#fff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.08); margin-bottom:24px; overflow:hidden; }}
.period-header {{ background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; padding:14px 20px; }}
.period-header h2 {{ font-size:18px; margin-bottom:4px; }}
.period-header .info {{ font-size:13px; opacity:0.9; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ background:#f8f9fa; padding:8px 5px; text-align:center; font-weight:600; border-bottom:2px solid #e0e0e0; white-space:nowrap; }}
td {{ padding:7px 5px; text-align:center; border-bottom:1px solid #eee; }}
tr:hover td {{ background:#f8f9ff; }}
.pos {{ color:#e74c3c; font-weight:600; }}
.neg {{ color:#27ae60; font-weight:600; }}
.col-orig {{ background:#e3f2fd; }}
.col-new {{ background:#fff3e0; }}
.col-cb {{ background:#fce4ec; }}
.col-fb {{ background:#e8f5e9; }}
.diff-pos {{ color:#e74c3c; font-weight:600; }}
.diff-neg {{ color:#27ae60; font-weight:600; }}
.overall-row {{ background:#fffde7 !important; font-weight:600; }}
.overall-row td {{ border-top:2px solid #f0e68c; border-bottom:2px solid #f0e68c; }}
.tag {{ display:inline-block; padding:1px 5px; border-radius:3px; font-size:10px; font-weight:500; }}
.tag-trigger {{ background:#c62828; color:#fff; }}
.tag-release {{ background:#2e7d32; color:#fff; }}
.tag-force {{ background:#1565c0; color:#fff; }}
</style>
</head>
<body>
<h1>V14熔断变体对比：原版(5%/4%) vs 新版(-8%/-30%/-7%)</h1>
<div class="sub">MA20 · 费率万0.5 · 8股+国债动态标的池 · 决策bf=(T-1收盘/T-1 MA20)-1 · T日开盘执行 · open-to-open</div>
<div class="note">
<b>原版熔断</b>：V8回撤 &lt; -5% 触发熔断转国债，&gt; -4% 解除<br>
<b>新版熔断</b>：V8回撤 &lt; -8% 触发熔断转国债，&lt; -30% 强制重新买入(解除熔断恢复正常交易)，&gt; -7% 正常解除<br>
<span style="color:#666">新版逻辑：市场温和下跌(-8%)时避险持国债，但如果市场暴跌到极端水平(-30%)，认为是恐慌性底部，强制重新买入抄底</span>
</div>
'''

# 汇总卡片
html += '<div class="summary-grid">'
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    html += f'<div class="summary-card"><h3>{pname}</h3>'
    for vkey, vlabel, _ in variants:
        o = results[vkey][pname]['overall']
        ret_cls = 'pos' if o['total_ret'] >= 0 else 'neg'
        html += f'<div class="v-row"><span class="v-label">{vlabel}</span><span class="v-val {ret_cls}">{o["total_ret"]:+.1f}%</span></div>'
    # 差异
    diff = results['new'][pname]['overall']['total_ret'] - results['original'][pname]['overall']['total_ret']
    diff_cls = 'diff-pos' if diff >= 0 else 'diff-neg'
    html += f'<div class="v-row"><span class="v-label" style="color:#888">差异</span><span class="v-val {diff_cls}">{diff:+.1f}%</span></div>'
    html += '</div>'
html += '</div>'

# 各时段表格
for pname in ['近20年','近10年','近5年','近3年','近1年']:
    r = results['original'][pname]
    html += f'''<div class="period-card">
    <div class="period-header">
        <h2>{pname}</h2>
        <div class="info">{r["start"]} ~ {r["end"]} · {r["n_days"]}天</div>
    </div>
    <table>
    <thead><tr>
        <th rowspan="2">年份</th>
        <th rowspan="2">交易日</th>
        <th colspan="3" style="border-right:1px solid #ddd;background:#e3f2fd">原版(5%/4%)</th>
        <th colspan="4" style="border-right:1px solid #ddd;background:#fff3e0">新版(-8%/-30%/-7%)</th>
        <th rowspan="2">收益差异</th>
    </tr><tr>
        <th class="col-orig">收益</th>
        <th class="col-orig">回撤</th>
        <th class="col-orig">国债天数</th>
        <th class="col-new">收益</th>
        <th class="col-new">回撤</th>
        <th class="col-new">国债天数</th>
        <th class="col-new">切换</th>
    </tr></thead><tbody>'''

    all_years = sorted(set([y['year'] for y in r['yearly']]))
    for y in all_years:
        yo = next((yy for yy in results['original'][pname]['yearly'] if yy['year']==y), None)
        yn = next((yy for yy in results['new'][pname]['yearly'] if yy['year']==y), None)
        html += f'<tr><td>{y}</td>'
        html += f'<td>{yo["n_days"] if yo else "-"}</td>'
        # 原版
        if yo:
            ret_cls = 'pos' if yo['ret'] >= 0 else 'neg'
            html += f'<td class="col-orig {ret_cls}">{yo["ret"]:+.2f}%</td>'
            html += f'<td class="col-orig">{yo["mdd"]:.2f}%</td>'
            html += f'<td class="col-cb">{yo["cb_days"]}</td>'
        else:
            html += '<td class="col-orig">-</td><td class="col-orig">-</td><td class="col-cb">-</td>'
        # 新版
        if yn:
            ret_cls = 'pos' if yn['ret'] >= 0 else 'neg'
            html += f'<td class="col-new {ret_cls}">{yn["ret"]:+.2f}%</td>'
            html += f'<td class="col-new">{yn["mdd"]:.2f}%</td>'
            html += f'<td class="col-cb">{yn["cb_days"]}</td>'
            html += f'<td class="col-new">{yn["switches"]}</td>'
        else:
            html += '<td class="col-new">-</td><td class="col-new">-</td><td class="col-cb">-</td><td class="col-new">-</td>'
        # 差异
        if yo and yn:
            diff = yn['ret'] - yo['ret']
            diff_cls = 'diff-pos' if diff >= 0 else 'diff-neg'
            html += f'<td class="{diff_cls}">{diff:+.2f}%</td>'
        else:
            html += '<td>-</td>'
        html += '</tr>'

    # 整体行
    html += '<tr class="overall-row"><td>整体</td><td>-</td>'
    for vkey in ['original', 'new']:
        o = results[vkey][pname]['overall']
        ret_cls = 'pos' if o['total_ret'] >= 0 else 'neg'
        col_cls = 'col-orig' if vkey == 'original' else 'col-new'
        html += f'<td class="{col_cls} {ret_cls}">{o["total_ret"]:+.2f}%</td>'
        html += f'<td class="{col_cls}">{o["mdd"]:.2f}%</td>'
        html += f'<td class="col-cb">{o["cb_days"]}</td>'
        if vkey == 'new':
            html += f'<td class="{col_cls}">{o["switches"]}</td>'
    diff = results['new'][pname]['overall']['total_ret'] - results['original'][pname]['overall']['total_ret']
    diff_cls = 'diff-pos' if diff >= 0 else 'diff-neg'
    html += f'<td class="{diff_cls}">{diff:+.2f}%</td></tr>'

    # 统计行
    html += '<tr><td colspan="9" style="background:#f5f5f5;font-size:11px;color:#666;text-align:left;padding:8px 16px">'
    for vkey, vlabel, _ in variants:
        o = results[vkey][pname]['overall']
        html += f'<b>{vlabel}</b>: 年化{o["ann_ret"]:+.2f}% · 夏普{o["sharpe"]:.2f} · 回撤{o["mdd"]:.2f}% · 切换{o["switches"]}次 · '
        html += f'国债{o["cb_days"]}天({o["cb_days"]/o["switches"] if o["switches"]>0 else 0:.0f}天/次) · '
        html += f'<span class="tag tag-trigger">触发{o["n_trigger"]}</span> <span class="tag tag-release">解除{o["n_release"]}</span>'
        if 'n_force_buy' in o:
            html += f' <span class="tag tag-force">强制买入{o["n_force_buy"]}</span>'
        html += ' &nbsp;|&nbsp; '
    html += '</td></tr>'

    html += '</tbody></table></div>'

html += '''
<div style="text-align:center;font-size:12px;color:#999;margin-top:20px;">
收益口径: open-to-open · 蓝色列=原版(5%/4%) · 橙色列=新版(-8%/-30%/-7%) · 红底=国债持仓天数<br>
新版逻辑：-8%触发熔断 → -30%强制抄底或-7%恢复正常，熔断区间比原版更宽但增加了极端底部抄底机制
</div>
</body></html>'''

out_path = os.path.join(BASE_DIR, 'v14_cb_variant.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nHTML报告已生成: {out_path}")
