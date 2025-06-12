# CI Update Hosts

Ansible automation for updating remote Alpine Linux hosts via CI/CD pipelines.

## Overview

This repository contains Ansible playbooks designed to automate package management tasks on Alpine Linux systems. It's structured for use in CI/CD environments to ensure remote hosts stay updated with the latest packages.

## Prerequisites

### For Manual Execution
- Ansible installed on the control machine
- SSH access to target Alpine Linux hosts
- Ansible inventory file configured with target hosts

### For CI/CD Pipeline
- Woodpecker CI server configured
- Required secrets configured in CI environment

## Installation

1. Clone this repository
2. Install required Ansible collections:
   ```bash
   ansible-galaxy collection install -r requirements.yml
   ```

## Usage

### Update Alpine Linux Hosts

Run the main update playbook:
```bash
ansible-playbook playbooks/update_alpine.yml -i <inventory_file>
```

### Target Specific Hosts

Limit execution to specific hosts or groups:
```bash
ansible-playbook playbooks/update_alpine.yml -i <inventory_file> --limit <host_pattern>
```

### Dry Run

Test the playbook without making changes:
```bash
ansible-playbook playbooks/update_alpine.yml -i <inventory_file> --check
```

## What It Does

The `update_alpine.yml` playbook performs:
- Updates the package cache using `apk update`
- Upgrades all installed packages using `apk upgrade`

## CI/CD Pipeline

The repository includes a Woodpecker CI configuration that automatically runs updates when triggered by:
- Git pushes to the main branch
- Manual pipeline execution
- Scheduled cron jobs

### Pipeline Steps
1. **Populate Inventory**: Creates inventory file from secrets
2. **Update Alpine Servers**: Executes the Ansible playbook
3. **Send Notification**: Reports results to Discord

### Required Secrets
Configure these secrets in your Woodpecker CI environment:
- `hosts` - YAML inventory content defining target hosts
- `ansible_private_key` - SSH private key for authenticating to remote hosts
- `webhook_id` - Discord webhook ID for notifications
- `webhook_token` - Discord webhook token for notifications

## Structure

```
├── .woodpecker/
│   └── main.yaml           # Woodpecker CI pipeline configuration
├── playbooks/
│   └── update_alpine.yml   # Main Alpine update playbook
└── requirements.yml        # Ansible collection dependencies
```

## Dependencies

- `community.general` - Provides the `apk` module for Alpine package management