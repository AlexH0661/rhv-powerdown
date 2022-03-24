#!/bin/bash

if [[ ! -d /opt/rhv_scripts ]]; then
  mkdir /opt/rhv_scripts
fi

if [[ ! -d /opt/rhv_scripts/venv ]]; then
  python3 -m venv /opt/rhv_scripts/venv
fi

source /opt/rhv_scripts/venv/bin/activate

monitorups