import pytest

import monitor_ups.__main__ as monitor_ups

def test_snmp_battery_time_remaining(monkeypatch):
    """
    We mock the SNMP response, so that we can just test how we parse the response
    Result is a list of tuples.
    The first element of the tuple is the SNMP OID description, the second value
    is the OID value.

    `300` means the estimated remaining battery time.
    """
    def mock_getCmdBatteryTime(*args, **kwargs):
        return [('battery_time_remaining', 300)]
    monkeypatch.setattr(monitor_ups, '_get_oid_value', mock_getCmdBatteryTime)

    assert monitor_ups.ups_battery_time_remaining('127.0.0.1') == 300

def test_snmp_ups_on_mains(monkeypatch):
    """
    We mock the SNMP response, so that we can just test how we parse the response
    Result is a list of tuples.
    The first element of the tuple is the SNMP OID description, the second value
    is the OID value.

    `2` means the UPS is on mains.
    `1` means the UPS is on battery.
    """
    def mock_getCmdOnMains(*args, **kwargs):
        return [('is_on_mains', 2)]
    monkeypatch.setattr(monitor_ups, '_get_oid_value', mock_getCmdOnMains)

    assert monitor_ups.is_ups_on_mains('127.0.0.1') == True