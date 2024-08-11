#!/bin/bash
# dynamic_timer.sh

SECONDS=$1
TYPE=$2
SCRIPT_DIR=$(dirname "$0")
PYTHON_EXE="$SCRIPT_DIR/venv/bin/python3"
TRIGGER_SCRIPT="$SCRIPT_DIR/trigger_alarm_timer.py"

sleep $SECONDS
$PYTHON_EXE $TRIGGER_SCRIPT $TYPE