#!/bin/bash
# Start/stop the ATDD Slack bot
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$DIR/.bot.pid"
LOGFILE="$DIR/bot.log"

stop() {
  if [ -f "$PIDFILE" ]; then
    pid=$(cat "$PIDFILE")
    if kill -0 "$pid" 2>/dev/null; then
      echo "Stopping bot (PID $pid)..."
      kill "$pid"
      sleep 3
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null
    fi
    rm -f "$PIDFILE"
  fi
}

case "${1:-start}" in
  start)
    stop
    sleep 2
    cd "$DIR"
    source "$DIR/.venv/bin/activate" 2>/dev/null || true
    nohup python -u "$DIR/app.py" >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    echo "Bot started (PID $!). Log: $LOGFILE"
    sleep 3
    tail -5 "$LOGFILE"
    ;;
  stop)
    stop
    echo "Bot stopped."
    ;;
  restart)
    stop
    sleep 3
    exec "$0" start
    ;;
  log)
    tail -f "$LOGFILE"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|log}"
    ;;
esac
