#!/bin/bash
DIR="$(dirname "$0")"
source "$DIR/config.sh"
OUT="$REPORT_DIR/report_$(date +%F_%H%M).txt"
{
  echo "===== STORAGE REPORT: $(hostname) | $(date) ====="
  echo
  echo "--- Disk Utilization ---"
  df -h | grep -E '^Filesystem|^/dev/'
  echo
  echo "--- Inode Usage ---"
  df -i | grep -E '^Filesystem|^/dev/'
  echo
  echo "--- Top 10 Largest Folders in Home ---"
  du -xh "$HOME" -d 2 2>/dev/null | sort -rh | head -10
  echo
  echo "--- Recent Alerts ---"
  tail -n 10 "$ALERT_LOG" 2>/dev/null
  echo
  echo "--- Growth History (last 10) ---"
  tail -n 10 "$LOG_DIR/usage_history.csv" 2>/dev/null
} > "$OUT"
echo "Report saved: $OUT"
