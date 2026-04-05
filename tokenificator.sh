#!/bin/sh
# Flatpak launcher for Tokenificator.
# Runs inside the sandbox; DATA_DIR is XDG_DATA_HOME/tokenificator (writable).
exec python3 /app/share/tokenificator/main.py "$@"
