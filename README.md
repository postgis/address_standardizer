# address_standardizer extension

This is a fork of the [PAGC standardizer](http://www.pagcgeo.org/) and a single line address parser.
The code is built into a single PostgreSQL extension library.

Portions of this code belong to their respective contributors.
This code is released under an [MIT-X license](COPYING).

Copyright (c) 2006-2014 Stephen Woodbridge.
Copyright (c) 2008 Walter Bruce Sinclair

woodbri@swoodbridge.com


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


## Prerequisites

* PostgreSQL headers and PGXS tools
* libpcre2 and headers
  ```
  sudo apt install libpcre2-dev libpcre2-8-0 libpcre2-posix2
  ```


## Build and Install

```
make
sudo make install
```

This will install all the files needed for `CREATE EXTENSION`.
```
createdb testdb
psql -c "create extension address_standardizer"
```


## Test and Try

```
select * from parse_address('2099 university ave w, saint paul, mn, 55104-3431');
select * from parse_address('university ave w @ main st, saint paul, mn, 55104-3431');

select * from parse_address('385 Landgrove Rd  Landgrove VT 05148');
-- "385";"Landgrove Rd";"";"385 Landgrove Rd";"Landgrove";"VT";"05148";"";"US"

select * from standardize_address(
        'select seq, word::text, stdword::text, token from gaz union all select seq, word::text, stdword::text, token from lex ',
        'select seq, word::text, stdword::text, token from gaz order by id',
        'select * from rules order by id',
        'select 0::int4 as id, ''1071 B Ave''::text as micro, ''Loxley, AL 36551''::text as macro');

select * from standardize_address(
        'select seq, word::text, stdword::text, token from lex order by id',
        'select seq, word::text, stdword::text, token from gaz order by id',
        'select * from rules order by id',
        'select 0::int4 as id, ''116 commonwealth ave apt a''::text as micro, ''west concord, ma 01742''::text as macro');
```

## How the Parser Works

The parser works from right to left looking first at the macro elements 
for postcode, state/province, city, and then looks micro elements to determine
if we are dealing with a house number street or intersection or landmark.
It currently does not look for a country code or name, but that could be
introduced in the future.

### Country code

Assumed to be US or CA based on:

    postcode as US or Canada
    state/province as US or Canada
    else US

### Postcode/zipcode

These are recognized using Perl compatible regular expressions.
These regexs are currently in the `parseaddress-api.c` and are relatively
simple to make changes to if needed.

### State/Province

These are recognized using Perl compatible regular expressions.
These regexs are currently in the parseaddress-api.c but could get moved
into includes in the future for easier maintenance.

### City name

This part is rather complicated and there are lots of issues around ambiguities
as to where to split a series of tokens when a token might belong to either
the city or the street name. The current strategy follows something like this:

1. if we have a state, then get the city regex for that state
2. if we can match that to the end of our remaining address string then
   extract the city name and continue.
3. if we do not have a state or fail to match it then
   cycle through a series of regex patterns that try to separate the city
   from the street, stop and extract the city if we match

### Number street name

1. check for a leading house number, and extract that
2. if there is an '@' then split the string on the '@' into street and
   street2 else put the rest into street


## Managing the regexes

The regexes are used to recognize US states and Canadian provinces
and USPS city names.

### City regexes
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


