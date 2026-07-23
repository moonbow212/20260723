"""分析2024年历史最高点 vs 近1年最高点熔断版本的差异"""
import pandas as pd
import numpy as np
import os

DATA_DIR = r'C:\Users\wbl\WorkBuddy\2026-07-20-20-22-46\data'
FEE = 0.00005

STOCK_ALL = [2, 3, 5, 6, 7, 8, 11, 12, 13]
BOND = 9
GOLD = 10
names = {2:'创业板50',3:'纳斯达克100',5:'中证500',6:'中证1000',7:'标普500',8:'科创50',
         9:'国债',10:'黄金ETF',11:'中证A500',12:'北证50',13:'中证A50'}

def load_data():
    bond = pd.read_csv(os.path.join(DATA_DIR, '9_国债.csv'), parse_dates=['date'])
    bond = bond.sort_values('date').reset_index(drop=True)
    all_dates = set(bond['date'].dt.date)
    
    stocks = {}
    for sid in STOCK_ALL + [GOLD]:
        path = os.path.join(DATA_DIR, f'{sid}_{names[sid]}.csv')
        df = pd.read_csv(path, parse_dates=['date'])
        df = df.sort_values('date').reset_index(drop=True)
        df = df.drop_duplicates(subset='date', keep='last').reset_index(drop=True)
        df['ma20'] = df['close'].rolling(20, min_periods=20).mean()
        df['ratio'] = df['close'] / df['ma20']
        df['bf'] = df['ratio'] - 1
        stocks[sid] = df
        all_dates &= set(df['date'].dt.date)
    
    # Gold for dynamic safe haven
    gold_df = stocks[GOLD].copy()
    gold_df['gold_ma20'] = gold_df['close'].rolling(20, min_periods=20).mean()
    gold_df['gold_above_ma'] = gold_df['close'] > gold_df['gold_ma20']
    
    cal = bond[bond['date'].dt.date.isin(all_dates)].sort_values('date').reset_index(drop=True)
    return cal, stocks, gold_df, bond

def build_master(cal, stocks, gold_df, bond):
    df = cal[['date']].copy()
    for sid in STOCK_ALL:
        s = stocks[sid][['date','open','close','bf','ratio']].copy()
        s.columns = ['date', f'open_{sid}', f'close_{sid}', f'bf_{sid}', f'ratio_{sid}']
        df = df.merge(s, on='date', how='left')
    # Bond
    b = bond[['date','open','close']].copy()
    b.columns = ['date','open_9','close_9']
    df = df.merge(b, on='date', how='left')
    # Gold
    g = gold_df[['date','open','close','gold_above_ma']].copy()
    g.columns = ['date','open_10','close_10','gold_above_ma']
    df = df.merge(g, on='date', how='left')
    return df

def get_safe_haven(df, idx):
    """获取T日的避险资产"""
    if idx < 0 or pd.isna(df.iloc[idx].get('gold_above_ma', np.nan)):
        return BOND
    return GOLD if df.iloc[idx]['gold_above_ma'] else BOND

def get_signal(df, idx, cb_active, safe_haven_id):
    """获取T日信号"""
    if cb_active:
        return safe_haven_id
    best_bf = -999
    best_sid = safe_haven_id
    for sid in STOCK_ALL:
        bf_val = df.iloc[idx].get(f'bf_{sid}', np.nan)
        ratio_val = df.iloc[idx].get(f'ratio_{sid}', np.nan)
        if pd.notna(bf_val) and pd.notna(ratio_val) and ratio_val >= 1 and bf_val > best_bf:
            best_bf = bf_val
            best_sid = sid
    return best_sid if best_bf > 0 else safe_haven_id

