#!/usr/bin/env python3

""" Gracefully shutdown all services on a Red Hat Virtualization Host when all UPS are on battery """
import argparse
import logging
import json
import socket
import subprocess
import sys
import time
import urllib3

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

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
HOST_IP = s.getsockname()[0]
HOSTNAME = socket.gethostname() 

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
    shutdown = False
    while not shutdown:
        result = subprocess.run([
            'hosted-engine',
            '--vm-status ',
            '--json'
        ], capture_output=True)
        json_result = json.loads(result)

        hosted_engine_down = 0
        for i in json_result.keys():
            if json_result[i]["engine-status"]["vm"] == "down":
                hosted_engine_down += 1
        if hosted_engine_down == len(json_result) - 1:
            shutdown = True
            break

def power_off_vms(connection, protected_vms, ups):
    """
    power off VMs using oVirt SDK for connection
    :param object connection: oVirt connection object
    :param list protected_vms: A list of VMs that we shouldn't shutdown if required
    :param list ups: A list of UPS that we want to poll while shutting the VMs down
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
                    LOGGER.info(f"{vm.name}: {vm.status}")
                    vm_service = vms_service.vm_service(vm.id)
                    if vm.status == sdk.types.VmStatus.SHUTTING_DOWN:
                        low_battery_count = 0
                        for appliance in ups:
                            ups_battery_level = ups_battery_time_remaining(appliance)
                            if ups_battery_level < 240:
                                low_battery_count += 1
                        if low_battery_count == len(ups):
                            vm_service.stop()
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

def _get_oid_value(ups_ip_addr, oid):
    """
    Using SNMPv3 get the value for a specific OID

    :param string ups_ip_addr: IP address of the UPS to poll
    :param string oid: OID to get the value of
    :returns: SNMP result (pysnmp generator)
    """
    iterator = getCmd(SnmpEngine(),
                  UsmUserData('readuser'),
                  UdpTransportTarget((ups_ip_addr, 161)),
                  ContextData(),
                  ObjectType(ObjectIdentity(oid)),
                  lookupMib=False)

    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

    if errorIndication:  # SNMP engine errors
        LOGGER.critical(errorIndication)
        sys.exit(1)

    if errorStatus:  # SNMP agent errors
        LOGGER.critical('%s at %s' % (errorStatus.prettyPrint(), varBinds[int(errorIndex)-1] if errorIndex else '?'))
        sys.exit(1)

    return varBinds

def is_ups_on_mains(ups_ip_addr):
    """
    checks if an Eaton UPS is on battery
    :param string ups_ip_addr: IP address of the UPS to check
    """
    # varBinds is a generator created by pysnmp which contains the SNMP Get results
    varBinds = _get_oid_value(ups_ip_addr, '1.3.6.1.4.1.705.1.7.3.0')
    for varBind in varBinds:
        result = varBind[1]
        if result == 2:
            return True
        if result == 1:
            return False

def ups_battery_time_remaining(ups_ip_addr):
    """
    amount of time remaining on battery
    :param string ups_ip_addr: IP address of the IPS to check
    """
    # varBinds is a generator created by pysnmp which contains the SNMP Get results
    varBinds = _get_oid_value(ups_ip_addr, '1.3.6.1.4.1.705.1.5.1.0')
    for varBind in varBinds:
        print(varBind)
        result = varBind[1]
    return result

def _post_msg_discord(msg, discordHook, colour='16711680'):
    """
    post a message to discord
    """
    data = {}
    data["tts"] = "true"
    data["username"] = HOSTNAME
    data["avatar_url"] = "https://cdn3.vectorstock.com/i/1000x1000/78/02/cartoon-turtle-vector-4367802.jpg"
    data["embeds"] = []
    embed = {}
    embed["color"] = colour
    embed["title"] = "UPS Notification"
    embed["description"] = msg
    data["embeds"].append(embed)
    http = urllib3.PoolManager()
    headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.18363"
            }
    resp =  http.request(method="POST", url=discordHook, body=bytes(json.dumps(data), 'UTF-8'), headers=headers)
    if resp.status >= 400:
        LOGGER.warning(f"Server response: {resp.data.decode('UTF-8')}")

def main():
    """
    main application loop
    """
    LOGGER.info('Starting')
    with open(ARGS.config, 'r') as fp:
        config = yaml.safe_load(fp)
    protected_vms = config.get('protected_vms', 'HostedEngine')
    monitor_frequency = config.get('monitor_frequency', 60)
    discord_webhook = config.get('discord_webhook', None)
    ups = config['ups']
    LOGGER.info('Started')
    try:
        count = 0
        LOGGER.info('Monitoring')
        while count < len(ups):
            monitor_frequency = config.get('monitor_frequency', 60)
            for appliance in ups:
                on_mains = is_ups_on_mains(appliance)
                if not on_mains:
                    count += 1
                    msg = f"{appliance} is on battery!"
                    LOGGER.info(msg)
                    if discord_webhook:
                        _post_msg_discord(msg, discord_webhook)
                    monitor_frequency=10
            if count == len(ups):
                msg = "All UPS are on battery. Begining shutdown!"
                LOGGER.info(msg)
                if discord_webhook:
                    _post_msg_discord(msg, discord_webhook)
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
    power_off_vms(connection, protected_vms, ups)
    power_off_rhvm()
    if ARGS.ceph:
        LOGGER.info('Setting ceph flags')
        set_ceph_flags()
    LOGGER.info('Completed')
    power_off_host()

if __name__ == '__main__':
    LOGGER.info('Monitoring UPS')
    main()