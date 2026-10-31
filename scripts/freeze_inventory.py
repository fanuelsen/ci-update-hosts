#!/usr/bin/env python3
"""Freeze the Proxmox inventory for the update step.

Reads what `ansible-inventory --list` prints (JSON, stdin) and writes a static
YAML inventory (stdout) holding host names, their groups and a checked
`ansible_host`: nothing else.

Why not `ansible-inventory --list -y` as it is: the plugin marks what it reads
from Proxmox (VM names, tags, the addresses a guest's agent reports) as unsafe,
so Ansible never renders it as a template. A YAML round trip loses that mark,
and a guest whose agent reported an address like `192.168.{{ lookup(...) }}`
would have it rendered on the runner, which holds the SSH key to every host.
Here an address is either an IP address or the run stops.
"""
import ipaddress
import json
import re
import sys

import yaml

NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.+-]*$")


def freeze(inventory):
    """The minimal static inventory for this `--list` output; ValueError when something in it is not plain."""
    nodes = set(inventory.get("proxmox_nodes", {}).get("hosts", []))
    if not inventory.get("proxmox_all_qemu", {}).get("hosts"):
        # ansible-inventory exits 0 when the plugin fails (a warning, then an
        # empty inventory); a run that updates nothing must not look green.
        raise ValueError("no VM in the inventory: did the Proxmox inventory plugin fail (see its warnings)?")
    hosts = {}
    for name, hostvars in inventory.get("_meta", {}).get("hostvars", {}).items():
        if not NAME.match(name):
            raise ValueError(f"host name {name!r} is not a plain name")
        address = hostvars.get("ansible_host") or ""
        if address == "":
            if name not in nodes:  # a node is never a target, and has no address on purpose
                print(f"{name}: no LAN address (guest agent down?); Ansible will connect by name", file=sys.stderr)
            hosts[name] = {}
            continue
        try:
            ipaddress.ip_address(str(address))
        except ValueError:
            raise ValueError(f"{name}: ansible_host {address!r} is not an IP address") from None
        hosts[name] = {"ansible_host": str(address)}

    groups = {}
    for group, body in inventory.items():
        if group in ("_meta", "all"):
            continue
        if not NAME.match(group):
            raise ValueError(f"group name {group!r} is not a plain name")
        entry = {}
        for member in body.get("hosts", []):
            if not NAME.match(member):
                raise ValueError(f"host name {member!r} is not a plain name")
            entry.setdefault("hosts", {})[member] = {}
        for child in body.get("children", []):
            if not NAME.match(child):
                raise ValueError(f"group name {child!r} is not a plain name")
            entry.setdefault("children", {})[child] = {}
        groups[group] = entry
    return {"all": {"hosts": hosts, "children": groups}}


def main(src=sys.stdin, dst=sys.stdout):
    yaml.safe_dump(freeze(json.load(src)), dst, default_flow_style=False, sort_keys=True)


if __name__ == "__main__":
    try:
        main()
    except ValueError as e:
        sys.exit(f"freeze_inventory: {e}")
