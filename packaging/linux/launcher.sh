#!/bin/sh
export PYTHONPATH=/usr/lib/drivesync-iqbal${PYTHONPATH:+:$PYTHONPATH}
exec python3 -m drivesync_iqbal "$@"
