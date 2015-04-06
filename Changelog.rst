0.7.2 (23-Jan-2015)

  Fixed various issues, including:

  * Do not error on tables whose names start with 'public' (#109)

  * Deal properly with inherited constraints in children tables (#102)

  * Handle external languages like plv8 correctly (#97)

  * Correct quoting of mixed case constraint names (#83)

  * Avoid problems with certain complex index definitions (#98)

  * Have dbtoyaml output correctly a table with an embedded period in
    the name and having an associated sequence (#79)

  * Use relative paths in database summary for ``--multiple-files``
    (#93)

  * Support mapping of indexes on materialized views (#82)

0.7.1 (5-Dec-2013)

  * Moved ``config.yaml`` under ``pyrseas`` directory and use
    ``package_data`` to install (#77)

  * yamltodb output to a file is encoded using utf-8 (#78)


0.7.0 (25-Nov-2013)

  * Added support for:

    - Postgres 9.3, specifically

      + EVENT TRIGGER
      + MATERIALIZED VIEWS

    - CLUSTER
    - Partial indexes
    - Storage parameters in CREATE and ALTER TABLE
    - ALTER COLUMN SET STATISTICS
    - LEAKPROOF qualifier for FUNCTIONs
    - YAML multi-line string formatting for view definitions,
      function source text and object comments

  * Configuration files

    All Pyrseas utilities can now use YAML-formatted configuration
    files, in addition to command line options

  * Multiple-file input or output

    Spread database object information across a version control
    repository

  * Data export/import

    Load a database with static data in production or data subsets
    for testing

  * dbtoyaml/yamltodb

    - Added --quote-reserved option to yamltodb
    - Exclude arguments from sfunc and finalfunc attributes of
      aggregate functions (#54)
    - Correct generation of SQL for functions with DEFAULT
      arguments (#52)

  * Augmenter

    New utility (dbaugment) to consistently add objects to an
    existent database.  This is currently an experimental
    feature and covers adding audit columns to tables.

  * TTM-inspired relational interface

    A new interface to Postgres, inspired by *The Third Manifesto*


0.6.1 (31-Jan-2013)

  * Add support for INSTEAD OF triggers on views (#50).

  * Eliminated yamltodb generation of spurious REVOKE/GRANT commands
    (#51).

  * Removed setuptools from setup.py install_requires.


0.6.0 (26-Oct-2012)

  * Added support for:

    - EXTENSIONs
    - COLLATIONs
    - OWNER information
    - Access privileges (GRANT and REVOKE)
    - TABLESPACEs for tables, primary keys and indexes
    - MATCH attributes for foreign keys (#34)
    - ALTER composite TYPE ADD/DROP/RENAME ATTRIBUTE
    - ENUMs with no labels (#31)
    - UNLOGGED tables (#45)
    - CREATE FUNCTION SET configuration_parameter (#46)
    - PostgreSQL 9.2

  * Correctly support index functions/expressions (#3, #44).

  * Schema-qualify composite types when dropping or renaming
    attributes (#47)

  * Fix DbConnection exception handling under Python 3 (#25).

  * dbtoyaml

    - Fix -t option to output sequences owned by table and the schema
      description.
    - Use pg_user_mappings view to allow usage by non-superusers.

  * yamltodb

    - Schema-qualify table when dropping columns (#26).
    - Correct column drop/add case in middle of table (#8).
    - Fix adding and dropping of columns in inherited tables (#33).
    - Enable renaming of indexes (#38).
    - Ignore all temp schemas (#37)

  * dbtoyaml/yamltodb

    - Give PGUSER precedence over USER environment variable.

  * Testing

    - Added support, via Tox, for testing against multiple
      PostgreSQL/Python combinations

    - Changes and documentation for testing on Microsoft Windows


0.5.0 (10-Mar-2012)

  * Added support for:

    - TEXTSEARCH parsers, dictionaries, configurations and templates
    - FOREIGN DATA WRAPPERs, SERVERs, USER MAPPINGs and FOREIGN TABLEs
    - ROWS clause in set-returning functions (issue #11)
    - Deferrable/deferred constraints (#13)
    - CATEGORY and PREFERRED clauses for TYPEs,
      SORTOP clause for AGGREGATEs
      HASHES and MERGES clauses for OPERATORs (#15)
    - Operator class qualifiers for INDEXes (#16)
    - Python 3.2 and later

  * Correct schema normalization for constraints (#9) and indexes.

  * Fix COMMENTs generated for constraints (#12).

  * Fix DEFAULT clause for OPERATOR CLASS.

  * dbtoyaml

    - When restricting to specific schemas or tables, include
      non-schema objects (e.g., languages).

  * yamltodb

    - Add -n/--schema option (#6).
    - Add -u/--update option to apply SQL statements to target
      database.
    - Exclude database-wide objects when -n/--schema is used (#21).
    - Allow YAML spec argument to be read from standard input.

  * dbtoyaml/yamltodb

    - Add -o/--output option
    - Add -W/--password option (#18)


0.4.1 (27-Oct-2011)

  * Make the initial SET search_path persistent.

  * Correct exclusion of PG internal schemas in various queries.

  * Fix generation of COMMENTs with single quotes in the text.

  * For inherited tables, only generate constraints that are defined
    locally.

  * Correct generation of ALTER TABLE ADD/DROP COLUMN when input
    columns are in different order than original.

  * Support PG 9.1 (add description for PL/pgSQL language).


0.4.0 (26-Sep-2011)

  * Added support for:

    - CASTs
    - CONSTRAINT TRIGGERs
    - CONVERSIONs
    - OPERATORs, OPERATOR CLASSes and OPERATOR FAMILies
    - Dynamically loaded C language functions
    - Composite and base TYPEs

  * Clean up and enhance documentation and redundant methods.

  * Use obj_description/col_description functions instead of querying
    pg_description directly.


0.3.1 (26-Aug-2011)

  * Added workaround for incorrect assumption that 'public' schema is
    always present (issue #4).

  * Added support for delimited (or quoted) identifiers, e.g., those
    with embedded spaces, upper case characters, etc. (except for SQL
    keywords) (issue #5).


0.3.0 (30-Jun-2011)

  * Added support for:

    - AGGREGATE functions
    - DOMAINs
    - ENUMerated TYPEs
    - Functions returning table row types
    - INDEXes on expressions (issue #3)
    - Rewrite RULEs
    - SECURITY DEFINER functions
    - TRIGGERs

 * Enhanced host/port defaults to use sockets, resulting in noticeable
   performance improvement.


0.2.1 (7-Jun-2011)

  * Fixed problem with mapping a FOREIGN KEY in a table with a dropped
    column (issue #2).


0.2.0 (19-May-2011)

  * Added support for:

    - COMMENTs on schemas, tables, columns and functions
    - FOREIGN KEY ON UPDATE and ON DELETE actions
    - ALTER TABLE RENAME COLUMN and enhanced support for other ALTER
      object RENAME statements.
    - VIEWs
    - INHERITed tables, and by extension, partitioned tables.
    - PROCEDURAL LANGUAGEs
    - FUNCTIONs.

  * Added files for release via PGXN.
  * Added support for testing against multiple PostgreSQL versions.
  * Fixed cross-schema REFERENCES failure in dbtoyaml (issue #1).


0.1.0 (5-Apr-2011)

  * Initial release

    - dbtoyaml and yamltodb support PostgreSQL schemas, tables,
      sequences, check constraints, primary keys, foreign keys, unique
      constraints and indexes.
