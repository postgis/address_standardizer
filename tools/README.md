# Ferramentas Auxiliares (Tools)

Este diretório contém utilitários para geração de dados e geocodificação brasileira com PostGIS.

---

## 1. `generate_br_data.py` (Gerador de Léxico, Gazetteer e Regras PAGC)

Consome a **API Oficial de Localidades do IBGE** e compila os arquivos SQL da extensão `address_standardizer_data_br`:
* `sql/23_br_lex.sql`: Léxico com tipos de logradouro, complementos e conectores.
* `sql/24_br_gaz.sql`: Gazetteer com os **5.571 municípios** e **27 estados**.
* `sql/25_br_rules.sql`: Regras gramaticais PAGC para endereços brasileiros.
* `sql/26_br_data_extension.sql`: Manifesto de extensão PostgreSQL.

### Como executar:
```bash
python3 tools/generate_br_data.py
```

---

## 2. `import_cnefe.py` (Importador Oficial de Geocodificação IBGE CNEFE 2022)

Baixa os dados abertos de endereços e coordenadas GPS do **Censo 2022 do IBGE** e carrega no PostGIS com geometrias espaciais `Point(4326)` e índices de alta performance (`GiST` e `GIN Trigramas`).

### Funcionalidades:
* **Leitura Direta de `.env`:** Respeita as configurações de banco (`POSTGRES_DB`, `POSTGRES_USER`, etc.) e diretório de armazenamento.
* **Streaming sem Descompactação em Disco:** O arquivo ZIP original é mantido no disco no diretório configurado, enquanto a extração e transmissão dos registros CSV são feitas diretamente em memória (streaming via COPY), sem necessidade de gravar arquivos intermediários descompactados no disco rígido.
* **Cache Validado:** Downloads novos passam por verificação CRC completa; arquivos já validados no cache são reutilizados sem descompactar novamente todo o CSV.
* **Lotes Resilientes:** Importações de múltiplas UFs continuam após uma falha isolada, mostram o resumo das UFs com erro e terminam com código diferente de zero.
* **Carga em Alta Velocidade:** Insere mais de **70.000 registros/segundo** usando o protocolo nativo `COPY` do PostgreSQL.
* **Indexação Espacial Automática:** Cria os índices espaciais `GIST (geom)` e `GIN (trigramas)` ao finalizar a carga.


### Exemplos de Uso:

```bash
# 1. Importar um estado completo (Ex: Amapá, Pará, São Paulo)
python3 tools/import_cnefe.py --uf AP
python3 tools/import_cnefe.py --uf PA
python3 tools/import_cnefe.py --uf SP

# 2. Importar múltiplos estados específicos em sequência
python3 tools/import_cnefe.py --uf SP,RJ,MG

# 3. Importar o Brasil completo (todos os 27 estados do Censo 2022)
python3 tools/import_cnefe.py --uf BR
# ou
python3 tools/import_cnefe.py --all

# 4. Testar importando apenas os primeiros 5.000 registros por estado
python3 tools/import_cnefe.py --uf SP --limit 5000

# 5. Especificar uma pasta personalizada para guardar os downloads do IBGE
python3 tools/import_cnefe.py --uf MG --dest ./downloads_cnefe
```

---

## Variáveis de Ambiente Suportadas (`.env`)

Você pode configurar no seu arquivo `.env`:

```bash
POSTGRES_DB=address_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_PORT=5432

# Diretórios de armazenamento (podem apontar para disco local ou volume externo)
POSTGRES_DATA_DIR=./.pgdata
CNEFE_DOWNLOAD_DIR=./downloads_cnefe
```

---

## 3. Atualização / Migração de Bancos de Dados Existentes

O script `docker/init.sql` é executado pelo PostgreSQL automaticamente apenas na inicialização de um cluster novo (quando a pasta `.pgdata` está vazia).

Para aplicar ou atualizar as tabelas e regras do dataset brasileiro em uma base ou contêiner existente sem recriar o cluster:

```bash
docker exec -i postgis_br sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/init.sql'
```

Caso deseje reiniciar o cluster do zero (apagando os dados atuais):
```bash
# Execute a partir da raiz do repositório. Carregue .env antes de expandir POSTGRES_DATA_DIR.
set -a
. ./.env
set +a
docker compose down
rm -rf -- "${POSTGRES_DATA_DIR:-./.pgdata}"
docker compose up -d
```
