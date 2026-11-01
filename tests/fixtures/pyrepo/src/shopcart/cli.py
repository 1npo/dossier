import argparse
import sys

from shopcart import core, store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db")  # @io-cli
    args = parser.parse_args()
    print(core.total([]), store.DB, args.db)  # @io-print
    sys.exit(0)  # @io-exit


if __name__ == "__main__":  # @ep-guard
    main()
