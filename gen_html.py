# -*- coding: utf-8 -*-
"""生成近一年操作明细HTML报告"""
import pandas as pd
import numpy as np

df = pd.read_csv('v14_past_year_detail.csv', encoding='utf-8-sig')

def pos_tag(name):
    if name == '国债':
        return '<span class="tag tag-bond">国债</span>'
    elif name == '空仓':
        return '<span class="tag tag-empty">空仓</span>'
    else:
        return f'<span class="tag tag-stock">{name}</span>'

def ret_color(val):
    v = float(val.replace('%', '').replace('+', ''))
    cls = 'pos' if v > 0 else ('neg' if v < 0 else '')
    return f'<span class="{cls}">{val}</span>'

def dd_color(val):
    v = float(val.replace('%', '').replace('+', ''))
    if v < -5:
        return f'<span class="neg" style="font-weight:bold">{val}</span>'
    elif v < 0:
        return f'<span class="neg">{val}</span>'
    return val

rows_html = []
for idx, row in df.iterrows():
    row_class = ''
    cb_tag = ''
    if row['熔断状态'] == '熔断中':
        row_class = 'row-cb'
        cb_tag = '<span class="tag tag-cb">熔断中</span>'
    elif row['熔断状态'] == '解除':
        row_class = 'row-cb-release'
        cb_tag = '<span class="tag tag-release">解除</span>'
    elif row['是否换仓'] == '是':
        row_class = 'row-change'

    # bf detail
    bf_detail = str(row['各成分bf(T-1收盘)']) if pd.notna(row['各成分bf(T-1收盘)']) else ''
    bf_parts = bf_detail.split(' | ') if bf_detail else []
    bf_html_parts = []
    for p in bf_parts:
        if '↑' in p:
            bf_html_parts.append(f'<span class="bf-pos">{p}</span>')
        elif '↓' in p:
            bf_html_parts.append(f'<span class="bf-neg">{p}</span>')
        else:
            bf_html_parts.append(p)
    bf_html = ' | '.join(bf_html_parts)

    # 决策bf
    sig_bf = str(row['决策bf(T-1)']) if pd.notna(row['决策bf(T-1)']) and row['决策bf(T-1)'] != '' else ''
    if sig_bf:
        sig_bf_val = float(sig_bf)
        bf_cls = 'pos' if sig_bf_val > 0 else 'neg'
        sig_bf = f'<span class="{bf_cls}">{sig_bf}</span>'

    change_icon = '<span style="color:#e65100">🔄 换仓</span>' if row['是否换仓'] == '是' else ''

    rows_html.append(f'''<tr class="{row_class}">
<td>{row["决策日期"]}</td>
<td>{row["星期"]}</td>
<td>{pos_tag(row["实际持仓"])}</td>
<td>{pos_tag(row["前日持仓"])}</td>
<td>{change_icon}</td>
<td>{row["信号标的(T-1收盘)"]}</td>
<td>{sig_bf}</td>
<td class="bf-detail">{bf_html}</td>
<td>{ret_color(row["V14日收益"])}</td>
<td class="nav">{row["V14净值"]}</td>
<td>{dd_color(row["V8回撤"])}</td>
<td>{cb_tag}</td>
</tr>''')

