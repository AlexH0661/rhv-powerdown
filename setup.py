from setuptools import setup

setup(
    name='rhv-power',
    version='0.1',
    packages=[
        'monitor_ups'
    ],
    install_requires=[
        'msgpack',
        'pylint',
        'pysnmp',
        'pytest',
        'pyyaml'
    ],
    entry_points = {
        'console_scripts': [
            'monitorups = monitor_ups.__main__:main'
        ],
    },
    data_files=[
        ('/etc/systemd/system/', ['scripts/systemd/monitor_ups.service']),
        ('/usr/local/bin/', ['scripts/bin/monitor_ups.sh']),
        ('/opt/rhv_power/', ['config.yml.example'])
    ]
)