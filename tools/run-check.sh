#!/bin/sh

set -eu

PG_CONFIG=${PG_CONFIG:-pg_config}
MAKE=${MAKE:-make}
KEEP_CHECK_ARTIFACTS=${KEEP_CHECK_ARTIFACTS:-0}

repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
pg_bindir=$("$PG_CONFIG" --bindir)
pg_sharedir=$("$PG_CONFIG" --sharedir)
pg_pkglibdir=$("$PG_CONFIG" --pkglibdir)
pg_major=$("$PG_CONFIG" --version | sed -n "s/.*PostgreSQL \([0-9][0-9]*\).*/\1/p")
pg_user=${PGUSER:-$(id -un)}
port=$((49152 + ($$ % 10000)))

if [ -z "$pg_major" ]; then
    echo "Could not determine PostgreSQL major version from $PG_CONFIG." >&2
    exit 1
fi

if [ "$pg_major" -lt 16 ]; then
    cat >&2 <<EOF
make check needs PostgreSQL 16+ so it can point a temporary cluster at the
freshly built extension with extension_control_path.

On older PostgreSQL versions, use:
  make install
  make installcheck
EOF
    exit 1
fi

install_root=$(mktemp -d "${TMPDIR:-/tmp}/address-standardizer-install.XXXXXX")
pgdata=$(mktemp -d "${TMPDIR:-/tmp}/address-standardizer-pgdata.XXXXXX")
sockdir=$(mktemp -d "${TMPDIR:-/tmp}/address-standardizer-pgsock.XXXXXX")
logfile="$pgdata/postgresql.log"
sharedir="$install_root$pg_sharedir"
pkglibdir="$install_root$pg_pkglibdir"

cleanup() {
    status=$?

    if [ -f "$pgdata/postmaster.pid" ]; then
        "$pg_bindir/pg_ctl" -D "$pgdata" -m fast stop >/dev/null 2>&1 || true
    fi

    if [ "$status" -ne 0 ] || [ "$KEEP_CHECK_ARTIFACTS" = "1" ]; then
        echo "Temporary install root: $install_root" >&2
        echo "Temporary data dir: $pgdata" >&2
        echo "Temporary socket dir: $sockdir" >&2
        echo "PostgreSQL log: $logfile" >&2
    fi

    if [ "$status" -eq 0 ] && [ "$KEEP_CHECK_ARTIFACTS" != "1" ]; then
        rm -rf "$install_root" "$pgdata" "$sockdir"
    fi

    trap - EXIT HUP INT TERM
    exit "$status"
}

trap cleanup EXIT HUP INT TERM

"$MAKE" -C "$repo_root" -f Makefile install DESTDIR="$install_root"

"$pg_bindir/initdb" -D "$pgdata" --locale=C --encoding=UTF8 --auth=trust --no-instructions >/dev/null

cat >> "$pgdata/postgresql.auto.conf" <<EOF
listen_addresses = ''
unix_socket_directories = '$sockdir'
port = $port
extension_control_path = '$sharedir:\$system'
dynamic_library_path = '$pkglibdir:\$libdir'
EOF

if ! "$pg_bindir/pg_ctl" -D "$pgdata" -l "$logfile" -w start >/dev/null; then
    cat "$logfile" >&2 || true
    exit 1
fi

export PATH="$pg_bindir:$PATH"
export PGHOST="$sockdir"
export PGPORT="$port"
export PGUSER="$pg_user"

createdb contrib_regression
"$MAKE" -C "$repo_root" -f Makefile installcheck
