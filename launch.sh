#!/bin/bash
DISPLAY=:0 nohup python3 /home/jdog/code/money-tracker/app.py > /tmp/money_tracker.log 2>&1 &
