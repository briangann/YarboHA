#!/usr/bin/env python3
"""Deploy a Yarbo dashboard YAML to Home Assistant via WebSocket API.

Usage:
    python3 dashboards/deploy_dashboard.py <serial_number> [--dashboard yarbo-active] [--url http://zeus:8123] [--token TOKEN]

The script:
  1. Generates the dashboard YAML by substituting <DEVICE_SN> with the serial number.
  2. Connects to HA via WebSocket.
  3. Creates the dashboard if it doesn't exist, or updates its config if it does.
  4. Prints the dashboard URL on success.
"""

import argparse
import asyncio
import json
import pathlib
import sys
import yaml

try:
    import websockets
except ImportError:
    print(
        "error: websockets not installed. Run: pip install websockets", file=sys.stderr
    )
    sys.exit(1)

DASHBOARDS_DIR = pathlib.Path(__file__).parent
DEFAULT_HA_URL = "http://zeus:8123"
DEFAULT_DASHBOARD = "yarbo-monitoring"


async def _ws_send(ws, msg_id: int, msg_type: str, **kwargs) -> dict:
    payload = {"id": msg_id, "type": msg_type, **kwargs}
    await ws.send(json.dumps(payload))
    while True:
        raw = await ws.recv()
        resp = json.loads(raw)
        if resp.get("id") == msg_id:
            if not resp.get("success", True) and "error" in resp:
                raise RuntimeError(f"HA error: {resp['error']}")
            return resp


async def deploy(ha_url: str, token: str, dashboard: str, sn: str) -> None:
    template = DASHBOARDS_DIR / f"{dashboard}.yaml"
    if not template.exists():
        available = [p.stem for p in DASHBOARDS_DIR.glob("*.yaml")]
        print(
            f"error: {template} not found. Available: {', '.join(sorted(available))}",
            file=sys.stderr,
        )
        sys.exit(1)

    yaml_str = template.read_text().replace("<DEVICE_SN>", sn.lower())
    yaml_config = yaml.safe_load(yaml_str)

    ws_url = (
        ha_url.replace("http://", "ws://").replace("https://", "wss://")
        + "/api/websocket"
    )

    async with websockets.connect(ws_url) as ws:
        # 1. Read auth_required
        hello = json.loads(await ws.recv())
        assert hello["type"] == "auth_required", f"unexpected: {hello}"

        # 2. Authenticate
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth_resp = json.loads(await ws.recv())
        if auth_resp["type"] != "auth_ok":
            print(f"error: authentication failed: {auth_resp}", file=sys.stderr)
            sys.exit(1)

        msg_id = 1

        # 3. List existing dashboards
        resp = await _ws_send(ws, msg_id, "lovelace/dashboards/list")
        msg_id += 1
        existing = {d["url_path"]: d for d in resp.get("result", [])}

        url_path = dashboard
        if url_path in existing:
            # Update config only
            print(f"Dashboard '{url_path}' exists — updating config...")
            await _ws_send(
                ws,
                msg_id,
                "lovelace/config/save",
                url_path=url_path,
                config=yaml_config,
            )
            msg_id += 1
        else:
            # Create dashboard then save config
            print(f"Creating dashboard '{url_path}'...")
            title = yaml_config.get("title", dashboard)
            await _ws_send(
                ws,
                msg_id,
                "lovelace/dashboards/create",
                url_path=url_path,
                title=title,
                icon="mdi:robot-mower",
                show_in_sidebar=True,
                require_admin=False,
            )
            msg_id += 1
            await _ws_send(
                ws,
                msg_id,
                "lovelace/config/save",
                url_path=url_path,
                config=yaml_config,
            )
            msg_id += 1

        print(f"Done. Dashboard available at: {ha_url}/{url_path}")


def main() -> None:
    available = [p.stem for p in DASHBOARDS_DIR.glob("*.yaml")]

    parser = argparse.ArgumentParser(
        description="Deploy a Yarbo dashboard to Home Assistant."
    )
    parser.add_argument(
        "serial_number", help="Device serial number (e.g. 24430102GM0W6421)"
    )
    parser.add_argument(
        "-d",
        "--dashboard",
        default=DEFAULT_DASHBOARD,
        help=f"Dashboard to deploy (default: {DEFAULT_DASHBOARD}). Available: {', '.join(sorted(available))}",
    )
    parser.add_argument(
        "-u",
        "--url",
        default=DEFAULT_HA_URL,
        help=f"Home Assistant URL (default: {DEFAULT_HA_URL})",
    )
    parser.add_argument(
        "-t",
        "--token",
        default=None,
        help="Long-lived access token (or set HA_TOKEN env var)",
    )
    args = parser.parse_args()

    import os

    token = args.token or os.environ.get("HA_TOKEN")
    if not token:
        print("error: provide --token or set HA_TOKEN env var", file=sys.stderr)
        sys.exit(1)

    asyncio.run(deploy(args.url, token, args.dashboard, args.serial_number))


if __name__ == "__main__":
    main()
