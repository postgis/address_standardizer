ARG POSTGRES_MAJOR=15
ARG POSTGIS_VERSION=3.5

FROM postgis/postgis:${POSTGRES_MAJOR}-${POSTGIS_VERSION} AS runtime
ARG POSTGRES_MAJOR

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-${POSTGRES_MAJOR} \
    && rm -rf /var/lib/apt/lists/*

FROM runtime AS builder
ARG POSTGRES_MAJOR

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpcre2-dev \
        postgresql-server-dev-${POSTGRES_MAJOR} \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src/address_standardizer
COPY . .
RUN make PG_CONFIG=/usr/lib/postgresql/${POSTGRES_MAJOR}/bin/pg_config with_llvm=no -j"$(nproc)" \
    && make PG_CONFIG=/usr/lib/postgresql/${POSTGRES_MAJOR}/bin/pg_config with_llvm=no install

FROM runtime
ARG POSTGRES_MAJOR

COPY --from=builder \
    /usr/lib/postgresql/${POSTGRES_MAJOR}/lib/address_standardizer.so \
    /usr/lib/postgresql/${POSTGRES_MAJOR}/lib/address_standardizer.so
COPY --from=builder \
    /usr/share/postgresql/${POSTGRES_MAJOR}/extension/address_standardizer* \
    /usr/share/postgresql/${POSTGRES_MAJOR}/extension/