def run_strategy(df, peak_window=None):
    """运行策略，peak_window=None为历史最高点，252为近1年"""
    n = len(df)
    raw_rets = np.zeros(n)
    v8_nav = np.ones(n)
    v14_nav = np.ones(n)
    position = np.full(n, BOND, dtype=int)
    cb_active = False
    safe_haven_ids = np.full(n, BOND, dtype=int)
    
    # First compute V8 (raw strategy without circuit breaker)
    for i in range(1, n):
        # Signal from T-1
        sig_idx = i - 1
        safe_id = get_safe_haven(df, sig_idx)
        safe_haven_ids[i] = safe_id
        sig = get_signal(df, sig_idx, False, safe_id)
        prev_pos = position[i-1] if i > 0 else BOND
        if prev_pos == 0:
            raw_rets[i] = 0
        else:
            prev_open = df.iloc[i-1].get(f'open_{prev_pos}', np.nan)
            curr_open = df.iloc[i].get(f'open_{prev_pos}', np.nan)
            if pd.notna(prev_open) and pd.notna(curr_open) and prev_open > 0:
                raw_rets[i] = (curr_open / prev_open) - 1 - FEE
            else:
                raw_rets[i] = 0
        position[i] = sig
        v8_nav[i] = v8_nav[i-1] * (1 + raw_rets[i])
    
    # Now compute V14 with circuit breaker
    v14_nav2 = np.ones(n)
    cb_states = np.zeros(n, dtype=bool)
    position2 = np.full(n, BOND, dtype=int)
    
    for i in range(1, n):
        sig_idx = i - 1
        safe_id = safe_haven_ids[i]
        
        # Compute drawdown
        if peak_window is None:
            peak = v8_nav[:i+1].max()
        else:
            start_idx = max(0, i - peak_window + 1)
            peak = v8_nav[start_idx:i+1].max()
        
        dd = v8_nav[i] / peak - 1 if peak > 0 else 0
        
        if cb_active:
            if dd >= -0.04:
                cb_active = False
        else:
            if dd < -0.05:
                cb_active = True
        
        cb_states[i] = cb_active
        sig = get_signal(df, sig_idx, cb_active, safe_id)
        
        prev_pos = position2[i-1] if i > 0 else BOND
        if prev_pos == 0:
            ret = 0
        else:
            prev_open = df.iloc[i-1].get(f'open_{prev_pos}', np.nan)
            curr_open = df.iloc[i].get(f'open_{prev_pos}', np.nan)
            if pd.notna(prev_open) and pd.notna(curr_open) and prev_open > 0:
                ret = (curr_open / prev_open) - 1 - FEE
            else:
                ret = 0
        v14_nav2[i] = v14_nav2[i-1] * (1 + ret)
        position2[i] = sig
    
    return v8_nav, v14_nav2, cb_states, position2, safe_haven_ids

