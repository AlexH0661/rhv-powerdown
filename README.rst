# rhv-powerdown
[bdist_rpm]
requires=python3-ovirt-engine-sdk4

[options.data_files]
/etc/systemd/system/ = scripts/systemd/monitor_ups.service
/usr/local/bin/ = scripts/bin/monitor_ups.sh
/opt/rhv_power/ = config.yml.example, ca-bundle.pem