
import sys
import os

# Ensure the 'src' directory is in the Python path
# This script should be in the 'TradingOS' directory
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    from tradingos.engines.profiler_service import ProfilerService
    from tradingos.data.schemas import ProfilerRequest

    # SRS requires portfolio_value for initialization
    svc = ProfilerService(portfolio_value=300_000_000)

    print('Ticker,Action,Confidence,Entry,SL,TP1,TP2')
    for t in ['EVE', 'HCC']:
        try:
            p = svc.run(ProfilerRequest(ticker=t, mode='FULL'))
            print(f'{t},{p.action},{p.confidence},{p.entry_price:.0f},{p.stop_loss:.0f},{p.tp1:.0f},{p.tp2:.0f}')
        except Exception as e:
            print(f'Error processing {t}: {e}', file=sys.stderr)

except ModuleNotFoundError:
    print("Fatal: Could not find 'tradingos' module. Make sure PYTHONPATH is set correctly or run from the 'TradingOS' directory.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"An unexpected error occurred: {e}", file=sys.stderr)
    sys.exit(1)
