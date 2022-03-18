#!/usr/bin/env python3

""" Gracefully shutdown all services on a Red Hat Virtualization Host """
import argparse
import os
import subprocess
import sys
import time

import msgpack
import ovirtsdk4 as sdk
from ovirtsdk4 import types
import yaml

PARSER = argparse.ArgumentParser()
PARSER.add_argument('--ceph', action='store_true', help='This node hosts RHCS')
ARGS = PARSER.parse_args()

FLAGS = [
    'noout',
    'norecover',
    'norebalance',
    'nobackfill',
    'nodown',
    'pause'
    ]

def power_off_host():
    """
    powers off Red Hat Virtualization Host
    """
    subprocess.run([
        'poweroff'
    ])

def power_off_rhvm():
    """
    power off Red Hat Virtualization Manager
    """
    subprocess.run([
        'hosted-engine',
        '--vm-shutdown'
    ])

def power_off_vms(connection, protected_vms):
    """
    power off VMs using oVirt SDK for connection
    :param object connection: oVirt connection object
    """
    print('Retrieving VM details')
    print(f"Excluding the following VMs: {protected_vms}")
    system_service = connection.system_service()
    vms_service = system_service.vms_service()
    loop_count = 0
    stopped_vms = set()
    vms = vms_service.list()
    while len(stopped_vms) < (len(vms)-len(protected_vms)):
        loop_count += 1
        for vm in vms:
            if vm.name not in protected_vms:
                try:
                    print(f"{vm.name}: {vm.status}")
                    vm_service = vms_service.vm_service(vm.id)
                    if vm.status == types.VmStatus.DOWN:
                        stopped_vms.add(vm.name)
                    if vm.status == types.VmStatus.UP:
                        vm_service.shutdown()
                    continue
                except BaseException as base_err:
                    print(base_err)
                    sys.exit(1)
        print(f"VM's shutoff {len(stopped_vms)}/{len(vms)-len(protected_vms)}")
        print(f"Loop number: {loop_count}")
        time.sleep(1)
        vms = vms_service.list()

def set_maintenance_mode():
    """
    put Red Hat Virtualization cluster in maintenance mode
    """
    subprocess.run([
        'hosted-engine',
        '--set-maintenance',
        '--mode=global'
    ])

def set_ceph_flags():
    """
    set ceph flags required for graceful shutdown
    """
    for flag in FLAGS:
        subprocess.run([
            'ceph',
            'osd',
            'set',
            flag
        ])

def main():
    """
    main application loop
    """
    with open('config.yml', 'r') as fp:
        config = yaml.safe_load(fp)
    protected_vms = config.get('protected_vms', 'HostedEngine')
    print('Connecting to RHVM')
    connection = sdk.Connection(
        url = config['rhvm_url'],
        username = config['rhvm_username'],
        password = config['rhvm_password'],
        ca_file = 'ca-bundle.pem'
    )
    set_maintenance_mode()
    power_off_vms(connection, protected_vms)
    power_off_rhvm()
    if ARGS.ceph:
        print('Setting ceph flags')
        set_ceph_flags()
    power_off_host()

if __name__ == '__main__':
    print('Starting graceful shutdown procedure')
    main()