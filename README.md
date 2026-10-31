# CI Update Hosts

Daily package updates for every VM in the homelab, run by Woodpecker CI:
`apk upgrade` on Alpine, `apt dist-upgrade` on Debian.

The hosts are discovered **dynamically from Proxmox** (the same inventory as
`iac-baseline`): every running QEMU VM, so a new VM is updated from its first
day and there is no host list to maintain. Before this, the inventory was a
Woodpecker secret, and the three hosts missing from it went unpatched for
months.

## What a run does

For each host, `playbooks/update.yml`:

1. Upgrades every package: `community.general.apk` (Alpine) or
   `ansible.builtin.apt` with `upgrade: dist` + `autoremove` (Debian).
2. Compares the running kernel with the newest one installed and prints
   `reboot needed: running X, installed Y` for a host that differs.
3. Reboots that host **only** if its VM is tagged `autoreboot` in Proxmox, and
   never the CI runner (`chipchopdeploy`: the reboot would kill the pipeline
   doing it; reboot it by hand).

## Proxmox tags

| tag | effect |
|---|---|
| `nobaseline` | left out (an appliance, or a VM CI cannot reach), as in `iac-baseline` |
| `noupdate` | left out: reachable, but its packages are not CI's to touch |
| `autoreboot` | rebooted by the run when a newer kernel is installed than running |

## Pipeline

`.woodpecker.yml` runs on push to `main`, by hand, and from the `Daily Run`
cron (06:07 UTC):

1. **Resolve the fleet from Proxmox**: `ansible-inventory` with the
   `community.proxmox.proxmox` plugin (read-only `PVEAuditor` token from the
   `proxmox_token_secret` secret, TLS verified against the pinned
   `inventory/pve-api.pem`), printed as a graph and frozen to
   `inventory/hosts.yml` by `scripts/freeze_inventory.py`: host names, groups
   and a checked IP address, nothing else. The plugin marks what Proxmox and
   the guests' agents report as unsafe (never rendered as a template); a plain
   YAML round trip would lose that, and the runner holds the SSH key to every
   host. A `plugin-ansible` step cannot mix `settings:` and `environment:`, so
   this is the only step that holds the token.
2. **Update every host**: `woodpeckerci/plugin-ansible` runs the playbook as
   user `ansible` with `become` against the frozen inventory.
3. **Send Notification**: build status to Discord.

The runner updates itself like any other host. That works because its own
`ansible` key is the one `iac-baseline` leaves without a `from=` restriction
(SSH to its own LAN IP comes from the docker bridge); keep it that way.

### Secrets

| secret | scope | what |
|---|---|---|
| `proxmox_token_secret` | global | read-only PVE API token secret (`ci@pve!inventory`) |
| `ansible_private_key` | global | SSH key for the `ansible` user |
| `webhook_id` / `webhook_token` | global | Discord notifications |

The old repo secret `hosts` (the static inventory) is no longer read.

### The pinned API certificate

`inventory/pve-api.pem` is the node's API certificate (self-signed by the PVE
cluster CA, which lacks a keyUsage extension and so fails today's strict
verification; the leaf is pinned instead). It expires 2027-10-09. When PVE
renews it, the resolve step fails with an SSL error until the file is refreshed:

```bash
openssl s_client -connect proximusmaximus.sublog.org:8006 </dev/null 2>/dev/null \
  | openssl x509 > inventory/pve-api.pem
```

An ACME certificate on the node would make the pin unnecessary.

## Running it by hand

```bash
ansible-galaxy collection install -r requirements.yml
export PROXMOX_TOKEN_SECRET=...          # the token's value
export ANSIBLE_INVENTORY_ENABLED=community.proxmox.proxmox
export REQUESTS_CA_BUNDLE=inventory/pve-api.pem

ansible-inventory -i inventory/proxmox.yml --graph             # who is in
ansible-playbook -i inventory/proxmox.yml playbooks/update.yml \
  -u ansible --become --check                                  # preview
ansible-playbook -i inventory/proxmox.yml playbooks/update.yml \
  -u ansible --become --limit pihole01                         # one host
```

## Structure

```
├── .woodpecker.yml               # pipeline: resolve fleet, update, notify
├── inventory/proxmox.yml         # Proxmox dynamic inventory (hosts.yml: frozen by a run, ignored)
├── inventory/pve-api.pem         # the pinned PVE API certificate
├── playbooks/update.yml          # the update play
├── scripts/freeze_inventory.py   # the frozen inventory: names, groups, checked addresses
├── tests/                        # python3 -m unittest discover -s tests
└── requirements.yml              # community.proxmox, community.general
```
