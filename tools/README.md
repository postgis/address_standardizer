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
* **Streaming sem Descompactação em Disco:** Mantém apenas o arquivo ZIP compactado em cache e transmite os registros CSV descompactados diretamente pela memória, sem precisar expandir arquivos de texto gigantes no disco rígido.
* **Carga em Alta Velocidade:** Insere mais de **70.000 registros/segundo** usando o protocolo nativo `COPY` do PostgreSQL.
* **Indexação Espacial Automática:** Cria os índices espaciais `GIST (geom)` e `GIN (trigramas)` ao finalizar a carga.


### Exemplos de Uso:

```bash
# 1. Importar um estado completo (Ex: Pará, São Paulo, Rio de Janeiro)
python3 tools/import_cnefe.py --uf PA
python3 tools/import_cnefe.py --uf SP
python3 tools/import_cnefe.py --uf RJ

# 2. Testar importando apenas os primeiros 5.000 registros
python3 tools/import_cnefe.py --uf SP --limit 5000

# 3. Especificar uma pasta personalizada para guardar os downloads do IBGE
python3 tools/import_cnefe.py --uf MG --dest ./downloads_cnefe
```

---

## Variáveis de Ambiente Suportadas (`.env`)

Você pode configurar no seu arquivo `.env`:

```bash
POSTGRES_DB=address_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_PORT=5432

# Diretórios de armazenamento (podem apontar para disco local ou volume externo)
POSTGRES_DATA_DIR=./.pgdata
CNEFE_DOWNLOAD_DIR=./downloads_cnefe
```

