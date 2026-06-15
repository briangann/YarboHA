#!/usr/bin/env python3
"""Generate a Yarbo dashboard YAML with a specific device serial number."""

import argparse
import pathlib
import sys

DASHBOARDS = [p.stem for p in pathlib.Path(__file__).parent.glob("*.yaml")]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Yarbo dashboard YAML for a specific device."
    )
    parser.add_argument("serial_number", help="Device serial number (e.g. YB123456)")
    parser.add_argument(
        "-d",
        "--dashboard",
        help=f"Dashboard template to use (default: yarbo-monitoring). Available: {', '.join(sorted(DASHBOARDS))}",
        default="yarbo-monitoring",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file path (default: print to stdout)",
        default=None,
    )
    args = parser.parse_args()

    template = pathlib.Path(__file__).parent / f"{args.dashboard}.yaml"
    if not template.exists():
        print(f"error: {template} not found", file=sys.stderr)
        print(f"available dashboards: {', '.join(sorted(DASHBOARDS))}", file=sys.stderr)
        sys.exit(1)

    yaml = template.read_text().replace("<DEVICE_SN>", args.serial_number.lower())

    if args.output:
        pathlib.Path(args.output).write_text(yaml)
        print(f"Written to {args.output}")
    else:
        print(yaml, end="")


if __name__ == "__main__":
    main()
