import argparse
from .agent import run_agent


def main():
    parser = argparse.ArgumentParser(description="ASHRE buying agent")
    parser.add_argument("request", help="What do you want to buy?")
    parser.add_argument(
        "--vendor",
        default="http://localhost:8000",
        help="Vendor server base URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    result = run_agent(args.request, args.vendor)
    print(result)
