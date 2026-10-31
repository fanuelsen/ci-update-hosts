"""The frozen inventory the update step reads: names, groups and a checked address, nothing else."""
import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "freeze_inventory.py"
spec = importlib.util.spec_from_file_location("freeze_inventory", SCRIPT)
freeze_inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freeze_inventory)


def listing(**hostvars):
    """What `ansible-inventory --list` prints for the Proxmox plugin, for these hosts (name -> ansible_host)."""
    return {
        "_meta": {"hostvars": {
            **{name: {"ansible_host": address, "proxmox_name": name, "proxmox_tags_parsed": ["alpine"],
                      "proxmox_agent_interfaces": [{"name": "eth0", "ip-addresses": [f"{address}/24"]}]}
               for name, address in hostvars.items()},
            # The node itself: want_proxmox_nodes_ansible_host is false, so no address.
            "proximusmaximus": {"proxmox_node": "proximusmaximus"}}},
        "all": {"children": ["proxmox_all_qemu", "proxmox_all_running", "tag_alpine", "ungrouped"]},
        "proxmox_all_qemu": {"hosts": sorted(hostvars)},
        "proxmox_all_running": {"hosts": sorted(hostvars)},
        "tag_alpine": {"hosts": sorted(hostvars), "vars": {"proxmox_tag": "alpine"}},
        "ungrouped": {},
        "proxmox_nodes": {"hosts": ["proximusmaximus"]},
    }


class FreezeTest(unittest.TestCase):
    def test_keeps_names_groups_and_the_address_only(self):
        out = freeze_inventory.freeze(listing(pihole01="192.168.30.106", copyparty="192.168.30.108"))
        self.assertEqual(out, {"all": {
            "hosts": {"pihole01": {"ansible_host": "192.168.30.106"}, "copyparty": {"ansible_host": "192.168.30.108"},
                      "proximusmaximus": {}},
            "children": {
                "proxmox_all_qemu": {"hosts": {"copyparty": {}, "pihole01": {}}},
                "proxmox_all_running": {"hosts": {"copyparty": {}, "pihole01": {}}},
                "tag_alpine": {"hosts": {"copyparty": {}, "pihole01": {}}},
                "ungrouped": {},
                "proxmox_nodes": {"hosts": {"proximusmaximus": {}}},
            }}})

    def test_unwraps_an_address_the_plugin_marked_unsafe(self):
        # `--list` prints a value the plugin marked unsafe as {"__ansible_unsafe": value} (run 540 saw this
        # for the portal VM only); the mark is the point of the check, the value is what we validate.
        src = listing(pihole01="192.168.30.106")
        src["_meta"]["hostvars"]["pihole01"]["ansible_host"] = {"__ansible_unsafe": "192.168.30.106"}
        out = freeze_inventory.freeze(src)
        self.assertEqual(out["all"]["hosts"]["pihole01"], {"ansible_host": "192.168.30.106"})
        src["_meta"]["hostvars"]["pihole01"]["ansible_host"] = {"__ansible_unsafe": "{{ 1 + 1 }}"}
        with self.assertRaises(ValueError):
            freeze_inventory.freeze(src)

    def test_refuses_an_address_that_is_not_an_ip_address(self):
        # A guest's agent reports its addresses; the plugin marks them unsafe, a YAML round trip would not.
        with self.assertRaises(ValueError) as e:
            freeze_inventory.freeze(listing(pihole01="192.168.{{ lookup('pipe', 'id') }}"))
        self.assertIn("pihole01", str(e.exception))

    def test_a_host_without_an_address_stays_in_so_the_play_reports_it_unreachable(self):
        err = io.StringIO()
        with redirect_stderr(err):
            out = freeze_inventory.freeze(listing(pihole01=""))
        self.assertEqual(out["all"]["hosts"], {"pihole01": {}, "proximusmaximus": {}})
        self.assertIn("pihole01", err.getvalue())

    def test_the_node_has_no_address_and_gets_no_warning(self):
        err = io.StringIO()
        with redirect_stderr(err):
            freeze_inventory.freeze(listing(pihole01="192.168.30.106"))
        self.assertEqual(err.getvalue(), "")

    def test_refuses_an_inventory_without_vms(self):
        # ansible-inventory exits 0 when the plugin fails (a warning, an empty inventory); the run must not.
        with self.assertRaises(ValueError) as e:
            freeze_inventory.freeze(listing())
        self.assertIn("no VM", str(e.exception))

    def test_refuses_a_host_name_that_is_not_a_plain_name(self):
        with self.assertRaises(ValueError):
            freeze_inventory.freeze(listing(**{"a b{{": "192.168.30.1"}))

    def test_main_reads_json_and_writes_yaml(self):
        src = json.dumps(listing(pihole01="192.168.30.106"))
        out = io.StringIO()
        freeze_inventory.main(io.StringIO(src), out)
        self.assertEqual(yaml.safe_load(out.getvalue())["all"]["hosts"],
                         {"pihole01": {"ansible_host": "192.168.30.106"}, "proximusmaximus": {}})
        for proxmox_data in ("proxmox_name", "proxmox_tags_parsed", "ip-addresses", "eth0"):
            self.assertNotIn(proxmox_data, out.getvalue())


if __name__ == "__main__":
    unittest.main()
