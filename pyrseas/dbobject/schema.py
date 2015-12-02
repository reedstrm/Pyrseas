# -*- coding: utf-8 -*-
"""
    pyrseas.dbobject.schema
    ~~~~~~~~~~~~~~~~~~~~~~~

    This defines two classes, Schema and SchemaDict, derived from
    DbObject and DbObjectDict, respectively.
"""
import os

from pyrseas.yamlutil import yamldump
from pyrseas.dbobject import DbObjectDict, DbObject
from pyrseas.dbobject import quote_id, split_schema_obj
from pyrseas.dbobject import commentable, ownable, grantable
from pyrseas.dbobject.dbtype import BaseType, Composite, Domain, Enum
from pyrseas.dbobject.table import Table, Sequence, View, MaterializedView
from pyrseas.dbobject.privileges import privileges_from_map


class Schema(DbObject):
    """A database schema definition, i.e., a named collection of tables,
    views, triggers and other schema objects."""

    keylist = ['name']
    objtype = 'SCHEMA'

    @property
    def allprivs(self):
        return 'UC'

    def extern_dir(self, root='.'):
        """Return the path to a directory to hold the schema objects.

        :return: directory path
        """
        (dir, ext) = os.path.splitext(os.path.join(root,
                                                   self.extern_filename()))
        return dir

    def to_map(self, dbschemas, opts):
        """Convert tables, etc., dictionaries to a YAML-suitable format

        :param dbschemas: dictionary of schemas
        :param opts: options to include/exclude schemas/tables, etc.
        :return: dictionary
        """
        if self.name == 'pyrseas':
            return {}
        no_owner = opts.no_owner
        no_privs = opts.no_privs
        schbase = {} if no_owner else {'owner': self.owner}
        if not no_privs and self.privileges:
            schbase.update({'privileges': self.map_privs()})
        if self.description is not None:
            schbase.update(description=self.description)

        schobjs = []
        seltbls = getattr(opts, 'tables', [])
        if hasattr(self, 'tables'):
            for objkey in self.tables:
                if not seltbls or objkey in seltbls:
                    obj = self.tables[objkey]
                    schobjs.append((obj, obj.to_map(dbschemas, opts)))

        def mapper(objtypes):
            if hasattr(self, objtypes):
                schemadict = getattr(self, objtypes)
                for objkey in schemadict:
                    if objtypes == 'sequences' or (
                            not seltbls or objkey in seltbls):
                        obj = schemadict[objkey]
                        schobjs.append((obj, obj.to_map(opts)))

        for objtypes in ['ftables', 'sequences', 'views', 'matviews']:
            mapper(objtypes)

        def mapper2(objtypes):
            if hasattr(self, objtypes):
                schemadict = getattr(self, objtypes)
                for objkey in schemadict:
                    obj = schemadict[objkey]
                    schobjs.append((obj, obj.to_map(no_owner)))

        if hasattr(opts, 'tables') and not opts.tables or \
                not hasattr(opts, 'tables'):
            for objtypes in ['conversions', 'domains',
                             'operators', 'operclasses', 'operfams',
                             'tsconfigs', 'tsdicts', 'tsparsers', 'tstempls',
                             'types', 'collations']:
                mapper2(objtypes)
            if hasattr(self, 'functions'):
                for objkey in self.functions:
                    obj = self.functions[objkey]
                    schobjs.append((obj, obj.to_map(no_owner, no_privs)))

        # special case for pg_catalog schema
        if self.name == 'pg_catalog' and not schobjs:
            return {}

        if hasattr(self, 'datacopy') and self.datacopy:
            dir = self.extern_dir(opts.data_dir)
            if not os.path.exists(dir):
                os.mkdir(dir)
            for tbl in self.datacopy:
                self.tables[tbl].data_export(dbschemas.dbconn, dir)

        if opts.multiple_files:
            dir = self.extern_dir(opts.metadata_dir)
            if not os.path.exists(dir):
                os.mkdir(dir)
            filemap = {}
            for obj, objmap in schobjs:
                if objmap is not None:
                    extkey = obj.extern_key()
                    filepath = os.path.join(dir, obj.extern_filename())
                    with open(filepath, 'a') as f:
                        f.write(yamldump({extkey: objmap}))
                    outobj = {extkey:
                              os.path.relpath(filepath, opts.metadata_dir)}
                    filemap.update(outobj)
            # always write the schema YAML file
            filepath = self.extern_filename()
            extkey = self.extern_key()
            with open(os.path.join(opts.metadata_dir, filepath), 'a') as f:
                f.write(yamldump({extkey: schbase}))
            filemap.update(schema=filepath)
            return {extkey: filemap}

        schmap = dict((obj.extern_key(), objmap) for obj, objmap in schobjs
                  if objmap is not None)
        schmap.update(schbase)
        return {self.extern_key(): schmap}

    @commentable
    @grantable
    @ownable
    def create(self):
        """Return SQL statements to CREATE the schema

        :return: SQL statements
        """
        return ["CREATE SCHEMA %s" % quote_id(self.name)]

    def data_import(self, opts):
        """Generate SQL to import data from the tables in this schema

        :param opts: options to include/exclude schemas/tables, etc.
        :return: list of SQL statements
        """
        stmts = []
        if hasattr(self, 'datacopy') and self.datacopy:
            dir = self.extern_dir(opts.data_dir)
            for tbl in self.datacopy:
                stmts.append(self.tables[tbl].data_import(dir))
        return stmts


