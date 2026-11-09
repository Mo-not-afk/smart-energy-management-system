import argparse
import json
from .core import Tariff, analyze, load_csv, synthetic_readings

def main():
    parser = argparse.ArgumentParser(description="Analyze meter CSV data or reproducible simulated readings")
    parser.add_argument("--csv")
    parser.add_argument("--tariff", type=float, default=0.30)
    parser.add_argument("--generate", help="write deterministic simulated CSV to this path")
    args = parser.parse_args()
    frame = load_csv(args.csv) if args.csv else synthetic_readings()
    if args.generate:
        frame.to_csv(args.generate, index=False)
    print(json.dumps(analyze(frame, Tariff(args.tariff)), indent=2))

if __name__ == "__main__": main()
