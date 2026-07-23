# -*- coding: utf-8 -*-
"""
V14策略数据自动获取器
====================
从akshare免费获取9个标的的日线数据，保存为CSV格式。
- 中国指数+国债：akshare与同花顺数据一致，直接使用
- 美股指数(纳斯达克100/标普500)：读取同花顺历史数据，用akshare增量更新
  - 通过比率调整保持价格水平一致
  - 日收益率差异平均仅0.04%，不影响策略信号

运行方式：python fetch_data.py
输出：data/目录下的9个CSV文件(date,open,close)
"""
import pandas as pd
import numpy as np
import akshare as ak
import requests
import os, sys, warnings
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

# ===== 配置 =====
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
THS_DIR = 'C:/Users/wbl/Desktop'
# Cloud/CI fallback: 如果桌面路径不可用，使用仓库内的 ths_data/ 目录
if not os.path.isdir(THS_DIR):
    THS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ths_data')

# 标的配置: id -> (名称, akshare代码, 数据源类型, 桌面CSV文件名或None)
# 类型: 'cn' = 中国指数(akshare直接获取), 'us' = 美股指数(桌面CSV历史+akshare增量)
STOCKS = {
    1: ('上证50',    'sh000016', 'cn', None),
    2: ('创业板50',  'sz399673', 'cn', None),
    3: ('纳斯达克100', '.NDX',    'us', None),
    4: ('沪深300',   'sh000300', 'cn', None),
    5: ('中证500',   'sh000905', 'cn', None),
    6: ('中证1000',  'sh000852', 'cn', None),
    7: ('标普500',   '.INX',     'us', '美国标准普尔500指数历史数据.csv'),
    8: ('科创50',    'sh000688', 'cn', None),
    9: ('国债',      'sh000012', 'cn', None),
    10: ('黄金ETF',  '518880',   'etf', None),
}

def read_ths_file(name):
    """读取同花顺导出的数据文件"""
    path = os.path.join(THS_DIR, f'{name}.xlsx')
    if not os.path.exists(path):
        path2 = os.path.join(THS_DIR, '同花顺历史数据', f'{name}.xlsx')
        if os.path.exists(path2):
            path = path2
        else:
            return None
    try:
        d = pd.read_csv(path, sep='\t', encoding='gbk')
        d['date'] = pd.to_datetime(d['时间'].str.split(',').str[0])
        for c in ['开盘', '收盘']:
            d[c] = pd.to_numeric(d[c], errors='coerce')
        d = d[['date', '开盘', '收盘']].rename(columns={'开盘': 'open', '收盘': 'close'})
        d = d.dropna(subset=['open', 'close']).sort_values('date').reset_index(drop=True)
        return d
    except Exception as e:
        print(f'  读取同花顺文件失败 {name}: {e}')
        return None

