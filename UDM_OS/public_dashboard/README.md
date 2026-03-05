# UDM Public Dashboard

Sanitized, read-only view: state (OPEN/WATCH/CLOSED), symbolic drivers S/C/P, hysteresis depth/count, reason codes, short receipt hash.
Reads from GET /public/state (fallback: POST /ui/replay_last).
After restarting the server: http://localhost:8000/public/
