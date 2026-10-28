#!/bin/bash
DIR="$(dirname "$0")"
source "$DIR/config.sh"; source "$DIR/alert.sh"

df -P | awk 'NR>1 && $1 ~ /^\/dev\// {print $5, $6}' | \
while read use mount; do
    pct=${use%\%}
    if [ "$pct" -ge "$DISK_THRESHOLD" ]; then
        send_alert "Disk usage on $mount is ${pct}% (threshold ${DISK_THRESHOLD}%)"
    fi
done
echo "Disk check completed."
