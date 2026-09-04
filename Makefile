SHELL := /bin/bash

-include .env

COMPOSE ?= docker compose
SERVICE ?= mysql

MYSQL_DATABASE ?= webster
MYSQL_USER ?= webster
MYSQL_PASSWORD ?= webster
MYSQL_ROOT_PASSWORD ?= root

SCHEMA_DIR := 01-database-schema
INSERT_DIR := 02-database-insert
INDEX_DIR := 03-database-indexing
EXPORT_DIR := exports

TABLES := \
	dictionary_webster1828 \
	dictionary_webster1844 \
	dictionary_webster1913_alt \
	dictionary_webster1913_definitions \
	dictionary_webster1913_words

MYSQL_BASE := $(COMPOSE) exec -T $(SERVICE) mysql \
	--default-character-set=utf8mb4 \
	--max-allowed-packet=256M \
	-u$(MYSQL_USER) \
	-p$(MYSQL_PASSWORD) \
	$(MYSQL_DATABASE)

MYSQL_INTERACTIVE := $(COMPOSE) exec $(SERVICE) mysql \
	--default-character-set=utf8mb4 \
	-u$(MYSQL_USER) \
	-p$(MYSQL_PASSWORD) \
	$(MYSQL_DATABASE)

MYSQL_EXPORT := $(COMPOSE) exec -T $(SERVICE) mysql \
	--default-character-set=utf8mb4 \
	--max-allowed-packet=256M \
	--batch \
	--raw \
	--skip-column-names \
	-u$(MYSQL_USER) \
	-p$(MYSQL_PASSWORD) \
	$(MYSQL_DATABASE)

# A split phpMyAdmin index file may restore these @OLD_* variables at EOF.
# Initialize them for every independent file execution so those footers work.
define MYSQL_SESSION_HEADER
SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT;
SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS;
SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION;
endef
export MYSQL_SESSION_HEADER

.PHONY: help up down restart logs status wait mysql \
	schemas indexes inserts test-inserts truncates exports load clean-data

help:
	@echo "Container:"
	@echo "  make up                         Start MySQL"
	@echo "  make down                       Stop MySQL"
	@echo "  make restart                    Restart MySQL"
	@echo "  make logs                       Follow MySQL logs"
	@echo "  make status                     Show container status"
	@echo "  make mysql                      Open MySQL shell"
	@echo
	@echo "Bulk database operations:"
	@echo "  make schemas                    Apply every schema"
	@echo "  make inserts                    Load every insert dump"
	@echo "  make indexes                    Apply every index file"
	@echo "  make test-inserts               Test one real row from every insert dump"
	@echo "  make truncates                  TRUNCATE every dictionary table"
	@echo "  make exports                    Export every table as NDJSON"
	@echo "  make load                       schemas -> inserts -> indexes"
	@echo
	@echo "Per-table operations:"
	@echo "  make schema-<table>"
	@echo "  make insert-<table>"
	@echo "  make index-<table>"
	@echo "  make test-insert-<table>"
	@echo "  make truncate-<table>"
	@echo "  make export-<table>             Export one table as NDJSON"
	@echo
	@echo "Example:"
	@echo "  make test-insert-dictionary_webster1828"

up:
	@mkdir -p data/mysql
	$(COMPOSE) up -d $(SERVICE)
	@$(MAKE) --no-print-directory wait

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart $(SERVICE)
	@$(MAKE) --no-print-directory wait

logs:
	$(COMPOSE) logs -f $(SERVICE)

status:
	$(COMPOSE) ps

wait:
	@echo "Waiting for MySQL..."
	@until $(COMPOSE) exec -T $(SERVICE) mysqladmin ping \
		-h 127.0.0.1 -u$(MYSQL_USER) -p$(MYSQL_PASSWORD) --silent >/dev/null 2>&1; do \
		sleep 1; \
	done
	@echo "MySQL is ready."

mysql: wait
	$(MYSQL_INTERACTIVE)

schemas: $(addprefix schema-,$(TABLES))

indexes: $(addprefix index-,$(TABLES))

inserts: $(addprefix insert-,$(TABLES))

test-inserts: $(addprefix test-insert-,$(TABLES))

truncates: $(addprefix truncate-,$(TABLES))

exports: $(addprefix export-,$(TABLES))

# For a large initial import, create indexes after loading the rows.
load: schemas inserts indexes

