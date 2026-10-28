#!/bin/bash
DIR="$(dirname "$0")"
source "$DIR/config.sh"; source "$DIR/alert.sh"

df -i | awk 'NR>1 && $1 ~ /^\/dev\// {print $8, $9}' | \
while read use mount; do
    pct=${use%\%}
    [[ "$pct" =~ ^[0-9]+$ ]] || continue
    if [ "$pct" -ge "$INODE_THRESHOLD" ]; then
        send_alert "Inode usage on $mount is ${pct}% (threshold ${INODE_THRESHOLD}%)"
    fi
done
echo "Inode check completed."
