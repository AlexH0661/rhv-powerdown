#!/usr/bin/env python3

""" Gracefully shutdown all services on a Red Hat Virtualization Host """
import argparse
import logging
import os
import subprocess
import sys
import time

import msgpack
from pysnmp.hlapi import *
import ovirtsdk4 as sdk
import yaml

PARSER = argparse.ArgumentParser()
PARSER.add_argument('--ceph', action='store_true', help='This node hosts RHCS')
PARSER.add_argument('--config', help='Path to configuration file', default='/opt/rhv_scripts/config.yml')
PARSER.add_argument(
    '--verbose', help='Increase application verbosity', action='store_true'
)
ARGS = PARSER.parse_args()

LOG_LEVEL = logging.INFO
if ARGS.verbose:
    LOG_LEVEL = logging.DEBUG

LOGGER = logging.getLogger('monitorups')
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

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
    LOGGER.debug('Retrieving VM details')
    LOGGER.info(f"Excluding the following VMs: {protected_vms}")
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
                    LOGGER.debug(f"{vm.name}: {vm.status}")
                    vm_service = vms_service.vm_service(vm.id)
                    if vm.status == sdk.types.VmStatus.DOWN:
                        stopped_vms.add(vm.name)
                    if vm.status == sdk.types.VmStatus.UP:
                        vm_service.shutdown()
                    continue
                except BaseException as base_err:
                    LOGGER.critical(base_err)
                    sys.exit(1)
        LOGGER.info(f"VM's shutoff {len(stopped_vms)}/{len(vms)-len(protected_vms)}")
        LOGGER.debug(f"Loop number: {loop_count}")
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

def _is_ups_on_mains(ups_ip_addr):
    """
    checks if an Eaton UPS is on battery
    :param string ups_ip_addr: IP address of the UPS to check
    """
    iterator = getCmd(SnmpEngine(),
                  UsmUserData('readuser'),
                  UdpTransportTarget((ups_ip_addr, 161)),
                  ContextData(),
                  ObjectType(ObjectIdentity('1.3.6.1.4.1.705.1.7.3.0')),
                  lookupMib=False)

    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

    if errorIndication:  # SNMP engine errors
        LOGGER.critical(errorIndication)
        sys.exit(1)

    if errorStatus:  # SNMP agent errors
        LOGGER.critical('%s at %s' % (errorStatus.prettyPrint(), varBinds[int(errorIndex)-1] if errorIndex else '?'))
        sys.exit(1)

    for varBind in varBinds: # Have to iterate, even though we are looking at a single instance
        result = varBind[1]
        if result == 2:
            return True
        if result == 1:
            return False

def main():
    """
    main application loop
    """
    LOGGER.info('Starting')
    with open(ARGS.config, 'r') as fp:
        config = yaml.safe_load(fp)
    protected_vms = config.get('protected_vms', 'HostedEngine')
    monitor_frequency = config.get('monitor_frequency', 60)
    ups = config['ups']
    LOGGER.info('Started')
    try:
        count = 0
        LOGGER.info('Monitoring')
        while count < len(ups):
            monitor_frequency = config.get('monitor_frequency', 60)
            for appliance in ups:
                on_mains = _is_ups_on_mains(appliance)
                if not on_mains:
                    count += 1
                    LOGGER.info(f"{appliance} is on battery!")
                    monitor_frequency=10
            if count == len(ups):
                break
            count = 0
            time.sleep(monitor_frequency)
    except KeyboardInterrupt as key_int_err:
        LOGGER.critical('Caught CTRL+C - Exiting')
        sys.exit(1)
    LOGGER.info('Starting graceful shutdown procedure')
    LOGGER.debug('Connecting to RHVM')
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
        LOGGER.debug('Setting ceph flags')
        set_ceph_flags()
    LOGGER.info('Completed')
    power_off_host()

if __name__ == '__main__':
    LOGGER.info('Monitoring UPS')
    main()