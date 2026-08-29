#!/bin/sh
# Convenience launcher: falls back to sudo if the udev rule is not installed.
cd "$(dirname "$0")" || exit 1
if python3 -c "
import sys, via
d = via.find_devices(0x4653, 1) or via.find_devices()
sys.exit(0 if d and __import__('os').access(d[-1]['path'], 6) else 1)
" 2>/dev/null; then
    exec python3 server.py "$@"
fi
echo "No writable raw-HID device — see 'Device permissions' in README.md."
echo "Falling back to sudo; ctrl-c to cancel."
exec sudo python3 server.py --no-browser "$@"
