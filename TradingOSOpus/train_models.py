#!/usr/bin/env python3
"""train_models.py – Standalone model training script."""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(__file__))
from models.trainer import ModelTrainer

def main():
    p = argparse.ArgumentParser(description="Vietnam Trading Model Trainer")
    p.add_argument("--ticker", default="FPT"); p.add_argument("--horizon", default="1W", choices=["1W","2W","1M","3M","5M"])
    p.add_argument("--start", default="2016-01-01"); p.add_argument("--all", action="store_true")
    args = p.parse_args()
    print(f"\n\U0001f393 Training {args.ticker} from {args.start}")
    trainer = ModelTrainer()
    if args.all: trainer.train_all(ticker=args.ticker)
    else: trainer.train_single(args.ticker, horizon_key=args.horizon, start=args.start)
    print("\n✅ Training complete!")

if __name__ == "__main__": main()
