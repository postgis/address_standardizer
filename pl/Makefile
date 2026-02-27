#
# Preserved for posterity, these scripts and data files
# are used to build some regex pattern header files that are
# used in the C code.
#
# mk-city-regex.pl => parseaddress-stcities.h
# mk-st-regexp.pl  => parseaddress-regex.h
#
# The pre-built copies of parseaddress-*.h in ./src are fine.
#

parseaddress-stcities.h: mk-city-regex.pl usps-st-city-name.txt
	$(PERL) mk-city-regex.pl > $@

parseaddress-regex.h: mk-st-regexp.pl
	$(PERL) mk-st-regexp.pl > $@

usps-st-city-name.txt: usps-st-city-adds.txt usps-st-city-orig.txt
	cat $^ > $@
