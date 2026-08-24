#
# address_standardizer
#
EXTENSION = address_standardizer
DATA_EXTENSION = address_standardizer_data_us
DATA_EXTENSION_BR = address_standardizer_data_br

#
# To set the version, edit the default in the control file
#
AS_VERSION = $(shell grep default $(EXTENSION).control | cut -f2 -d'=' | tr -d "' ")

#
# Use default PostgreSQL or change this to point to the
# install you are building against
#
PG_CONFIG = pg_config
PYTHON ?= python3

MODULE_big = $(EXTENSION)
DATA = $(DATA_EXTENSION).control $(DATA_EXTENSION_BR).control

DISTNAME = $(EXTENSION)-$(AS_VERSION)
DISTARCHIVE = $(DISTNAME).tar.gz

SRCS = $(wildcard src/*.c)
OBJS = $(SRCS:.c=.o)

DATA_built = \
	data/$(EXTENSION)--$(AS_VERSION).sql \
	data/$(EXTENSION)--ANY--$(AS_VERSION).sql \
	data/$(DATA_EXTENSION)--$(AS_VERSION).sql \
	data/$(DATA_EXTENSION)--ANY--$(AS_VERSION).sql \
	data/$(DATA_EXTENSION_BR)--$(AS_VERSION).sql \
	data/$(DATA_EXTENSION_BR)--ANY--$(AS_VERSION).sql

REGRESS_OPTS = --inputdir=test --outputdir=test
REGRESS = \
	init-extensions \
	debug_standardize_address \
	parseaddress \
	standardize_address_1 \
	standardize_address_2 \
	standardize_address_br \
	security_bounds

#PG_LIBS
#LIBS +=

PG_CPPFLAGS += -DAS_VERSION=\"$(AS_VERSION)\" -DPCRE_VERSION=2
#PG_CFLAGS +=
SHLIB_LINK += -lpcre2-8

EXTRA_CLEAN = \
	$(DATA_built) \
	data/$(EXTENSION)_core.sql \
	data/$(DATA_EXTENSION)_core.sql \
	data/$(DATA_EXTENSION_BR)_core.sql \
	test/rules_api_test \
	test/rules_api_test.exe \
	$(DISTARCHIVE)

ifdef DEBUG
COPT += -O0 -Werror -g
endif

all: $(DATA_built)

data:
	mkdir -p $@

data/$(EXTENSION)_core.sql: sql/01_types.sql sql/12_functions.sql | data
	cat $^ > $@

data/$(DATA_EXTENSION)_core.sql: sql/13_us_lex.sql sql/14_us_gaz.sql sql/15_us_rules.sql sql/16_data_extension.sql | data
	cat $^ > $@

data/$(DATA_EXTENSION_BR)_core.sql: sql/23_br_lex.sql sql/24_br_gaz.sql sql/25_br_rules.sql sql/26_br_data_extension.sql | data
	cat $^ > $@

data/$(EXTENSION)--$(AS_VERSION).sql: data/$(EXTENSION)_core.sql | data
	cat $^ > $@

data/$(EXTENSION)--ANY--$(AS_VERSION).sql: sql/12_functions.sql | data
	cat $^ > $@

data/$(DATA_EXTENSION)--$(AS_VERSION).sql: data/$(DATA_EXTENSION)_core.sql | data
	cat $^ > $@

data/$(DATA_EXTENSION)--ANY--$(AS_VERSION).sql: data/$(DATA_EXTENSION)_core.sql | data
	cat $^ > $@

data/$(DATA_EXTENSION_BR)--$(AS_VERSION).sql: data/$(DATA_EXTENSION_BR)_core.sql | data
	cat $^ > $@

data/$(DATA_EXTENSION_BR)--ANY--$(AS_VERSION).sql: data/$(DATA_EXTENSION_BR)_core.sql | data
	cat $^ > $@


.PHONY: dist check installcheck installcheck-latin1 test-rules-api test-br-data-generator
dist:
	git archive --prefix=$(DISTNAME)/ HEAD | gzip > $(DISTARCHIVE)


PGXS := $(shell $(PG_CONFIG) --pgxs)
include $(PGXS)


# override pgxs check target and perform in-place extension check
test-rules-api: test/rules_api_test
	./test/rules_api_test

test-br-data-generator:
	$(PYTHON) test/test_generate_br_data.py -q

# gettext() lives in libc on glibc/Linux; other ports with NLS need -lintl
ifeq ($(enable_nls),yes)
ifneq ($(PORTNAME),linux)
RULES_API_TEST_LIBS = -lintl
endif
endif

test/rules_api_test: test/rules_api_test.c src/gamma.c src/err_param.c src/pagc_tools.c src/standard.c src/tokenize.c src/lexicon.c src/hash.c src/analyze.c src/export.c src/pagc_api.h src/pagc_std_api.h src/gamma.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(PG_CPPFLAGS) -DPAGC_STANDALONE -ffunction-sections -Isrc -I$(shell $(PG_CONFIG) --includedir-server) -o $@ test/rules_api_test.c src/gamma.c src/err_param.c src/pagc_tools.c src/standard.c src/tokenize.c src/lexicon.c src/hash.c src/analyze.c src/export.c -Wl,--gc-sections -L$(shell $(PG_CONFIG) --pkglibdir) -lpgcommon -lpgport $(RULES_API_TEST_LIBS)

installcheck: test-rules-api test-br-data-generator

installcheck-latin1:
	sh tools/run-latin1-check.sh

check: test-rules-api test-br-data-generator
	PG_CONFIG="$(PG_CONFIG)" MAKE="$(MAKE)" sh tools/run-check.sh
