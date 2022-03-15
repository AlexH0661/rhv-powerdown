#!/usr/bin/env python3

""" Gracefully shutdown all services on a Red Hat Virtualization Host """
import os
from re import sub
import subprocess

import msgpack
import ovirtsdk4 as sdk
from ovirtsdk4 import types

PROTECTED_VMS = ['HostedEngine', 'hussdc01.hussdogg.com', 'identity.idm.hussdogg.com']
FLAGS = [
    'noout',
    'norecover',
    'norebalance',
    'nobackfill',
    'nodown',
    'pause'
    ]
BASE_URL = 'https://rhvm.idm.hussdogg.com/ovirt-engine/api'

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

def power_off_vms(connection):
    """
    power off VMs using oVirt SDK for connection
    :param object connection: oVirt connection object
    """
    print('Retrieving VM details')
    system_service = connection.system_service()
    vms_service = system_service.vms_service()
    loop_count = 0
    count = 0
    vms = vms_service.list()
    while count > (len(vms)-len(PROTECTED_VMS)):
        loop_count += 1
        for vm in vms:
            if vm.name not in PROTECTED_VMS:
                print(f"{vm.name}: {vm.status}")
                vm_service = vms_service.vm_service(vm.id)
                if vm.status == types.VmStatus.DOWN:
                    count += 1
                if vm.status == types.VmStatus.UP:
                    vm_service.stop()
                continue
        print(f"VM's shutoff {count}/{len(vms)-len(PROTECTED_VMS)}")
        print(f"Loop number: {loop_count}")
        vms = vms_service.list()
        count = 0

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
    print('Setting ceph flags')
    set_ceph_flags()
    print('Connecting to RHVM')
    connection = sdk.Connection(
        url = BASE_URL,
        username = os.environ['RHVM_USERNAME'],
        password = os.environ['RHVM_PASSWORD'],
        ca_file = 'ca-bundle.pem'
    )
    set_maintenance_mode()
    power_off_vms(connection)
    power_off_rhvm()
    power_off_host()

if __name__ == '__main__':
    print('Starting graceful shutdown procedure')
    main()