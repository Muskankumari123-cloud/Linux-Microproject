#!/bin/bash
DIR="$(dirname "$0")"
source "$DIR/config.sh"; source "$DIR/alert.sh"

CSV="$LOG_DIR/usage_history.csv"
now=$(df -kP /System/Volumes/Data | awk 'NR==2 {print $3}')
prev=$(tail -n 1 "$CSV" 2>/dev/null | cut -d, -f2)
echo "$(date '+%F_%T'),$now" >> "$CSV"

if [ -n "$prev" ]; then
    growth_mb=$(( (now - prev) / 1024 ))
    echo "Growth since last check: ${growth_mb} MB"
    if [ "$growth_mb" -ge "$GROWTH_THRESHOLD" ]; then
        send_alert "Storage grew by ${growth_mb} MB since last check (threshold ${GROWTH_THRESHOLD} MB)"
    fi
else
    echo "First run: baseline saved."
fi
