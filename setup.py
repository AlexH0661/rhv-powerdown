from setuptools import setup

setup(
    name='rhv-power',
    version='0.0.1',
    packages=[
        'rhv_power'
    ],
    install_requires=[
        'msgpack',
        'pylint',
        'pysnmp',
        'pyyaml'
    ],
    entry_points = {
        'console_scripts': [
            'monitorups = rhv_power.__main__:main'
        ],
    }
)