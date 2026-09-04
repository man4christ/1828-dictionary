This dataset was built by forking the original 1828 Dictionary project from [DataWar](https://github.com/DataWar/1828-dictionary). The source MySQL database was containerized, the schemas were recreated, the original data was imported, and the necessary indexes were added. The dictionary data was then exported as NDJSON and transformed into a normalized JSON format. During this process, the 1828 and 1844 dictionaries were normalized to share a common data structure, making them easier to consume programmatically. Support for the 1913 dictionary has been left as a future enhancement.

# Webster Dictionaries — MySQL Starter

This starter keeps the original SQL dumps in MySQL format. There is no SQL
translation layer: schema, insert, and index files are sent directly to MySQL.

## Expected layout

```text
.
├── docker-compose.yml
├── Makefile
├── .env
├── scripts/
│   └── first_insert.py
├── 01-database-schema/
│   ├── dictionary_webster1828.sql
│   ├── dictionary_webster1844.sql
│   ├── dictionary_webster1913_alt.sql
│   ├── dictionary_webster1913_definitions.sql
│   └── dictionary_webster1913_words.sql
├── 02-database-insert/
│   └── ...same five names...
├── 03-database-indexing/
│   └── ...same five names...
└── data/
    └── mysql/
```

Your database files live in `./data/mysql` and are bind-mounted to
`/var/lib/mysql` inside the container. `make down` therefore stops/removes the
container without deleting the database.

## Setup

```bash
cp .env.example .env
make up
```

Defaults are intentionally simple local-development credentials. Change them
in `.env` if desired.

## Initial load

For a large dump, load rows before building secondary indexes:

```bash
make schemas
make test-inserts
make inserts
make indexes
```

Or:

```bash
make load
```

`make load` runs `schemas -> inserts -> indexes`.

## Bulk targets

```bash
make schemas
make indexes
make inserts
make test-inserts
make truncates
make exports
```

## Individual table targets

Every dictionary has the same target pattern:

```bash
make schema-dictionary_webster1828
make test-insert-dictionary_webster1828
make insert-dictionary_webster1828
make index-dictionary_webster1828
make truncate-dictionary_webster1828
```

Available table names:

```text
dictionary_webster1828
dictionary_webster1844
dictionary_webster1913_alt
dictionary_webster1913_definitions
dictionary_webster1913_words
```

## Safe single-row insert tests

A test target does **not** truncate or modify the real table.

For example:

```bash
make test-insert-dictionary_webster1828
```

The helper reads only the first tuple from the first `INSERT INTO` statement
and sends SQL equivalent to:

```sql
START TRANSACTION;
CREATE TEMPORARY TABLE `__insert_test_dictionary_webster1828`
  LIKE `dictionary_webster1828`;

INSERT INTO `__insert_test_dictionary_webster1828` (...columns...)
VALUES (...first real row from dump...);

SELECT COUNT(*) AS inserted_rows
FROM `__insert_test_dictionary_webster1828`;

ROLLBACK;
```

Expected output includes:

```text
inserted_rows
1
```

This validates a real source row against the real table definition without
risking existing dictionary data or primary-key collisions.

## Truncation

Truncation is deliberately explicit:

```bash
make truncate-dictionary_webster1844
```

To truncate all five tables:

```bash
make truncates
make exports
```

These commands really delete table contents. They do not delete the table
schema.

## NDJSON exports

Export all five tables:

```bash
make exports
```

Or export one table:

```bash
make export-dictionary_webster1828
make export-dictionary_webster1844
make export-dictionary_webster1913_alt
make export-dictionary_webster1913_definitions
make export-dictionary_webster1913_words
```

Files are written to:

```text
exports/dictionary_webster1828.ndjson
exports/dictionary_webster1844.ndjson
exports/dictionary_webster1913_alt.ndjson
exports/dictionary_webster1913_definitions.ndjson
exports/dictionary_webster1913_words.ndjson
```

Each line is one complete JSON object from one database row. The three Webster
1913 tables remain separate raw exports for now; they can be joined or composed
into a higher-level dictionary object later.

The export uses MySQL's `JSON_OBJECT()` directly, so embedded quotes, HTML,
newlines, and other string content are JSON-escaped by MySQL rather than by a
custom conversion script.

## Persistence

Safe across restarts:

```bash
make down
make up
```

The data remains under:

```text
./data/mysql
```

To deliberately delete the entire local MySQL data directory:

```bash
make clean-data
```

## Other commands

```bash
make mysql
make logs
make status
make restart
make down
```

## Split phpMyAdmin dump files

phpMyAdmin dumps often initialize variables near the start of the original
file and restore them near the end, for example:

```sql
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
```

Because your schema/index sections are separate files and run in separate
connections, the Makefile initializes those `@OLD_*` variables before each
schema/index file. This lets the split files remain independently runnable.

## Large INSERT statements

The container and MySQL client are configured with a 256 MB maximum packet for
large dump statements. If one individual SQL statement is larger than that,
increase `--max-allowed-packet` in both `docker-compose.yml` and the Makefile.
