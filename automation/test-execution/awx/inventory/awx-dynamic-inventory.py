#!/usr/bin/env python3
"""
AWX Dynamic Inventory Script for vLLM Performance Testing

This script generates Ansible inventory dynamically based on AWX extra_vars.
It allows users to configure DUT and load generator settings through the AWX UI
without editing static inventory files.

Usage in AWX:
  1. Create Inventory Source (type: Custom Script)
  2. Paste this script
  3. Sync inventory before running jobs
  4. Survey extra_vars will override defaults

Environment Variables (from AWX survey):
  - DUT_HOST: DUT hostname/IP
  - DUT_USER: DUT SSH user
  - LOADGEN_MODE: "localhost" or "remote"
  - LOADGEN_HOST: Load generator hostname/IP (if remote)
  - LOADGEN_USER: Load generator SSH user (if remote)
  - RESULTS_DIR: Results directory path
  - VLLM_IMAGE: vLLM container image
  - GUIDELLM_IMAGE: GuideLLM container image
"""

import json
import os
import sys


def get_inventory():
    """Generate dynamic inventory from environment variables."""

    # Read configuration from environment (set by AWX survey)
    dut_host = os.getenv('DUT_HOST', 'localhost')
    dut_user = os.getenv('DUT_USER', 'ec2-user')

    loadgen_mode = os.getenv('LOADGEN_MODE', 'localhost')
    loadgen_host = os.getenv('LOADGEN_HOST', 'localhost')
    loadgen_user = os.getenv('LOADGEN_USER', os.getenv('USER', 'awx'))

    results_dir = os.getenv('RESULTS_DIR', '/tmp/benchmark-results')
    vllm_image = os.getenv('VLLM_IMAGE', 'quay.io/mtahhan/vllm:0.13.0-amx')
    guidellm_image = os.getenv('GUIDELLM_IMAGE', 'localhost/guidellm:latest')

    # Build inventory structure
    inventory = {
        "all": {
            "children": ["dut", "load_generator"]
        },
        "dut": {
            "hosts": {
                "my-dut": {
                    "ansible_host": dut_host,
                    "ansible_user": dut_user,
                }
            }
        },
        "load_generator": {
            "hosts": {
                "my-loadgen": {
                    "ansible_host": loadgen_host if loadgen_mode == "remote" else "localhost",
                    "ansible_connection": "ssh" if loadgen_mode == "remote" else "local",
                    "ansible_user": loadgen_user if loadgen_mode == "remote" else None,
                    "ansible_python_interpreter": "auto_silent",
                    "ansible_become": False,
                    "bench_config": {
                        "vllm_host": dut_host,
                        "vllm_port": 8000,
                        "results_dir": results_dir
                    }
                }
            }
        },
        "_meta": {
            "hostvars": {
                "my-dut": {
                    "ansible_host": dut_host,
                    "ansible_user": dut_user
                },
                "my-loadgen": {
                    "ansible_host": loadgen_host if loadgen_mode == "remote" else "localhost",
                    "ansible_connection": "ssh" if loadgen_mode == "remote" else "local",
                    "bench_config": {
                        "vllm_host": dut_host,
                        "vllm_port": 8000,
                        "results_dir": results_dir
                    }
                }
            }
        }
    }

    # Remove None values
    def remove_none(obj):
        if isinstance(obj, dict):
            return {k: remove_none(v) for k, v in obj.items() if v is not None}
        elif isinstance(obj, list):
            return [remove_none(item) for item in obj if item is not None]
        else:
            return obj

    return remove_none(inventory)


def main():
    """Main entry point."""
    if len(sys.argv) == 2 and sys.argv[1] == '--list':
        inventory = get_inventory()
        print(json.dumps(inventory, indent=2))
    elif len(sys.argv) == 3 and sys.argv[1] == '--host':
        # AWX expects this for host-specific vars (already in _meta)
        print(json.dumps({}))
    else:
        print("Usage: {} --list or {} --host <hostname>".format(sys.argv[0], sys.argv[0]))
        sys.exit(1)


if __name__ == '__main__':
    main()