def main():
    cal, stocks, gold_df, bond = load_data()
    df = build_master(cal, stocks, gold_df, bond)
    
    # Run both versions
    v8_nav, v14_alltime, cb_alltime, pos_alltime, sh_alltime = run_strategy(df, peak_window=None)
    _, v14_1y, cb_1y, pos_1y, sh_1y = run_strategy(df, peak_window=252)
    
    # Filter to 2024
    df['date'] = pd.to_datetime(df['date'])
    mask_2024 = df['date'].dt.year == 2024
    idx_2024 = np.where(mask_2024)[0]
    
    if len(idx_2024) == 0:
        print("No 2024 data found!")
        return
    
    # Find first trading day of 2024
    start_2024 = idx_2024[0]
    
    # Year start/end nav
    nav_start_at = v14_alltime[start_2024 - 1] if start_2024 > 0 else 1
    nav_end_at = v14_alltime[idx_2024[-1]]
    ret_at = (nav_end_at / nav_start_at - 1) * 100
    
    nav_start_1y = v14_1y[start_2024 - 1] if start_2024 > 0 else 1
    nav_end_1y = v14_1y[idx_2024[-1]]
    ret_1y = (nav_end_1y / nav_start_1y - 1) * 100
    
    print(f"=== 2024年收益对比 ===")
    print(f"历史最高点版: {ret_at:.2f}% (净值 {nav_start_at:.2f} -> {nav_end_at:.2f})")
    print(f"近1年最高点版: {ret_1y:.2f}% (净值 {nav_start_1y:.2f} -> {nav_end_1y:.2f})")
    print(f"差异: {ret_1y - ret_at:.2f}%")
    print()
    
    # Find days where positions differ
    print(f"=== 2024年持仓差异明细 ===")
    print(f"{'日期':<12} {'V8净值':>10} {'历史峰':>10} {'1年峰':>10} {'历史DD':>8} {'1年DD':>8} {'历史CB':>6} {'1年CB':>6} {'历史持仓':>10} {'1年持仓':>10} {'差异日收益':>10}")
    
    diff_days = []
    for i in idx_2024:
        date_str = df.iloc[i]['date'].strftime('%Y-%m-%d')
        v8 = v8_nav[i]
        
        peak_at = v8_nav[:i+1].max()
        peak_1y = v8_nav[max(0,i-251):i+1].max()
        dd_at = v8 / peak_at - 1
        dd_1y = v8 / peak_1y - 1
        
        cb_at = cb_alltime[i]
        cb_1y_state = cb_1y[i]
        
        pos_at = pos_alltime[i]
        pos_1y_val = pos_1y[i]
        
        name_at = names.get(pos_at, str(pos_at))
        name_1y = names.get(pos_1y_val, str(pos_1y_val))
        
        # Daily return difference
        if i > 0:
            prev_pos_at = pos_alltime[i-1]
            prev_pos_1y = pos_1y[i-1]
            
            if prev_pos_at > 0:
                prev_open = df.iloc[i-1].get(f'open_{prev_pos_at}', np.nan)
                curr_open = df.iloc[i].get(f'open_{prev_pos_at}', np.nan)
                ret_at_daily = ((curr_open / prev_open - 1 - FEE) * 100) if pd.notna(prev_open) and pd.notna(curr_open) and prev_open > 0 else 0
            else:
                ret_at_daily = 0
                
            if prev_pos_1y > 0:
                prev_open = df.iloc[i-1].get(f'open_{prev_pos_1y}', np.nan)
                curr_open = df.iloc[i].get(f'open_{prev_pos_1y}', np.nan)
                ret_1y_daily = ((curr_open / prev_open - 1 - FEE) * 100) if pd.notna(prev_open) and pd.notna(curr_open) and prev_open > 0 else 0
            else:
                ret_1y_daily = 0
        else:
            ret_at_daily = 0
            ret_1y_daily = 0
        
        if pos_at != pos_1y_val or cb_at != cb_1y_state:
            diff_days.append(i)
            print(f"{date_str:<12} {v8:>10.2f} {peak_at:>10.2f} {peak_1y:>10.2f} {dd_at*100:>7.2f}% {dd_1y*100:>7.2f}% {'ON' if cb_at else 'OFF':>6} {'ON' if cb_1y_state else 'OFF':>6} {name_at:>10} {name_1y:>10} {ret_at_daily:>9.2f}%/{ret_1y_daily:>7.2f}%")
    
    print(f"\n总差异天数: {len(diff_days)}")
    
    # Also show CB state transitions for both versions
    print(f"\n=== 2024年熔断状态变化 ===")
    print(f"--- 历史最高点版 ---")
    prev_cb = cb_alltime[start_2024 - 1] if start_2024 > 0 else False
    for i in idx_2024:
        if cb_alltime[i] != prev_cb:
            date_str = df.iloc[i]['date'].strftime('%Y-%m-%d')
            v8 = v8_nav[i]
            peak_at = v8_nav[:i+1].max()
            dd_at = v8 / peak_at - 1
            action = "触发熔断→避险" if cb_alltime[i] else "解除熔断→选股"
            print(f"  {date_str}: {action} (V8={v8:.2f}, 历史峰={peak_at:.2f}, DD={dd_at*100:.2f}%)")
            prev_cb = cb_alltime[i]
    
    print(f"--- 近1年最高点版 ---")
    prev_cb = cb_1y[start_2024 - 1] if start_2024 > 0 else False
    for i in idx_2024:
        if cb_1y[i] != prev_cb:
            date_str = df.iloc[i]['date'].strftime('%Y-%m-%d')
            v8 = v8_nav[i]
            peak_1y = v8_nav[max(0,i-251):i+1].max()
            dd_1y = v8 / peak_1y - 1
            action = "触发熔断→避险" if cb_1y[i] else "解除熔断→选股"
            print(f"  {date_str}: {action} (V8={v8:.2f}, 1年峰={peak_1y:.2f}, DD={dd_1y*100:.2f}%)")
            prev_cb = cb_1y[i]
    
    # Summary stats
    print(f"\n=== 2024年持仓占比 ===")
    for version_name, positions in [("历史最高点", pos_alltime), ("近1年最高点", pos_1y)]:
        pos_list = [positions[i] for i in idx_2024]
        from collections import Counter
        cnt = Counter(pos_list)
        total = len(pos_list)
        print(f"\n{version_name}版:")
        for pid, count in cnt.most_common():
            pct = count / total * 100
            print(f"  {names.get(pid, str(pid))}: {count}天 ({pct:.1f}%)")

if __name__ == '__main__':
    main()
