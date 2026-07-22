#!/usr/bin/env bash
# Free IP rotation for macOS — point the crawler at it with:
#   python -m crawler crawl ... --rotate-ip-cmd "bash crawler/scripts/rotate_ip_macos.sh" --rotate-after-blocks 1
#
# The crawler runs this between cooldown rounds and then verifies (via api/api6.ipify.org)
# that the public IPv4 OR IPv6 actually changed before continuing. No proxies, no cost.
#
# MODE (env var), pick what your network supports:
#   wifi  (default) — cycle Wi-Fi power. Forces a DHCP re-lease + fresh SLAAC/RFC-4941 IPv6.
#                     Often changes the public IPv6 (and sometimes IPv4) for free. No sudo.
#   ipv6            — reassign a random address inside your delegated /64 and make it the
#                     preferred source. Rotates the egress IPv6 without dropping the link.
#                     Needs sudo (configure NOPASSWD for ifconfig if running unattended).
#
# IFACE defaults to the primary Wi-Fi device (auto-detected), override with IFACE=en1 etc.
set -u

MODE="${MODE:-wifi}"

detect_iface() {
  # first Wi-Fi hardware port device, else en0
  local dev
  dev="$(networksetup -listallhardwareports 2>/dev/null \
        | awk '/Wi-Fi|AirPort/{getline; print $2; exit}')"
  echo "${dev:-en0}"
}
IFACE="${IFACE:-$(detect_iface)}"

case "$MODE" in
  wifi)
    echo "rotate: cycling Wi-Fi on $IFACE"
    networksetup -setairportpower "$IFACE" off
    sleep 4
    networksetup -setairportpower "$IFACE" on
    # give DHCP/SLAAC time to re-establish before the crawler probes
    sleep 8
    ;;
  ipv6)
    # derive a random host suffix inside the current /64 prefix
    prefix="$(ifconfig "$IFACE" 2>/dev/null \
              | awk '/inet6/ && !/fe80|::1/ {split($2,a,":"); print a[1]":"a[2]":"a[3]":"a[4]; exit}')"
    if [ -z "$prefix" ]; then
      echo "rotate: no global IPv6 /64 on $IFACE — falling back to wifi cycle"
      MODE=wifi exec bash "$0"
    fi
    rand() { printf '%x' $(( RANDOM % 65536 )); }
    newaddr="${prefix}:$(rand):$(rand):$(rand):$(rand)"
    echo "rotate: adding IPv6 $newaddr on $IFACE (sudo)"
    sudo ifconfig "$IFACE" inet6 "$newaddr" prefixlen 64 alias
    sleep 3
    ;;
  *)
    echo "rotate: unknown MODE=$MODE (use wifi|ipv6)" >&2
    exit 2
    ;;
esac
echo "rotate: done"