PREFIXES = {'domain ': 'types', 'type': 'types', 'table ': 'tables',
            'view ': 'tables', 'sequence ': 'tables',
            'materialized view ': 'tables',
            'function ': 'functions', 'aggregate ': 'functions',
            'operator family ': 'operfams', 'operator class ': 'operclasses',
            'conversion ': 'conversions', 'text search dictionary ': 'tsdicts',
            'text search template ': 'tstempls',
            'text search parser ': 'tsparsers',
            'text search configuration ': 'tsconfigs',
            'foreign table ': 'ftables', 'collation ': 'collations'}
SCHOBJS1 = ['types', 'tables', 'ftables']
SCHOBJS2 = ['collations', 'conversions', 'functions', 'operators',
            'operclasses', 'operfams', 'tsconfigs', 'tsdicts', 'tsparsers',
            'tstempls']


class SchemaDict(DbObjectDict):
    "The collection of schemas in a database.  Minimally, the 'public' schema."

    cls = Schema
    query = \
        """SELECT nspname AS name, rolname AS owner,
                  array_to_string(nspacl, ',') AS privileges,
                  obj_description(n.oid, 'pg_namespace') AS description
           FROM pg_namespace n
                JOIN pg_roles r ON (r.oid = nspowner)
           WHERE nspname NOT IN ('information_schema', 'pg_toast')
                 AND nspname NOT LIKE 'pg_temp\_%'
                 AND nspname NOT LIKE 'pg_toast_temp\_%'
           ORDER BY nspname"""

    def from_map(self, inmap, newdb):
        """Initialize the dictionary of schemas by converting the input map

        :param inmap: the input YAML map defining the schemas
        :param newdb: collection of dictionaries defining the database

        Starts the recursive analysis of the input map and
        construction of the internal collection of dictionaries
        describing the database objects.
        """
        for key in inmap:
            (objtype, spc, sch) = key.partition(' ')
            if spc != ' ' or objtype != 'schema':
                raise KeyError("Unrecognized object type: %s" % key)
            schema = self[sch] = Schema(name=sch)
            inschema = inmap[key]
            objdict = {}
            for key in sorted(inschema.keys()):
                mapped = False
                for prefix in PREFIXES:
                    if key.startswith(prefix):
                        otype = PREFIXES[prefix]
                        if otype not in objdict:
                            objdict[otype] = {}
                        objdict[otype].update({key: inschema[key]})
                        mapped = True
                        break
                # Needs separate processing because it overlaps
                # operator classes and operator families
                if not mapped and key.startswith('operator '):
                    otype = 'operators'
                    if otype not in objdict:
                        objdict[otype] = {}
                    objdict[otype].update({key: inschema[key]})
                    mapped = True
                elif key in ['oldname', 'owner', 'description']:
                    setattr(schema, key, inschema[key])
                    mapped = True
                elif key == 'privileges':
                    schema.privileges = privileges_from_map(
                        inschema[key], schema.allprivs, schema.owner)
                    mapped = True
                if not mapped and key != 'schema':
                    raise KeyError("Expected typed object, found '%s'" % key)

            for objtype in SCHOBJS1:
                if objtype in objdict:
                    subobjs = getattr(newdb, objtype)
                    subobjs.from_map(schema, objdict[objtype], newdb)
            for objtype in SCHOBJS2:
                if objtype in objdict:
                    subobjs = getattr(newdb, objtype)
                    subobjs.from_map(schema, objdict[objtype])

    def link_refs(self, db, datacopy):
        """Connect various schema objects to their respective schemas

        :param db: dictionary of dictionaries of all objects
        :param datacopy: dictionary of data copying info
        """
        def link_one(targdict, objtype, objkeys, subtype=None):
            schema = self[objkeys[0]]
            if subtype is None:
                subtype = objtype
            if not hasattr(schema, subtype):
                setattr(schema, subtype, {})
            objdict = getattr(schema, subtype)
            key = objkeys[1] if len(objkeys) == 2 else objkeys[1:]
            objdict.update({key: targdict[objkeys]})

        targ = db.types
        for keys in targ:
            dbtype = targ[keys]
            if isinstance(dbtype, Domain):
                link_one(targ, 'types', keys, 'domains')
            elif isinstance(dbtype, Enum) or isinstance(dbtype, Composite) \
                    or isinstance(dbtype, BaseType):
                link_one(targ, 'types', keys)
        targ = db.tables
        for keys in targ:
            table = targ[keys]
            type_ = 'tables'
            if isinstance(table, Table):
                link_one(targ, type_, keys)
            elif isinstance(table, Sequence):
                link_one(targ, type_, keys, 'sequences')
            elif isinstance(table, MaterializedView):
                link_one(targ, type_, keys, 'matviews')
            elif isinstance(table, View):
                link_one(targ, type_, keys, 'views')
        targ = db.functions
        for keys in targ:
            func = targ[keys]
            link_one(targ, 'functions', keys)
            if hasattr(func, 'returns'):
                rettype = func.returns
                if rettype.upper().startswith("SETOF "):
                    rettype = rettype[6:]
                (retsch, rettyp) = split_schema_obj(rettype, keys[0])
                if (retsch, rettyp) in db.tables:
                    deptbl = db.tables[(retsch, rettyp)]
                    if not hasattr(func, 'dependent_table'):
                        func.dependent_table = deptbl
                    if not hasattr(deptbl, 'dependent_funcs'):
                        deptbl.dependent_funcs = []
                    deptbl.dependent_funcs.append(func)
        for objtype in ['operators', 'operclasses', 'operfams', 'conversions',
                        'tsconfigs', 'tsdicts', 'tsparsers', 'tstempls',
                        'ftables', 'collations']:
            targ = getattr(db, objtype)
            for keys in targ:
                link_one(targ, objtype, keys)
        for key in datacopy:
            if not key.startswith('schema '):
                raise KeyError("Unrecognized object type: %s" % key)
            schema = self[key[7:]]
            if not hasattr(schema, 'datacopy'):
                schema.datacopy = []
            for tbl in datacopy[key]:
                if hasattr(schema, 'tables') and tbl in schema.tables:
                    schema.datacopy.append(tbl)

    def to_map(self, opts):
        """Convert the schema dictionary to a regular dictionary

        :param opts: options to include/exclude schemas/tables, etc.
        :return: dictionary

        Invokes the `to_map` method of each schema to construct a
        dictionary of schemas.
        """
        schemas = {}
        selschs = getattr(opts, 'schemas', [])
        for sch in self:
            if not selschs or sch in selschs:
                if hasattr(opts, 'excl_schemas') and opts.excl_schemas \
                        and sch in opts.excl_schemas:
                    continue
                schemas.update(self[sch].to_map(self, opts))

        return schemas

    def diff_map(self, inschemas):
        """Generate SQL to transform existing schemas

        :param input_map: a YAML map defining the new schemas
        :return: list of SQL statements

        Compares the existing schema definitions, as fetched from the
        catalogs, to the input map and generates SQL statements to
        transform the schemas accordingly.
        """
        stmts = []
        # check input schemas
        for sch in inschemas:
            insch = inschemas[sch]
            # does it exist in the database?
            if sch in self:
                stmts.append(self[sch].diff_map(insch))
            else:
                # check for possible RENAME
                if hasattr(insch, 'oldname'):
                    oldname = insch.oldname
                    try:
                        stmts.append(self[oldname].rename(insch.name))
                        del self[oldname]
                    except KeyError as exc:
                        exc.args = ("Previous name '%s' for schema '%s' "
                                    "not found" % (oldname, insch.name), )
                        raise
                else:
                    # create new schema
                    if insch.name not in ['pg_catalog']:
                        stmts.append(insch.create())
        # check database schemas
        for sch in self:
            # if missing and not 'public', drop it
            if sch not in ['public', 'pg_catalog'] and sch not in inschemas:
                self[sch].dropped = True
        return stmts

    def _drop(self):
        """Actually drop the schemas

        :return: SQL statements
        """
        stmts = []
        for sch in self:
            if sch != 'public' and hasattr(self[sch], 'dropped'):
                stmts.append(self[sch].drop())
        return stmts

    def data_import(self, opts):
        """Iterate over schemas with tables to be imported

        :param opts: options to include/exclude schemas/tables, etc.
        :return: list of SQL statements
        """
        return [self[sch].data_import(opts) for sch in self]
