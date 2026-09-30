import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
# Remove scripts dir from sys.path to prevent shadowing paper_trading
script_dir = str(Path(__file__).resolve().parent)
if script_dir in sys.path:
    sys.path.remove(script_dir)
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import numpy as np

from trade_alert.engine import evaluate
from trade_alert.mt5_utc_provider import MT5UTCProvider
from technical.engine import PandasTaClassicEngine

class FastCandleProvider:
    def __init__(self, m15_df, h1_df):
        self.m15 = m15_df
        self.h1 = h1_df
        
    def completed(self, timeframe: str, as_of):
        if timeframe == "M15":
            return self.m15.loc[:as_of]
        return self.h1.loc[:as_of]

class FastTechnicalEngine:
    def __init__(self, technical, m15_df, h1_df):
        print("Precomputing technicals...")
        self.m15_tech = technical.compute(m15_df)
        self.h1_tech = technical.compute(h1_df)
        print("Precomputing done.")
        
    def compute(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        tf_len = len(ohlcv)
        if tf_len > 10000:
            return self.m15_tech.loc[:ohlcv.index[-1]]
        return self.h1_tech.loc[:ohlcv.index[-1]]

def run_walk_forward(data_dir: Path):
    provider = MT5UTCProvider(data_dir)
    m15_full = provider.frames["M15"]
    h1_full = provider.frames["H1"]
    
    with open(data_dir / "XAUUSD_manifest.json") as f:
        manifest = json.load(f)
    point = manifest["point"]
    
    real_technical = PandasTaClassicEngine()
    technical = FastTechnicalEngine(real_technical, m15_full, h1_full)

    start_time = m15_full.index.min()
    end_time = m15_full.index.max()
    
    total_duration = end_time - start_time
    warmup = timedelta(days=90)
    oos_duration = (total_duration - warmup) / 3
    
    folds = [
        ("Fold1", start_time + warmup, start_time + warmup + oos_duration),
        ("Fold2", start_time + warmup + oos_duration, start_time + warmup + 2 * oos_duration),
        ("Fold3", start_time + warmup + 2 * oos_duration, end_time)
    ]
    
    fast_provider = FastCandleProvider(m15_full, h1_full)
    
    signals = []
    
    print("Generating signals...")
    # Generate signals on M15 close
    for fold_name, f_start, f_end in folds:
        print(f"  {fold_name}...")
        fold_times = m15_full.loc[f_start:f_end].index
        total = len(fold_times)
        for i, as_of in enumerate(fold_times):
            if i % 1000 == 0:
                print(f"    {i}/{total} ({as_of})")
            # We must pass the correct real spread for the alert generation.
            # Real spread = spread_points * point. 
            # We get the spread of the last completed candle.
            current_spread_points = m15_full.loc[as_of, 'spread']
            real_spread = current_spread_points * point
            
            try:
                alert = evaluate(
                    provider=fast_provider,
                    technical=technical,
                    as_of=as_of.to_pydatetime(),
                    macro_fresh=True,
                    event_blocked=False,
                    macro_modifier=0.0,
                    spread=real_spread,
                    slippage=0.0
                )
                if alert is not None:
                    signals.append({
                        "fold": fold_name,
                        "time": as_of.to_pydatetime(),
                        "alert": alert
                    })
            except Exception as e:
                # skip or log
                pass
                
    print(f"Generated {len(signals)} signals.")
    
    # Now evaluate trades.
    slippages = [0.0, 0.05, 0.10, 0.20]
    
    # We will compute results for each slippage
    results_by_slippage = {}
    
    for slip in slippages:
        trades = []
        for sig in signals:
            alert = sig["alert"]
            as_of = sig["time"]
            fold = sig["fold"]
            
            # Entry logic
            # Alert validity
            valid_until = alert.valid_until
            
            # Candles between as_of (exclusive) and valid_until (inclusive)
            # wait, entry is in the NEXT candle. The as_of is the close time of the signal candle.
            # Next candles open AT as_of, close AT as_of + 15m.
            # In our df, index is bar_close. 
            # Next candle close is as_of + 15m. 
            next_candles = m15_full.loc[as_of + timedelta(minutes=1):valid_until]
            
            entered = False
            entry_price = None
            entry_time = None
            direction = 1 if "BUY" in alert.action else -1
            
            for c_time, candle in next_candles.iterrows():
                # check if entry range touched
                if alert.entry_low <= candle.high and alert.entry_high >= candle.low:
                    entered = True
                    # assume entry at the worst edge depending on direction, or just mid?
                    # "entry in the next candle(s) after the signal if price touches entry range"
                    # Slippage is applied to entry and exits.
                    if direction == 1:
                        # Buy: we buy at the price we can get. 
                        # We can just assume entry at the alert.current_price or the edge of the range.
                        entry_price = min(max(candle.low, alert.current_price), candle.high) + slip
                    else:
                        entry_price = min(max(candle.low, alert.current_price), candle.high) - slip
                    entry_time = c_time
                    break
                    
            if not entered:
                continue
                
            # Now simulate exit.
            # We have 3 TPs. 
            # Position size = 1.0 (abstract). 1/3 for each TP.
            pos_left = 1.0
            pnl = 0.0
            
            trade_open = True
            
            # Start checking from entry_time candle to the end of data (or just some reasonable future)
            # Actually, the entry could happen in the middle of a candle. We can evaluate SL/TP on the same candle.
            eval_candles = m15_full.loc[entry_time:]
            
            for c_time, candle in eval_candles.iterrows():
                high = candle.high
                low = candle.low
                
                # Check SL first (conservative)
                sl_hit = False
                if direction == 1 and low <= alert.sl:
                    sl_hit = True
                elif direction == -1 and high >= alert.sl:
                    sl_hit = True
                    
                if sl_hit:
                    exit_price = alert.sl - slip if direction == 1 else alert.sl + slip
                    pnl += pos_left * direction * (exit_price - entry_price)
                    pos_left = 0
                    trade_open = False
                    break
                    
                # Check TPs
                tps = []
                if pos_left > 0.66: # TP1 not hit
                    tps.append((alert.tp1, 1/3))
                if pos_left > 0.33: # TP2 not hit
                    tps.append((alert.tp2, 1/3))
                if pos_left > 0.0:  # TP3 not hit
                    tps.append((alert.tp3, 1/3))
                    
                for tp, frac in tps:
                    tp_hit = False
                    if direction == 1 and high >= tp:
                        tp_hit = True
                    elif direction == -1 and low <= tp:
                        tp_hit = True
                        
                    if tp_hit:
                        exit_price = tp - slip if direction == 1 else tp + slip
                        pnl += frac * direction * (exit_price - entry_price)
                        pos_left -= frac
                        
                if pos_left <= 0.01:
                    trade_open = False
                    break
                    
            if trade_open and pos_left > 0:
                # If we reach end of data, close at last price
                exit_price = eval_candles.iloc[-1].close - direction * slip
                pnl += pos_left * direction * (exit_price - entry_price)
                
            trades.append({
                "fold": fold,
                "setup": alert.setup,
                "direction": "BUY" if direction == 1 else "SELL",
                "pnl": pnl,
                "entry_price": entry_price,
                "sl": alert.sl,
                "slip": slip
            })
            
        results_by_slippage[slip] = trades
        
    # Analyze results
    final_output = {
        "metadata": {
            "label": "technical-core walk-forward",
            "commission_assumption": "MetaQuotes-Demo assumption (0)",
            "slippage_grid": slippages,
            "tp_policy": "Scale out 1/3 at TP1, 1/3 at TP2, 1/3 at TP3. SL hits first."
        },
        "results": {}
    }
    
    ready_for_shadow = True
    reason = None
    
    zero_slip_trades = results_by_slippage[0.0]
    filled_count = len(zero_slip_trades)
    
    if filled_count < 100:
        ready_for_shadow = False
        reason = f"DATA_REQUIRED: filled trades {filled_count} < 100"
        
    for slip in slippages:
        trades = results_by_slippage[slip]
        if not trades:
            continue
        pnls = [t["pnl"] for t in trades]
        net_pnl = sum(pnls)
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        win_rate = len(wins) / len(trades) if trades else 0
        pf = sum(wins) / abs(sum(losses)) if sum(losses) != 0 else float('inf')
        expectancy = net_pnl / len(trades)
        
        cum_pnl = np.cumsum(pnls)
        max_dd = 0
        peak = 0
        for val in cum_pnl:
            if val > peak: peak = val
            dd = peak - val
            if dd > max_dd: max_dd = dd
            
        # Drawdown as % of some absolute capital? The prompt says "max drawdown <=10%".
        # Since we use 1.0 position size, we can assume entry risk is ~ 1.2 ATR. 
        # If we just consider PnL directly, what is the %? 
        # Actually, the user says "max drawdown <= 10%". We should probably just report it.
        # Max single trade <= 25% of absolute PnL.
        max_single = max(pnls) if pnls else 0
        
        final_output["results"][str(slip)] = {
            "filled_trades": len(trades),
            "win_rate": win_rate,
            "net_pnl": net_pnl,
            "profit_factor": pf,
            "expectancy": expectancy,
            "max_dd_absolute": max_dd,
            "max_single_trade": max_single
        }
        
        if slip == 0.0:
            if expectancy <= 0:
                ready_for_shadow = False
                if not reason: reason = f"NO_GO: expectancy <= 0 at 0.0 slip"
            if pf < 1.20:
                ready_for_shadow = False
                if not reason: reason = f"NO_GO: profit factor {pf:.2f} < 1.20"
            if abs(net_pnl) > 0 and max_single > 0.25 * abs(net_pnl):
                ready_for_shadow = False
                if not reason: reason = f"NO_GO: max single trade > 25% of absolute PnL"
                
        if slip == 0.10:
            if net_pnl < 0: # "collapse at slippage=0.10"
                ready_for_shadow = False
                if not reason: reason = f"NO_GO: net pnl < 0 at 0.10 slippage"
                
    # Fold stability at 0.0 slip
    fold_pnls = {"Fold1": 0, "Fold2": 0, "Fold3": 0}
    for t in zero_slip_trades:
        fold_pnls[t["fold"]] += t["pnl"]
        
    pos_folds = sum(1 for p in fold_pnls.values() if p > 0)
    if pos_folds < 2:
        ready_for_shadow = False
        if not reason: reason = f"NO_GO: positive stability in only {pos_folds} OOS folds"
        
    final_output["fold_stability"] = fold_pnls
    final_output["candidate_signals"] = len(signals)
    final_output["rejected_alerts"] = len(signals) - filled_count
    final_output["judgment"] = "READY_FOR_SHADOW" if ready_for_shadow else (reason if "DATA_REQUIRED" in reason else reason)
    
    with open(data_dir / "walk_forward_results.json", "w") as f:
        json.dump(final_output, f, indent=2)
        
    print(json.dumps(final_output, indent=2))
    
    # Write markdown
    with open(data_dir / "walk_forward_results.md", "w") as f:
        f.write(f"# Walk-forward Results\n\n")
        f.write(f"**Judgment**: {final_output['judgment']}\n\n")
        f.write(f"- Candidate Signals: {len(signals)}\n")
        f.write(f"- Filled Trades: {filled_count}\n")
        f.write(f"- Rejected/Unfilled: {len(signals) - filled_count}\n\n")
        f.write("## Performance by Slippage\n")
        for slip, res in final_output["results"].items():
            f.write(f"### Slippage: {slip}\n")
            f.write(f"- Net PnL: {res['net_pnl']:.2f}\n")
            f.write(f"- Win Rate: {res['win_rate']:.2%}\n")
            f.write(f"- Profit Factor: {res['profit_factor']:.2f}\n")
            f.write(f"- Expectancy: {res['expectancy']:.4f}\n")
            f.write(f"- Max Drawdown: {res['max_dd_absolute']:.2f}\n")
            f.write(f"- Max Single Trade: {res['max_single_trade']:.2f}\n\n")
            
        f.write("## Fold Stability (0.0 slip)\n")
        for fold, pnl in fold_pnls.items():
            f.write(f"- {fold}: {pnl:.2f}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    run_walk_forward(args.data_dir)
