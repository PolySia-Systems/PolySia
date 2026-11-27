#!/bin/sh
# Both release files have been verified by the README command.
set -eu
fail() { printf '%s\n' "$*" >&2; exit 1; }

printf '%s\n' 'Where should PolySia run?' \
    '  1  On this Linux computer' \
    '  2  On a server via SSH (new site or update on its current host)' \
    '  3  Recover a private site on a replacement host or restored snapshot'
printf 'Choose 1, 2 or 3: '
IFS= read -r mode || exit 1
case "$mode" in
1)
    [ "$(uname -s)" = Linux ] || fail 'Local mode needs Linux. Rerun and choose a Linux server.'
    python3 -I -c 'import sys, sqlite3; sys.exit(sys.version_info < (3, 12))' ||
        fail 'Install Python 3.12 or newer with SQLite on this Linux computer, then retry.'
    exec python3 -I ./polysia.pyz --start
    ;;
2|3) ;;
*) fail 'Rerun the install command and choose 1, 2 or 3.' ;;
esac

printf '%s\n' 'Use a dedicated Ubuntu 26.04 amd64 server with systemd and sudo access.'
printf 'SSH destination (your SSH alias or user@hostname): '
IFS= read -r host || exit 1
case "$host" in ''|-*|*[!a-zA-Z0-9@._-]*) fail 'Use an SSH alias or user@hostname. Put custom ports in your SSH config.' ;; esac
ssh_bin=ssh
# Use the same SSH configuration as PowerShell when running in Git Bash.
case "$(uname -s)" in MINGW*|MSYS*) [ ! -x /c/Windows/System32/OpenSSH/ssh.exe ] || ssh_bin=/c/Windows/System32/OpenSSH/ssh.exe ;; esac
connect() { MSYS2_ARG_CONV_EXCL='*' "$ssh_bin" -o ForwardAgent=no -o ClearAllForwardings=yes "$@" ; }
digest=$(sha256sum polysia.pyz)
digest=${digest%% *}
stage=$(connect -T "$host" 'set -eu; umask 077; f=$(mktemp /tmp/polysia.XXXXXXXXXX); if cat > "$f"; then echo "$f"; else rm -f "$f"; exit 1; fi' < polysia.pyz) ||
    fail 'Transfer failed. Check that you can SSH to the server and rerun.'
stage=$(printf '%s' "$stage" | tr -d '\r')
printf '%s\n' "$stage" | grep -Exq '/tmp/polysia\.[a-zA-Z0-9]{10}' && [ "$(printf '%s' "$stage" | wc -l)" -eq 0 ] ||
    fail 'Unexpected SSH response. Check the server login configuration.'
options=--prepare-cloudflare-host
if [ "$mode" = 3 ]; then
    options="$options --recover"
    printf '%s\n' 'Recovery requires the former host to be offline. Have your workspace backup ready.'
fi
connect -tt "$host" "trap 'rm -f $stage' EXIT; printf '%s  %s\n' '$digest' '$stage' | sha256sum -c - && sudo /usr/bin/python3 -I '$stage' $options"