rows_str = '\n'.join(rows_html)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V14近一年操作明细</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Microsoft YaHei', sans-serif; background: #f5f5f5; color: #333; padding: 20px; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
h1 {{ text-align: center; font-size: 24px; margin-bottom: 5px; color: #1a1a1a; }}
.subtitle {{ text-align: center; font-size: 14px; color: #888; margin-bottom: 20px; }}
.summary {{ display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }}
.summary-card {{ background: white; padding: 15px 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex: 1; min-width: 150px; text-align: center; }}
.summary-card .label {{ font-size: 12px; color: #888; margin-bottom: 5px; }}
.summary-card .value {{ font-size: 22px; font-weight: bold; }}
.pos {{ color: #e0394b; }}
.neg {{ color: #00897b; }}
.table-wrap {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
thead {{ position: sticky; top: 0; z-index: 10; }}
th {{ background: #2c3e50; color: white; padding: 10px 8px; text-align: center; font-weight: 500; white-space: nowrap; }}
th:first-child {{ text-align: left; padding-left: 15px; }}
td {{ padding: 7px 8px; text-align: center; border-bottom: 1px solid #f0f0f0; white-space: nowrap; }}
td:first-child {{ text-align: left; padding-left: 15px; font-weight: 500; }}
tr:hover {{ background: #f8f9fa; }}
.row-change {{ background: #fff8e1 !important; }}
.row-change:hover {{ background: #fff3cd !important; }}
.row-cb {{ background: #fce4ec !important; }}
.row-cb:hover {{ background: #f8bbd0 !important; }}
.row-cb-release {{ background: #e8f5e9 !important; }}
.row-cb-release:hover {{ background: #c8e6c9 !important; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 500; }}
.tag-bond {{ background: #607d8b; color: white; }}
.tag-stock {{ background: #1565c0; color: white; }}
.tag-empty {{ background: #9e9e9e; color: white; }}
.tag-cb {{ background: #c62828; color: white; }}
.tag-release {{ background: #2e7d32; color: white; }}
.bf-pos {{ color: #e0394b; }}
.bf-neg {{ color: #00897b; }}
.bf-detail {{ font-size: 11px; color: #666; max-width: 350px; white-space: normal; text-align: left; }}
.nav {{ font-family: 'Courier New', monospace; font-size: 12px; }}
.footer {{ text-align: center; margin-top: 15px; font-size: 12px; color: #aaa; }}
.legend {{ display: flex; gap: 15px; margin-bottom: 15px; justify-content: center; font-size: 12px; flex-wrap: wrap; }}
.legend-item {{ display: flex; align-items: center; gap: 5px; }}
.legend-color {{ width: 16px; height: 16px; border-radius: 3px; }}
</style>
</head>
<body>
<div class="container">
<h1>V14 MA20轮动策略 — 近一年操作明细</h1>
<p class="subtitle">{df.iloc[0]["决策日期"]} ~ {df.iloc[-1]["决策日期"]} | 决策bf=(T-1收盘/T-1 MA20)-1 | 收益口径open-to-open | 手续费0.02%</p>

<div class="summary">
<div class="summary-card"><div class="label">总收益</div><div class="value pos">+113.27%</div></div>
<div class="summary-card"><div class="label">交易日数</div><div class="value">243</div></div>
<div class="summary-card"><div class="label">换仓次数</div><div class="value">32</div></div>
<div class="summary-card"><div class="label">熔断触发</div><div class="value neg">11次</div></div>
<div class="summary-card"><div class="label">国债持仓占比</div><div class="value">69.1%</div></div>
</div>

<div class="legend">
<div class="legend-item"><div class="legend-color" style="background:#fff8e1;border:1px solid #ffd54f"></div>换仓日</div>
<div class="legend-item"><div class="legend-color" style="background:#fce4ec;border:1px solid #f48fb1"></div>熔断触发</div>
<div class="legend-item"><div class="legend-color" style="background:#e8f5e9;border:1px solid #81c784"></div>熔断解除</div>
</div>

<div class="table-wrap">
<table>
<thead>
<tr>
<th>决策日期</th>
<th>星期</th>
<th>实际持仓</th>
<th>前日持仓</th>
<th>换仓</th>
<th>信号标的(T-1收盘)</th>
<th>决策bf(T-1)</th>
<th>各成分bf(T-1收盘)</th>
<th>V14日收益</th>
<th>V14净值</th>
<th>V8回撤</th>
<th>熔断状态</th>
</tr>
</thead>
<tbody>
{rows_str}
</tbody>
</table>
</div>
<p class="footer">V14策略：5%/4%组合净值回撤熔断，8股+国债动态标的池 | 数据截至2026-07-22</p>
</div>
</body>
</html>'''

with open('v14_past_year_detail.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f'HTML已生成: v14_past_year_detail.html ({len(html)} chars)')
