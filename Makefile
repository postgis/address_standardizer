#
# address_standardizer
#
EXTENSION = address_standardizer
DATA_EXTENSION = address_standardizer_data_us

#
# To set the version, edit the default in the control file
#
AS_VERSION = $(shell grep default $(EXTENSION).control | cut -f2 -d'=' | tr -d "' ")

#
# Use default PostgreSQL or change this to point to the
# install you are building against
#
PG_CONFIG = pg_config

MODULE_big = $(EXTENSION)
DATA = $(DATA_EXTENSION).control

DISTNAME = $(EXTENSION)-$(AS_VERSION)

SRCS = $(wildcard src/*.c)
OBJS = $(SRCS:.c=.o)

DATA_built = \
	data/$(EXTENSION)--$(AS_VERSION).sql \
	data/$(EXTENSION)--ANY--$(AS_VERSION).sql \
	data/$(DATA_EXTENSION)--$(AS_VERSION).sql \
	data/$(DATA_EXTENSION)--ANY--$(AS_VERSION).sql

REGRESS_OPTS = --inputdir=test --outputdir=test
REGRESS = \
	init-extensions \
	debug_standardize_address \
	parseaddress \
	standardize_address_1 \
	standardize_address_2

#PG_LIBS
#LIBS +=

PG_CPPFLAGS += -DAS_VERSION=\"$(AS_VERSION)\" -DPCRE_VERSION=2
#PG_CFLAGS +=
SHLIB_LINK += -lpcre2-8


EXTRA_CLEAN = $(DATA_built) data/$(EXTENSION)_core.sql data/$(DATA_EXTENSION)_core.sql

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

data/$(EXTENSION)--$(AS_VERSION).sql: data/$(EXTENSION)_core.sql | data
	cat $^ > $@

data/$(EXTENSION)--ANY--$(AS_VERSION).sql: sql/12_functions.sql | data
	cat $^ > $@

data/$(DATA_EXTENSION)--$(AS_VERSION).sql: data/$(DATA_EXTENSION)_core.sql | data
	cat $^ > $@

data/$(DATA_EXTENSION)--ANY--$(AS_VERSION).sql: data/$(DATA_EXTENSION)_core.sql | data
	cat $^ > $@


.PHONY: dist check
dist:
	git archive --prefix=$(DISTNAME)/ HEAD | gzip > $(DISTNAME).tar.gz


PGXS := $(shell $(PG_CONFIG) --pgxs)
include $(PGXS)


# override pgxs check target and perform in-place extension check
check:
	PG_CONFIG="$(PG_CONFIG)" MAKE="$(MAKE)" sh tools/run-check.sh
