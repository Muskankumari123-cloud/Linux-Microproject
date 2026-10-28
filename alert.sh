#!/bin/bash
source "$(dirname "$0")/config.sh"

send_alert() {
    local msg="$1"
    echo "$(date '+%F %T') [ALERT] $msg" >> "$ALERT_LOG"
    logger -t storage-monitor "$msg"
    osascript -e "display notification \"$msg\" with title \"Storage Alert\" sound name \"Glass\""
    echo "ALERT: $msg"
}
