#!/bin/sh

set -eu

db="address_standardizer_latin1_$$"
cleanup() {
	dropdb --if-exists --echo "$db" >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

createdb --template=template0 --encoding=LATIN1 --lc-collate=C --lc-ctype=C "$db"
psql --no-psqlrc --quiet --dbname="$db" --set=ON_ERROR_STOP=1 \
	--file="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)/test/sql/latin1_c_locale.sql"