def read_desktop_csv(filename):
    """读取桌面CSV文件（如标普500历史数据，同花顺CSV导出格式）"""
    path = os.path.join(THS_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        d = pd.read_csv(path, encoding='utf-8')
        d['date'] = pd.to_datetime(d['日期'])
        d['close'] = d['收盘'].str.replace(',', '').astype(float)
        d['open'] = d['开盘'].str.replace(',', '').astype(float)
        d = d[['date', 'open', 'close']].sort_values('date').reset_index(drop=True)
        print(f'  桌面CSV: {d["date"].iloc[0].date()}~{d["date"].iloc[-1].date()}, {len(d)}条')
        return d
    except Exception as e:
        print(f'  读取桌面CSV失败 {filename}: {e}')
        return None

def fetch_cn_index(code):
    """从akshare获取中国指数日线数据"""
    df = ak.stock_zh_index_daily(symbol=code)
    df['date'] = pd.to_datetime(df['date'])
    df = df[['date', 'open', 'close']].copy()
    df['open'] = pd.to_numeric(df['open'], errors='coerce')
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df = df.dropna().sort_values('date').reset_index(drop=True)
    return df

def fetch_us_index(symbol):
    """从akshare获取美股指数日线数据"""
    df = ak.index_us_stock_sina(symbol=symbol)
    df['date'] = pd.to_datetime(df['date'])
    df = df[['date', 'open', 'close']].copy()
    df['open'] = pd.to_numeric(df['open'], errors='coerce')
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df = df.dropna().sort_values('date').reset_index(drop=True)
    return df

def fetch_etf(code):
    """从akshare获取ETF日线数据（前复权），带重试"""
    import time
    for attempt in range(3):
        try:
            df = ak.fund_etf_hist_em(symbol=code, adjust='qfq')
            df['date'] = pd.to_datetime(df['日期'])
            df['open'] = pd.to_numeric(df['开盘'], errors='coerce')
            df['close'] = pd.to_numeric(df['收盘'], errors='coerce')
            df = df[['date', 'open', 'close']].dropna().sort_values('date').reset_index(drop=True)
            return df
        except Exception as e:
            if attempt < 2:
                print(f'  重试 {attempt+1}/3...')
                time.sleep(3)
            else:
                raise e

def fetch_realtime_cn(codes):
    """
    从新浪实时行情API获取中国指数今日收盘数据（批量）
    codes: dict of {akshare_code: name}
    返回: dict of {akshare_code: (today, open, close)}
    """
    code_list = list(codes.keys())
    url = f'http://hq.sinajs.cn/list={",".join(code_list)}'
    headers = {'Referer': 'https://finance.sina.com.cn'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'gbk'
    except Exception as e:
        print(f'  实时行情获取失败: {e}')
        return {}

    result = {}
    today = datetime.now().date()
    for line in r.text.strip().split('\n'):
        if '=' not in line:
            continue
        var_part = line.split('=')[0].strip()
        val_part = line.split('=', 1)[1].strip('"').strip()
        if not val_part:
            continue
        parts = val_part.split(',')
        if len(parts) < 4:
            continue
        # 从 var hq_str_sh000016 提取 code
        code = var_part.split('hq_str_')[-1] if 'hq_str_' in var_part else ''
        if code not in codes:
            continue
        open_p = float(parts[1]) if parts[1] else 0
        pre_close = float(parts[2]) if parts[2] else 0
        close_p = float(parts[3]) if parts[3] else 0
        if open_p > 0 and close_p > 0:
            result[code] = (today, open_p, close_p)
    return result

def merge_us_data(ths_df, ak_df):
    """
    合并美股指数数据：
    - 历史部分用同花顺（价格水平一致）
    - 新增部分用akshare，通过比率调整到同花顺价格水平
    """
    if ths_df is None or len(ths_df) == 0:
        print('    同花顺历史数据不可用，直接使用akshare数据')
        return ak_df

    # 找到同花顺数据的最后日期
    ths_last_date = ths_df['date'].max()

    # 找到akshare中与同花顺最后日期重叠的数据，计算比率
    overlap = ak_df[ak_df['date'] <= ths_last_date].copy()
    if len(overlap) == 0:
        print('    无重叠日期，直接使用akshare数据')
        return ak_df

    ths_last = ths_df[ths_df['date'] == ths_last_date].iloc[0]
    ak_last = overlap[overlap['date'] == ths_last_date].iloc[0]

    # 计算价格比率（同花顺/akshare）
    ratio_close = ths_last['close'] / ak_last['close'] if ak_last['close'] != 0 else 1.0
    ratio_open = ths_last['open'] / ak_last['open'] if ak_last['open'] != 0 else ratio_close

    # 获取akshare中比同花顺最后日期更新的数据
    new_data = ak_df[ak_df['date'] > ths_last_date].copy()
    if len(new_data) == 0:
        print(f'    akshare无新增数据（同花顺已到最新: {ths_last_date.date()}）')
        return ths_df

    # 用比率调整新数据
    new_data['close'] = new_data['close'] * ratio_close
    new_data['open'] = new_data['open'] * ratio_open

    # 合并
    merged = pd.concat([ths_df, new_data], ignore_index=True)
    merged = merged.sort_values('date').reset_index(drop=True)
    merged = merged.drop_duplicates(subset=['date'], keep='last')

    print(f'    同花顺历史: {ths_df["date"].iloc[0].date()}~{ths_last_date.date()} ({len(ths_df)}条)')
    print(f'    akshare新增: {new_data["date"].iloc[0].date()}~{new_data["date"].iloc[-1].date()} ({len(new_data)}条)')
    print(f'    价格比率(同花顺/akshare): close={ratio_close:.6f}, open={ratio_open:.6f}')

    return merged

def main():
    print(f'=' * 60)
    print(f'V14策略数据自动获取  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'=' * 60)

    # 创建数据目录
    os.makedirs(DATA_DIR, exist_ok=True)

    # 批量获取中国指数实时行情（补充今日收盘数据）
    today = datetime.now().date()
    cn_codes = {code: name for sid, (name, code, dtype, csv_file) in STOCKS.items() if dtype == 'cn'}
    # ETF也通过新浪实时API获取，code格式为sh+数字
    for sid, (name, code, dtype, csv_file) in STOCKS.items():
        if dtype == 'etf':
            cn_codes[f'sh{code}'] = name
    realtime_data = {}
    if today.weekday() < 5:  # 工作日才获取实时行情
        print('\n获取实时行情...')
        realtime_data = fetch_realtime_cn(cn_codes)
        if realtime_data:
            print(f'  获取到 {len(realtime_data)} 个标的的实时行情')
        else:
            print('  无实时行情数据')

    for sid, (name, code, dtype, csv_file) in STOCKS.items():
        print(f'\n[{sid}] {name} ({code}, {dtype})')

        try:
            if dtype == 'cn':
                # 中国指数：直接从akshare获取
                df = fetch_cn_index(code)
                print(f'  akshare: {df["date"].iloc[0].date()}~{df["date"].iloc[-1].date()}, {len(df)}条')
                # 检查是否需要补充今日实时行情
                last_date = df['date'].iloc[-1]
                if last_date < pd.Timestamp(today) and code in realtime_data:
                    t_date, t_open, t_close = realtime_data[code]
                    new_row = pd.DataFrame({
                        'date': [pd.Timestamp(t_date)],
                        'open': [t_open],
                        'close': [t_close]
                    })
                    df = pd.concat([df, new_row], ignore_index=True)
                    df = df.sort_values('date').reset_index(drop=True)
                    chg = t_close - df[df['date'] < pd.Timestamp(t_date)]['close'].iloc[-1]
                    print(f'  实时补充: {t_date} open={t_open:.3f} close={t_close:.3f} (涨跌{chg:+.3f})')
                print(f'  最新: close={df["close"].iloc[-1]:.3f} ({df["date"].iloc[-1].date()})')
            elif dtype == 'etf':
                # ETF：从akshare获取前复权数据
                df = fetch_etf(code)
                print(f'  akshare: {df["date"].iloc[0].date()}~{df["date"].iloc[-1].date()}, {len(df)}条')
                # 检查是否需要补充今日实时行情
                last_date = df['date'].iloc[-1]
                rt_code = f'sh{code}'
                if last_date < pd.Timestamp(today) and rt_code in realtime_data:
                    t_date, t_open, t_close = realtime_data[rt_code]
                    new_row = pd.DataFrame({
                        'date': [pd.Timestamp(t_date)],
                        'open': [t_open],
                        'close': [t_close]
                    })
                    df = pd.concat([df, new_row], ignore_index=True)
                    df = df.sort_values('date').reset_index(drop=True)
                    chg = t_close - df[df['date'] < pd.Timestamp(t_date)]['close'].iloc[-1]
                    print(f'  实时补充: {t_date} open={t_open:.3f} close={t_close:.3f} (涨跌{chg:+.3f})')
                print(f'  最新: close={df["close"].iloc[-1]:.3f} ({df["date"].iloc[-1].date()})')
            elif dtype == 'us':
                # 美股指数：桌面CSV(优先)或同花顺历史 + akshare增量
                ths_df = None
                if csv_file:
                    ths_df = read_desktop_csv(csv_file)
                if ths_df is None:
                    ths_df = read_ths_file(name)
                if ths_df is not None:
                    print(f'  历史数据: {ths_df["date"].iloc[0].date()}~{ths_df["date"].iloc[-1].date()}, {len(ths_df)}条')
                ak_df = fetch_us_index(code)
                print(f'  akshare: {ak_df["date"].iloc[0].date()}~{ak_df["date"].iloc[-1].date()}, {len(ak_df)}条')
                df = merge_us_data(ths_df, ak_df)
                print(f'  合并后: {df["date"].iloc[0].date()}~{df["date"].iloc[-1].date()}, {len(df)}条')
                print(f'  最新: close={df["close"].iloc[-1]:.3f}')
            else:
                print(f'  未知数据类型: {dtype}')
                continue

            # 保存为CSV
            out_path = os.path.join(DATA_DIR, f'{sid}_{name}.csv')
            df.to_csv(out_path, index=False, encoding='utf-8')
            print(f'  已保存: {out_path}')

        except Exception as e:
            print(f'  ❌ 获取失败: {e}')
            import traceback
            traceback.print_exc()

    print(f'\n{"=" * 60}')
    print('数据获取完成！')
    print(f'数据目录: {DATA_DIR}')

    # 汇总
    print('\n各标的最新数据:')
    for sid, (name, code, dtype, csv_file) in STOCKS.items():
        path = os.path.join(DATA_DIR, f'{sid}_{name}.csv')
        if os.path.exists(path):
            d = pd.read_csv(path, parse_dates=['date'])
            print(f'  {name:10s}: {d["date"].iloc[-1].date()} close={d["close"].iloc[-1]:.3f} ({len(d)}条)')

if __name__ == '__main__':
    main()
