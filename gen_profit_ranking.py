# -*- coding: utf-8 -*-
"""生成近10年非国债持仓盈利明细HTML报告"""
import pandas as pd
import numpy as np

df = pd.read_csv('v14_past_10year_detail.csv', encoding='utf-8-sig')
df['ret_num'] = df['V14日收益'].str.replace('%', '').str.replace('+', '').astype(float) / 100

# 筛选盈利的非国债持仓
profit_df = df[(df['实际持仓'] != '国债') & (df['ret_num'] > 0)].copy()
profit_df = profit_df.sort_values('ret_num', ascending=False).reset_index(drop=True)
profit_df['排名'] = range(1, len(profit_df) + 1)

def pos_tag(name):
    colors = {
        '创业板50': '#e91e63',
        '科创50': '#9c27b0',
        '上证50': '#2196f3',
        '沪深300': '#00897b',
        '中证500': '#ff9800',
        '中证1000': '#795548',
        '纳斯达克100': '#3f51b5',
        '标普500': '#607d8b',
        '空仓': '#9e9e9e',
    }
    c = colors.get(name, '#666')
    return f'<span class="tag" style="background:{c}">{name}</span>'

rows_html = []
for idx, row in profit_df.iterrows():
    ret_pct = row['ret_num'] * 100
    # 根据收益大小设置行背景深浅
    if ret_pct >= 5:
        row_bg = 'background:#fff3e0'
    elif ret_pct >= 3:
        row_bg = 'background:#fff8e1'
    elif ret_pct >= 1:
        row_bg = 'background:#fffde7'
    else:
        row_bg = ''

    sig_bf = str(row['决策bf(T-1)']) if pd.notna(row['决策bf(T-1)']) and row['决策bf(T-1)'] != '' else '-'

    rows_html.append(f'''<tr style="{row_bg}">
<td class="rank">{row["排名"]}</td>
<td>{row["决策日期"]}</td>
<td>{row["星期"]}</td>
<td>{pos_tag(row["实际持仓"])}</td>
<td class="ret">{row["V14日收益"]}</td>
<td class="nav">{row["V14净值"]}</td>
<td>{row["信号标的(T-1收盘)"]}</td>
<td>{sig_bf}</td>
</tr>''')

rows_str = '\n'.join(rows_html)

total_profit = profit_df['ret_num'].sum() * 100
avg_profit = profit_df['ret_num'].mean() * 100
max_profit = profit_df['ret_num'].max() * 100
n = len(profit_df)

# 各标的盈利统计
stock_stats = []
for name in profit_df['实际持仓'].unique():
    sub = profit_df[profit_df['实际持仓'] == name]
    stock_stats.append({
        'name': name,
        'count': len(sub),
        'total': sub['ret_num'].sum() * 100,
        'avg': sub['ret_num'].mean() * 100,
        'max': sub['ret_num'].max() * 100,
    })
stock_stats.sort(key=lambda x: x['total'], reverse=True)

stats_html = ''
for s in stock_stats:
    colors = {
        '创业板50': '#e91e63',
        '科创50': '#9c27b0',
        '上证50': '#2196f3',
        '沪深300': '#00897b',
        '中证500': '#ff9800',
        '中证1000': '#795548',
        '纳斯达克100': '#3f51b5',
        '标普500': '#607d8b',
    }
    c = colors.get(s['name'], '#666')
    stats_html += f'''<div class="stat-card">
<div class="stat-header" style="background:{c}">{s['name']}</div>
<div class="stat-body">
<div>盈利次数: <b>{s['count']}</b></div>
<div>累计盈利: <b class="pos">+{s['total']:.2f}%</b></div>
<div>平均每次: <b class="pos">+{s['avg']:.2f}%</b></div>
<div>最大单次: <b class="pos">+{s['max']:.2f}%</b></div>
</div>
</div>'''

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14近10年非国债持仓盈利明细</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Microsoft YaHei', sans-serif; background: #f5f5f5; color: #333; padding: 20px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ text-align: center; font-size: 24px; margin-bottom: 5px; color: #1a1a1a; }}
.subtitle {{ text-align: center; font-size: 14px; color: #888; margin-bottom: 20px; }}
.summary {{ display: flex; gap: 15px; margin-bottom: 25px; flex-wrap: wrap; }}
.summary-card {{ background: white; padding: 15px 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex: 1; min-width: 140px; text-align: center; }}
.summary-card .label {{ font-size: 12px; color: #888; margin-bottom: 5px; }}
.summary-card .value {{ font-size: 22px; font-weight: bold; }}
.pos {{ color: #e0394b; }}
.neg {{ color: #00897b; }}
.stats-grid {{ display: flex; gap: 12px; margin-bottom: 25px; flex-wrap: wrap; }}
.stat-card {{ background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-width: 160px; flex: 1; }}
.stat-header {{ color: white; padding: 8px; text-align: center; font-weight: bold; font-size: 14px; }}
.stat-body {{ padding: 10px; font-size: 13px; line-height: 1.8; }}
.table-wrap {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
thead {{ position: sticky; top: 0; z-index: 10; }}
th {{ background: #2c3e50; color: white; padding: 10px 8px; text-align: center; font-weight: 500; white-space: nowrap; }}
td {{ padding: 7px 8px; text-align: center; border-bottom: 1px solid #f0f0f0; white-space: nowrap; }}
td.rank {{ font-weight: bold; color: #888; width: 50px; }}
td.ret {{ font-weight: bold; color: #e0394b; }}
td.nav {{ font-family: 'Courier New', monospace; font-size: 12px; color: #666; }}
tr:hover {{ background: #f8f9fa; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 500; color: white; }}
.footer {{ text-align: center; margin-top: 15px; font-size: 12px; color: #aaa; }}
</style>
</head>
<body>
<div class="container">
<h1>V14近10年 — 非国债持仓盈利明细</h1>
<p class="subtitle">2016-07-22 ~ 2026-07-22 | 按单日收益率从高到低排序 | 仅含盈利交易日</p>

<div class="summary">
<div class="summary-card"><div class="label">盈利天数</div><div class="value pos">{n}</div></div>
<div class="summary-card"><div class="label">累计盈利</div><div class="value pos">+{total_profit:.2f}%</div></div>
<div class="summary-card"><div class="label">平均每次</div><div class="value pos">+{avg_profit:.2f}%</div></div>
<div class="summary-card"><div class="label">最大单次</div><div class="value pos">+{max_profit:.2f}%</div></div>
</div>

<div class="stats-grid">
{stats_html}
</div>

<div class="table-wrap">
<table>
<thead>
<tr>
<th>排名</th>
<th>决策日期</th>
<th>星期</th>
<th>持仓标的</th>
<th>日收益</th>
<th>V14净值</th>
<th>信号标的</th>
<th>决策bf</th>
</tr>
</thead>
<tbody>
{rows_str}
</tbody>
</table>
</div>
<p class="footer">收益口径open-to-open | 仅展示收益>0的非国债持仓日</p>
</div>
</body>
</html>'''

with open('v14_profit_ranking.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f'HTML已生成: v14_profit_ranking.html ({len(html)} chars)')
print(f'共 {n} 条盈利记录')
