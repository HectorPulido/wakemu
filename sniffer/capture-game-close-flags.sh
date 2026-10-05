#!/bin/bash
# Optional transport evidence: text TCP FIN/RST headers only, never payload/pcap.
set -euo pipefail
interface="${1:-lo0}"
output="${2:-.runtime/local/game-close-flags.txt}"
umask 077
mkdir -p "$(dirname -- "$output")"
exec tcpdump -i "$interface" -nn -tttt -l -q \
  'tcp port 15556 and (tcp[tcpflags] & (tcp-fin|tcp-rst) != 0)' > "$output"