schema-%: wait
	@test -f "$(SCHEMA_DIR)/$*.sql" || { echo "Missing $(SCHEMA_DIR)/$*.sql"; exit 1; }
	@echo "==> schema: $*"
	@{ printf '%s\n' "$$MYSQL_SESSION_HEADER"; cat "$(SCHEMA_DIR)/$*.sql"; } | $(MYSQL_BASE)

index-%: wait
	@test -f "$(INDEX_DIR)/$*.sql" || { echo "Missing $(INDEX_DIR)/$*.sql"; exit 1; }
	@echo "==> indexes: $*"
	@{ printf '%s\n' "$$MYSQL_SESSION_HEADER"; cat "$(INDEX_DIR)/$*.sql"; } | $(MYSQL_BASE)

insert-%: wait
	@test -f "$(INSERT_DIR)/$*.sql" || { echo "Missing $(INSERT_DIR)/$*.sql"; exit 1; }
	@echo "==> inserts: $*"
	@$(MYSQL_BASE) < "$(INSERT_DIR)/$*.sql"

# The test NEVER writes to the real table. It makes a temporary LIKE-table,
# inserts the first real tuple from the dump, verifies one row, and rolls back.
test-insert-%: wait
	@test -f "$(INSERT_DIR)/$*.sql" || { echo "Missing $(INSERT_DIR)/$*.sql"; exit 1; }
	@echo "==> test insert: $*"
	@python3 scripts/first_insert.py "$(INSERT_DIR)/$*.sql" "$*" | $(MYSQL_BASE)

truncate-%: wait
	@case " $(TABLES) " in *" $* "*) ;; *) echo "Unknown table: $*"; exit 1;; esac
	@echo "==> truncate: $*"
	@printf 'TRUNCATE TABLE `%s`;\n' "$*" | $(MYSQL_BASE)


# Export one JSON object per line. These are intentionally raw table exports;
# the three Webster 1913 tables can be composed into a richer structure later.
export-%: wait
	@case " $(TABLES) " in *" $* "*) ;; *) echo "Unknown table: $*"; exit 1;; esac
	@mkdir -p "$(EXPORT_DIR)"
	@case "$*" in \
		dictionary_webster1828) \
			query='SELECT JSON_OBJECT("id", id, "word", word, "length", length, "string", string, "_word", _word, "heading", heading, "content", content) FROM `dictionary_webster1828` ORDER BY `id`' ;; \
		dictionary_webster1844) \
			query='SELECT JSON_OBJECT("dictionary_webster1844_id", dictionary_webster1844_id, "byuid", byuid, "_word", _word, "pronounce", pronounce, "letter", letter, "page", page, "order", `order`, "definition", definition) FROM `dictionary_webster1844` ORDER BY `dictionary_webster1844_id`' ;; \
		dictionary_webster1913_alt) \
			query='SELECT JSON_OBJECT("alt_id", alt_id, "word_id", word_id, "word", word, "_word", _word, "phonetic", phonetic, "pronounce", pronounce) FROM `dictionary_webster1913_alt` ORDER BY `alt_id`' ;; \
		dictionary_webster1913_definitions) \
			query='SELECT JSON_OBJECT("definition_id", definition_id, "word_id", word_id, "rank", rank, "definition", definition, "extra", extra) FROM `dictionary_webster1913_definitions` ORDER BY `definition_id`' ;; \
		dictionary_webster1913_words) \
			query='SELECT JSON_OBJECT("word_id", word_id, "word", word, "_word", _word, "_word_", _word_, "pos", pos, "phonetic", phonetic, "pronounce", pronounce, "root", root, "page", page, "alt", alt) FROM `dictionary_webster1913_words` ORDER BY `word_id`' ;; \
	esac; \
	echo "==> export: $* -> $(EXPORT_DIR)/$*.ndjson"; \
	$(MYSQL_EXPORT) -e "$$query" > "$(EXPORT_DIR)/$*.ndjson"; \
	printf "    rows: "; wc -l < "$(EXPORT_DIR)/$*.ndjson"

# Deliberately removes the bind-mounted database files too.
# `make down` alone does NOT remove them.
clean-data: down
	rm -rf data/mysql
	mkdir -p data/mysql

.PHONY: json-dictionary_webster1828

json-dictionary_webster1828:
	@echo "==> building Webster 1828 JSON"
	python3 scripts/build_dictionary_webster1828.py


json-dictionary_webster1844:
	@echo "==> building Webster 1828 JSON"
	python3 scripts/build_dictionary_webster1844.py