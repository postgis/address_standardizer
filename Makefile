#
# address_standardizer
#
EXTENSION = address_standardizer

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

SRCS = $(wildcard src/*.c)
OBJS = $(SRCS:.c=.o)

DATA = \
	data/$(EXTENSION).sql \
	data/$(EXTENSION)_upgrade.sql \
	data/$(EXTENSION)--$(AS_VERSION).sql \
	data/$(EXTENSION)--ANY--$(AS_VERSION).sql

REGRESS_OPTS = --inputdir=test --outputdir=test
REGRESS = \
	debug_standardize_address \
	parseaddress \
	standardize_address_1 \
	standardize_address_2

PG_CFLAGS += -DAS_VERSION=\"$(AS_VERSION)\"
PG_CFLAGS += -DPCRE_VERSION=2
PG_LDFLAGS += -lpcre2-8

#PG_LIBS
#LIBS += 
#SHLIB_LINK := $(LIBS)

EXTRA_CLEAN = $(DATA)

ifdef DEBUG
COPT += -O0 -Werror -g
endif

all: $(DATA)

data/$(EXTENSION).sql: $(wildcard sql/*.sql)
	cat $^ > $@

data/$(EXTENSION)_upgrade.sql: $(wildcard sql/1*.sql)
	cat $^ > $@

data/$(EXTENSION)--$(AS_VERSION).sql: data/$(EXTENSION).sql
	cat $^ > $@

data/$(EXTENSION)--ANY--$(AS_VERSION).sql: data/$(EXTENSION)_upgrade.sql
	cat $^ > $@


PGXS := $(shell $(PG_CONFIG) --pgxs)
include $(PGXS)


