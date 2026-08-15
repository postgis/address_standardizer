# address_standardizer extension

[![CI](https://github.com/postgis/address_standardizer/workflows/CI/badge.svg)](https://github.com/postgis/address_standardizer/actions)

This is a fork of the [PAGC standardizer](http://www.pagcgeo.org/) and single line address parser.
The code is built into a single PostgreSQL extension library.

Project history notes, including the standalone split from PostGIS and recent
standalone changes, live in [NEWS.md](NEWS.md).


## Build and Install

This is a PostgreSQL extension, and building it requires the PostgresSQL server headers, and regular expression library development headers.

* Install PostgreSQL development packages (`postgresql-devel` or `postgresql-server-devel`)
* Check access to the `pg_config` program on your path
* Install [libpcre2](https://github.com/PCRE2Project/pcre2) and headers

```
# debian
sudo apt install libpcre2-dev libpcre2-8-0 libpcre2-posix2

# redhat/centos
sudo dnf install pcre2-devel

# homebrew
brew install pcre2
```

With the correct libraries installed and `pg_config` on the path, building with `make` should work out of the box. If it fails, you may need to edit the Makefile to specify your `pg_config` or `pcre2` locations.

```
make
sudo make install
```

## Testing

For a self-contained regression run against the freshly built extension, use:

```
make -j check
```

`make check` creates a temporary install tree and PostgreSQL cluster, runs the
regressions, and cleans everything up afterward. This requires PostgreSQL 16 or
newer because it relies on `extension_control_path`.

If you want to inspect the temporary cluster after a failure, keep the scratch
artifacts with:

```
KEEP_CHECK_ARTIFACTS=1 make check
```

On older PostgreSQL versions, fall back to the traditional flow against an
existing server:

```
make
sudo make install
make installcheck
```

Once build and installed, you can activate the extension with `CREATE EXTENSION`.
```
createdb address_db
psql -d address_db -c "CREATE EXTENSION address_standardizer"
```


## Datasets

The extension supports datasets for different countries:
* `address_standardizer_data_us`: United States address dataset (USPS based lexicon and gazetteer).
* `address_standardizer_data_br`: Brazilian address dataset (IBGE / OpenStreetMap based lexicon, gazetteer of all 5,570 municipalities, 27 states, and Brazilian address grammar rules).

### Open Data Provenance for Brazil Dataset (`address_standardizer_data_br`)

> **Data Provenance & Licensing Statement:**
> The `address_standardizer_data_br` dataset is constructed exclusively from 100% public, official open data sources:
> * **IBGE (Instituto Brasileiro de Geografia e Estatística):** Official Public API for Localidades (5,570 Brazilian Municipalities and 27 Federative Units / States) and CNEFE 2022 (Cadastro Nacional de Endereços para Fins Estatísticos) under open government data terms.
> * **OpenStreetMap (OSM):** Standard community open terminology for Brazilian thoroughfare and unit types.
> 
> *No proprietary or copyrighted postal databases (such as Empresa Brasileira de Correios e Telégrafos - DNE) are used.*

## Test and Try

### United States (US)
```sql
SELECT * FROM standardize_address('us_lex', 'us_gaz', 'us_rules', '123 Main Street', 'Kansas City, MO 45678');
```

### Brazil (BR)
```sql
-- Standard street address
SELECT * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rua Augusta, 100', 'Sao Paulo, SP');

-- Address with Apartment and Postal Code (CEP)
SELECT * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Avenida Paulista, 1000 Apto 101', 'Sao Paulo, SP, 01310 100');

-- Highway with Kilometer
SELECT * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Rodovia dos Imigrantes, Km 50', 'Sao Paulo, SP');

-- Brasília Superquadra / Block format
SELECT * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'SQS 308 Bloco B Apto 101', 'Brasilia, DF');

-- Lot / Allotment format
SELECT * FROM standardize_address('br_lex', 'br_gaz', 'br_rules', 'Quadra 10 Lote 5', 'Goiania, GO');
```

# Development


## Release

The `release.yml` GitHub Action defines a release-on-tag process.

* Ensure the `NEWS.md` file is up-to-date and the release date is set to the current date.
* Ensure that the version in `address_standardizer.control` and `address_standardizer_data_us.control` is set to the release version (eg `default_version = '3.7.1'`).
* Tag the repository with that version prefixed by `v` (`git tag v3.7.1 && git push origin v3.7.1`)

The release will only build out with a clean build and matching tag/version numbers.


## Files

```
Makefile                - PGXS makefile
README.md               - this file
COPYING                 - License file

pl/
   mk-city-regex.pl        - Perl script to create parseaddress-regex.h
   mk-st-regexp.pl         - Perl script to create parseaddress-stcities.h
   usps-st-city-name.txt   - USPS city names

src/
    parseaddress-regex.h     - created by make and mk-st-regexp
    parseaddress-stcities.h  - created by make and mk-city-regex
                               from usps-st-city-name.txt
```

## How the Parser Works

The parser works from right to left looking first at the macro elements 
for postcode, state/province, city, and then looks micro elements to determine
if we are dealing with a house number street or intersection or landmark.
It currently does not look for a country code or name, but that could be
introduced in the future.

### Country Code

Assumed to be US or CA based on:

    postcode as US or Canada
    state/province as US or Canada
    else US

### Postcode/Zipcode

These are recognized using Perl compatible regular expressions.
These regexs are currently in the `parseaddress-api.c` and are relatively
simple to make changes to if needed.

### State/Province

These are recognized using Perl compatible regular expressions.
These regexs are currently in the parseaddress-api.c but could get moved
into includes in the future for easier maintenance.

### City Name

This part is rather complicated and there are lots of issues around ambiguities
as to where to split a series of tokens when a token might belong to either
the city or the street name. The current strategy follows something like this:

1. if we have a state, then get the city regex for that state
2. if we can match that to the end of our remaining address string then
   extract the city name and continue.
3. if we do not have a state or fail to match it then
   cycle through a series of regex patterns that try to separate the city
   from the street, stop and extract the city if we match

### Number Street Name

1. check for a leading house number, and extract that
2. if there is an '@' then split the string on the '@' into street and
   street2 else put the rest into street


## Managing the Regexes

The regexes are used to recognize US states and Canadian provinces
and USPS city names.

### City Regexes
```
usps-st-city-orig.txt  - this file contains all the acceptable USPS city
                         names by state. I periodically extract these from the
                         USPS and generate this file. I do NOT recommend
                         editing this file. 
usps-st-city-adds.txt  - this file you can add new definitions to if you need
                         them. The format of both these files is:
                         <StateAbbrev><tab><CityName>
```
These files are assembled into `usps-st-city-name.txt` which is compiled by a
perl script `mk-city-regex.pl` into `parseaddress-stcities.h` which is used to
lookup the city regex for a specific state or province.

As I mentioned above is these fail to detect the city, then a secondary
strategy is is deployed by cycling through a list of regex patterns. These
patterns and regexes are generated by `mk-st-regexp.pl` which creates the
`parseaddress-regex.h` include. This is a perl script so you can view and edit
it if that is needed.

I think that there might be some room for improved in the area if coodinating
this process with PAGC's `lexicon.csv` and `gazeteer.csv` in the future.


# License

Portions of this code belong to their respective contributors.
This code is released under an [MIT-X license](COPYING).

Copyright (c) 2006-2014 [Stephen Woodbridge](mailto:woodbri@swoodbridge.com) <br/>
Copyright (c) 2008 Walter Bruce Sinclair
