# FIXTURES — hand-calculated expected values (BRAIN). OPS turns these into pytest cases and must NOT adjust the expected values to fit the code.
Convention: qty in units, prices per unit, all times IST same day unless stated. Instrument in all fixtures: NIFTY 24500 CE, expiry 2026-11-04 (a Wednesday-like non-expiry day unless stated). No fees.

F1 simple long: BUY 150@100 10:00; SELL 150@120 10:30.
   -> 1 trip. pnl = 3000. size = 15000. hold = 30 min.

F2 FIFO with partial exits: BUY 100@50 10:00; BUY 100@60 10:05; SELL 150@70 10:20; SELL 50@40 10:40.
   -> 1 trip (flat to flat). pnl = 1500 (FIFO: 100*20 + 50*10 + 50*(40-60) = 2000+500-1000). entry_ts 10:00, exit_ts 10:40, hold 40 min,
      avg entry = 55, avg exit = 62.5, size = 200*55 = 11000.

F3 short first: SELL 75@200 11:00; BUY 75@150 11:20.
   -> 1 trip, direction short. pnl = +3750. hold 20 min. size = 75*200 = 15000.

F4 revenge flag (D1 defaults W=15 min, R=1.0):
   A: BUY 75@100 10:00; SELL 75@80 10:10  -> pnl -1500, size 7500, exit 10:10.
   B: BUY 150@90 10:20; SELL 150@70 10:50 -> pnl -3000, size 13500.
   -> 2 trips. D1 flags B (entered 10 min after losing exit, size 13500 >= 7500). D1 does not flag A. n_flagged = 1 so NOT reported (needs >= 3).
   Variant F4b: B enters at 10:30 (20 min gap) -> not flagged. Variant F4c: B is BUY 75@90 (size 6750 < 7500) -> not flagged.

F5 open position at period end: BUY 75@100 and no closing fill.
   -> 0 trips. Warnings: 1 open/unmatched position.

F6 expiry-day cheap premium (D2 default P=30): instrument expiry date = trade date.
   BUY 75@12 10:00; SELL 75@0 14:00 (expired worthless, recorded as sell at 0.05 is NOT used; use 0).
   -> 1 trip, pnl = -900, flagged by D2 (entry 12 <= 30). Variant F6b: same on a non-expiry date -> not flagged. Variant F6c: entry price 45 -> not flagged.

F7 oversizing (D3 defaults K=2.0, N=20): 12 prior trips each size 10000, then a trip with size 25000.
   -> flagged (25000 > 2.0 * 10000). Trip with size 19000 -> not flagged. With only 5 prior trips (< 10): whole-period median is used and the UI note says so.

F8 loser-holding (D5 default H=2.0, needs >= 3 winners): winners hold 10, 12, 14 min (median 12) ; losers hold 30 min and 20 min.
   -> loser with 30 min is flagged (30 > 2.0*12 = 24); loser with 20 min is not.

F9 multi-leg tag: BUY 75@100 NIFTY 24500 CE 10:00:05 and SELL 75@40 NIFTY 24800 CE 10:00:20, same expiry.
   -> both fills tagged possible_multi_leg (same underlying+expiry, within 60 s, different strikes). Excluded from detectors. Warning count = 1 group.

F10 empty/invalid input: empty file -> clear error message, no crash. Missing required column -> error naming the column.

S1 statistics (completed trips in exit order, pnl in INR): +3000, +1500, -1500, -3000, -900, +3750, -600
   -> trades 7; wins 3; win_rate 3/7 = 42.857%; net_pnl 2250; gross profit 8250; gross loss 6000;
      avg_win 2750; avg_loss 1500; payoff_ratio 2750/1500 = 1.8333; profit_factor 8250/6000 = 1.375;
      expectancy 2250/7 = 321.43; breakeven_win_rate 1/(1+1.8333) = 35.294%;
      cumulative: 3000, 4500, 3000, 0, -900, 2850, 2250 -> max_drawdown 5400 (peak 4500 to trough -900);
      longest_losing_streak 3 (-1500, -3000, -900); longest_winning_streak 2.
S2 no losers: +100, +200 -> win_rate 100%, avg_loss n/a, payoff_ratio n/a, profit_factor n/a, expectancy 150, max_drawdown 0.
S3 no winners: -100, -200 -> win_rate 0%, avg_win 0, payoff_ratio 0.0, profit_factor 0.0, expectancy -150, max_drawdown 300, longest_losing_streak 2.
S4 a trip with pnl exactly 0 counts in trades but in neither wins nor losses. S5 empty trips -> no panel, no crash.
S1 addendum: largest_win 3750; largest_loss 3000. (avg_trade_size has no fixture: test it on F1 alone -> 15000, and on F1+F2 -> (15000+11000)/2 = 13000.)
