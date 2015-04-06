# -*- coding: utf-8 -*-
"""
    pyrseas.dbobject.foreign
    ~~~~~~~~~~~~~~~~~~~~~~~~

    This defines nine classes: DbObjectWithOptions derived from
    DbObject, ForeignDataWrapper, ForeignServer and UserMapping
    derived from DbObjectWithOptions, ForeignDataWrapperDict,
    ForeignServerDict and UserMappingDict derived from DbObjectDict,
    ForeignTable derived from DbObjectWithOptions and Table, and
    ForeignTableDict derived from ClassDict.
"""
from pyrseas.dbobject import DbObjectDict, DbObject
from pyrseas.dbobject import quote_id, commentable, ownable, grantable
from pyrseas.dbobject.table import ClassDict, Table
from pyrseas.dbobject.privileges import privileges_from_map


class DbObjectWithOptions(DbObject):
    """Helper class for database objects with OPTIONS clauses"""

    def options_clause(self):
        """Create the OPTIONS clause

        :param optdict: the dictionary of options
        :return: SQL OPTIONS clause
        """
        opts = []
        for opt in self.options:
            (nm, val) = opt.split('=', 1)
            opts.append("%s '%s'" % (nm, val))
        return "OPTIONS (%s)" % ', '.join(opts)

    def diff_options(self, newopts):
        """Compare options lists and generate SQL OPTIONS clause

        :newopts: list of new options
        :return: SQL OPTIONS clause

        Generate ([ADD|SET|DROP key 'value') clauses from two lists in the
        form of 'key=value' strings.
        """
        def to_dict(optlist):
            return dict(opt.split('=', 1) for opt in optlist)

        oldopts = {}
        if hasattr(self, 'options'):
            oldopts = to_dict(self.options)
        newopts = to_dict(newopts)
        clauses = []
        for key, val in list(newopts.items()):
            if key not in oldopts:
                clauses.append("%s '%s'" % (key, val))
            elif val != oldopts[key]:
                clauses.append("SET %s '%s'" % (key, val))
        for key, val in list(oldopts.items()):
            if key not in newopts:
                clauses.append("DROP %s" % key)
        return clauses and "OPTIONS (%s)" % ', '.join(clauses) or ''

    def diff_map(self, inobj):
        """Generate SQL to transform an existing object

        :param inobj: a YAML map defining the new object
        :return: list of SQL statements
        """
        stmts = super(DbObjectWithOptions, self).diff_map(inobj)
        newopts = []
        if hasattr(inobj, 'options'):
            newopts = inobj.options
        diff_opts = self.diff_options(newopts)
        if diff_opts:
            stmts.append("ALTER %s %s %s" % (
                self.objtype, self.identifier(), diff_opts))
        return stmts


class ForeignDataWrapper(DbObjectWithOptions):
    """A foreign data wrapper definition"""

    objtype = "FOREIGN DATA WRAPPER"
    single_extern_file = True

    @property
    def allprivs(self):
        return 'U'

    def to_map(self, no_owner, no_privs):
        """Convert wrappers and subsidiary objects to a YAML-suitable format

        :param no_owner: exclude object owner information
        :param no_privs: exclude privilege information
        :return: dictionary
        """
        wrapper = self._base_map(no_owner, no_privs)
        if hasattr(self, 'servers'):
            srvs = {}
            for srv in self.servers:
                srvs.update(self.servers[srv].to_map(no_owner, no_privs))
            wrapper.update(srvs)
            del wrapper['servers']
        return wrapper

    @commentable
    @grantable
    @ownable
    def create(self):
        """Return SQL statements to CREATE the data wrapper

        :return: SQL statements
        """
        clauses = []
        for fnc in ['validator', 'handler']:
            if hasattr(self, fnc):
                clauses.append("%s %s" % (fnc.upper(), getattr(self, fnc)))
        if hasattr(self, 'options'):
            clauses.append(self.options_clause())
        return ["CREATE FOREIGN DATA WRAPPER %s%s" % (
                quote_id(self.name),
                clauses and '\n    ' + ',\n    '.join(clauses) or '')]

    def diff_map(self, inwrapper):
        """Generate SQL to transform an existing wrapper

        :param inwrapper: a YAML map defining the new wrapper
        :return: list of SQL statements
        """
        stmts = super(ForeignDataWrapper, self).diff_map(inwrapper)
        if inwrapper.owner is not None:
            if inwrapper.owner != self.owner:
                stmts.append(self.alter_owner(inwrapper.owner))
        stmts.append(self.diff_description(inwrapper))
        return stmts


QUERY_PRE91 = \
    """SELECT fdwname AS name, CASE WHEN fdwvalidator = 0 THEN NULL
                ELSE fdwvalidator::regproc END AS validator,
                fdwoptions AS options, rolname AS owner,
              array_to_string(fdwacl, ',') AS privileges,
              obj_description(w.oid, 'pg_foreign_data_wrapper') AS
                  description
       FROM pg_foreign_data_wrapper w
            JOIN pg_roles r ON (r.oid = fdwowner)
       ORDER BY fdwname"""


class ForeignDataWrapperDict(DbObjectDict):
    "The collection of foreign data wrappers in a database"

    cls = ForeignDataWrapper
    query = \
        """SELECT fdwname AS name, CASE WHEN fdwhandler = 0 THEN NULL
                      ELSE fdwhandler::regproc END AS handler,
                  CASE WHEN fdwvalidator = 0 THEN NULL
                      ELSE fdwvalidator::regproc END AS validator,
                  fdwoptions AS options, rolname AS owner,
                  array_to_string(fdwacl, ',') AS privileges,
                  obj_description(w.oid, 'pg_foreign_data_wrapper') AS
                      description
           FROM pg_foreign_data_wrapper w
                JOIN pg_roles r ON (r.oid = fdwowner)
           ORDER BY fdwname"""

    def _from_catalog(self):
        """Initialize the dictionary of wrappers by querying the catalogs"""
        if self.dbconn.version < 90100:
            self.query = QUERY_PRE91
        super(ForeignDataWrapperDict, self)._from_catalog()

    def from_map(self, inwrappers, newdb):
        """Initialize the dictionary of wrappers by examining the input map

        :param inwrappers: input YAML map defining the data wrappers
        :param newdb: collection of dictionaries defining the database
        """
        for key in inwrappers:
            if not key.startswith('foreign data wrapper '):
                raise KeyError("Unrecognized object type: %s" % key)
            fdw = key[21:]
            self[fdw] = wrapper = ForeignDataWrapper(name=fdw)
            inwrapper = inwrappers[key]
            inservs = {}
            for key in inwrapper:
                if key.startswith('server '):
                    inservs.update({key: inwrapper[key]})
                elif key in ['handler', 'validator', 'options', 'owner',
                             'oldname', 'description']:
                    setattr(wrapper, key, inwrapper[key])
                elif key == 'privileges':
                    wrapper.privileges = privileges_from_map(
                        inwrapper[key], wrapper.allprivs, inwrapper['owner'])
                else:
                    raise KeyError("Expected typed object, found '%s'" % key)
            newdb.servers.from_map(wrapper, inservs, newdb)

    def link_refs(self, dbservers):
        """Connect servers to their respective foreign data wrappers

        :param dbservers: dictionary of foreign servers
        """
        for (fdw, srv) in dbservers:
            dbserver = dbservers[(fdw, srv)]
            assert self[fdw]
            wrapper = self[fdw]
            if not hasattr(wrapper, 'servers'):
                wrapper.servers = {}
            wrapper.servers.update({srv: dbserver})

    def diff_map(self, inwrappers):
        """Generate SQL to transform existing data wrappers

        :param input_map: a YAML map defining the new data wrappers
        :return: list of SQL statements

        Compares the existing data wrapper definitions, as fetched from the
        catalogs, to the input map and generates SQL statements to
        transform the data wrappers accordingly.
        """
        stmts = []
        # check input data wrappers
        for fdw in inwrappers:
            infdw = inwrappers[fdw]
            # does it exist in the database?
            if fdw in self:
                stmts.append(self[fdw].diff_map(infdw))
            else:
                # check for possible RENAME
                if hasattr(infdw, 'oldname'):
                    oldname = infdw.oldname
                    try:
                        stmts.append(self[oldname].rename(infdw.name))
                        del self[oldname]
                    except KeyError as exc:
                        exc.args = ("Previous name '%s' for data wrapper "
                                    "'%s' not found" % (oldname, infdw.name), )
                        raise
                else:
                    # create new data wrapper
                    stmts.append(infdw.create())
        # check database data wrappers
        for fdw in self:
            # if missing, drop it
            if fdw not in inwrappers:
                self[fdw].dropped = True
        return stmts

    def _drop(self):
        """Actually drop the wrappers

        :return: SQL statements
        """
        stmts = []
        for fdw in self:
            if hasattr(self[fdw], 'dropped'):
                stmts.append(self[fdw].drop())
        return stmts


class ForeignServer(DbObjectWithOptions):
    """A foreign server definition"""

    objtype = "SERVER"
    privobjtype = "FOREIGN SERVER"
    keylist = ['wrapper', 'name']

    @property
    def allprivs(self):
        return 'U'

    def identifier(self):
        """Returns a full identifier for the foreign server

        :return: string
        """
        return quote_id(self.name)

    def to_map(self, no_owner, no_privs):
        """Convert servers and subsidiary objects to a YAML-suitable format

        :param no_owner: exclude server owner information
        :param no_privs: exclude privilege information
        :return: dictionary
        """
        key = self.extern_key()
        server = {key: self._base_map(no_owner, no_privs)}
        if hasattr(self, 'usermaps'):
            umaps = {}
            for umap in self.usermaps:
                umaps.update({umap: self.usermaps[umap].to_map()})
            server[key]['user mappings'] = umaps
            del server[key]['usermaps']
        return server

    @commentable
    @grantable
    @ownable
    def create(self):
        """Return SQL statements to CREATE the server

        :return: SQL statements
        """
        clauses = []
        options = []
        for opt in ['type', 'version']:
            if hasattr(self, opt):
                clauses.append("%s '%s'" % (opt.upper(), getattr(self, opt)))
        if hasattr(self, 'options'):
            options.append(self.options_clause())
        return ["CREATE SERVER %s%s\n    FOREIGN DATA WRAPPER %s%s" % (
                quote_id(self.name),
                clauses and ' ' + ' '.join(clauses) or '',
                quote_id(self.wrapper),
                options and '\n    ' + ',\n    '.join(options) or '')]

    def diff_map(self, inserver):
        """Generate SQL to transform an existing server

        :param inserver: a YAML map defining the new server
        :return: list of SQL statements
        """
        stmts = super(ForeignServer, self).diff_map(inserver)
        if inserver.owner is not None:
            if inserver.owner != self.owner:
                stmts.append(self.alter_owner(inserver.owner))
        stmts.append(self.diff_description(inserver))
        return stmts


class ForeignServerDict(DbObjectDict):
    "The collection of foreign servers in a database"

    cls = ForeignServer
    query = \
        """SELECT fdwname AS wrapper, srvname AS name, srvtype AS type,
                  srvversion AS version, srvoptions AS options,
                  rolname AS owner, array_to_string(srvacl, ',') AS privileges,
                  obj_description(s.oid, 'pg_foreign_server') AS description
           FROM pg_foreign_server s
                JOIN pg_roles r ON (r.oid = srvowner)
                JOIN pg_foreign_data_wrapper w ON (srvfdw = w.oid)
           ORDER BY fdwname, srvname"""

    def from_map(self, wrapper, inservers, newdb):
        """Initialize the dictionary of servers by examining the input map

        :param wrapper: associated foreign data wrapper
        :param inservers: input YAML map defining the foreign servers
        :param newdb: collection of dictionaries defining the database
        """
        for key in inservers:
            if not key.startswith('server '):
                raise KeyError("Unrecognized object type: %s" % key)
            srv = key[7:]
            self[(wrapper.name, srv)] = serv = ForeignServer(
                wrapper=wrapper.name, name=srv)
            inserv = inservers[key]
            if inserv:
                for attr, val in list(inserv.items()):
                    setattr(serv, attr, val)
                if 'user mappings' in inserv:
                    newdb.usermaps.from_map(serv, inserv['user mappings'])
                if 'oldname' in inserv:
                    del inserv['oldname']
                if 'privileges' in inserv:
                    serv.privileges = privileges_from_map(
                        inserv['privileges'], serv.allprivs, serv.owner)

    def to_map(self, no_owner, no_privs):
        """Convert the server dictionary to a regular dictionary

        :param no_owner: exclude server owner information
        :param no_privs: exclude privilege information
        :return: dictionary

        Invokes the `to_map` method of each server to construct a
        dictionary of foreign servers.
        """
        servers = {}
        for srv in self:
            servers.update(self[srv].to_map(no_owner, no_privs))
        return servers

    def link_refs(self, dbusermaps):
        """Connect user mappings to their respective servers

        :param dbusermaps: dictionary of user mappings
        """
        for (fdw, srv, usr) in dbusermaps:
            dbusermap = dbusermaps[(fdw, srv, usr)]
            assert self[(fdw, srv)]
            server = self[(fdw, srv)]
            if not hasattr(server, 'usermaps'):
                server.usermaps = {}
            server.usermaps.update({usr: dbusermap})

    def diff_map(self, inservers):
        """Generate SQL to transform existing foreign servers

        :param inservers: a YAML map defining the new foreign servers
        :return: list of SQL statements

        Compares the existing server definitions, as fetched from the
        catalogs, to the input map and generates SQL statements to
        transform the foreign servers accordingly.
        """
        stmts = []
        # check input foreign servers
        for (fdw, srv) in inservers:
            insrv = inservers[(fdw, srv)]
            # does it exist in the database?
            if (fdw, srv) in self:
                stmts.append(self[(fdw, srv)].diff_map(insrv))
            else:
                # check for possible RENAME
                if hasattr(insrv, 'oldname'):
                    oldname = insrv.oldname
                    try:
                        stmts.append(self[(fdw, oldname)].rename(insrv.name))
                        del self[oldname]
                    except KeyError as exc:
                        exc.args = ("Previous name '%s' for dictionary '%s' "
                                    "not found" % (oldname, insrv.name), )
                        raise
                else:
                    # create new dictionary
                    stmts.append(insrv.create())
        # check database foreign servers
        for srv in self:
            # if missing, drop it
            if srv not in inservers:
                self[srv].dropped = True
        return stmts

    def _drop(self):
        """Actually drop the servers

        :return: SQL statements
        """
        stmts = []
        for srv in self:
            if hasattr(self[srv], 'dropped'):
                stmts.append(self[srv].drop())
        return stmts


class UserMapping(DbObjectWithOptions):
    """A user mapping definition"""

    objtype = "USER MAPPING"

    keylist = ['wrapper', 'server', 'name']

    def extern_key(self):
        """Return the key to be used in external maps for this user mapping

        :return: string
        """
        return self.name

    def identifier(self):
        """Return a full identifier for a user mapping object

        :return: string
        """
        return "FOR %s SERVER %s" % (
            self.name == 'PUBLIC' and 'PUBLIC' or quote_id(self.name),
            quote_id(self.server))

    def create(self):
        """Return SQL statements to CREATE the user mapping

        :return: SQL statements
        """
        options = []
        if hasattr(self, 'options'):
            options.append(self.options_clause())
        return ["CREATE USER MAPPING FOR %s\n    SERVER %s%s" % (
                self.name == 'PUBLIC' and 'PUBLIC' or
                quote_id(self.name), quote_id(self.server),
                options and '\n    ' + ',\n    '.join(options) or '')]


class UserMappingDict(DbObjectDict):
    "The collection of user mappings in a database"

    cls = UserMapping
    query = \
        """SELECT fdwname AS wrapper, s.srvname AS server,
                  CASE umuser WHEN 0 THEN 'PUBLIC' ELSE
                  usename END AS name, umoptions AS options
           FROM pg_user_mappings u
                JOIN pg_foreign_server s ON (u.srvid = s.oid)
                JOIN pg_foreign_data_wrapper w ON (srvfdw = w.oid)
           ORDER BY fdwname, s.srvname, 3"""

    def from_map(self, server, inusermaps):
        """Initialize the dictionary of mappings by examining the input map

        :param server: foreign server associated with mappings
        :param inusermaps: input YAML map defining the user mappings
        """
        for key in inusermaps:
            usermap = UserMapping(wrapper=server.wrapper, server=server.name,
                                  name=key)
            inusermap = inusermaps[key]
            if inusermap:
                for attr, val in list(inusermap.items()):
                    setattr(usermap, attr, val)
                if 'oldname' in inusermap:
                    del inusermap['oldname']
            self[(server.wrapper, server.name, key)] = usermap

    def to_map(self):
        """Convert the user mapping dictionary to a regular dictionary

        :return: dictionary

        Invokes the `to_map` method of each mapping to construct a
        dictionary of user mappings.
        """
        usermaps = {}
        for um in self:
            usermaps.update(self[um].to_map())
        return usermaps

    def diff_map(self, inusermaps):
        """Generate SQL to transform existing user mappings

        :param input_map: a YAML map defining the new user mappings
        :return: list of SQL statements

        Compares the existing user mapping definitions, as fetched from the
        catalogs, to the input map and generates SQL statements to
        transform the user mappings accordingly.
        """
        stmts = []
        # check input user mappings
        for (fdw, srv, usr) in inusermaps:
            inump = inusermaps[(fdw, srv, usr)]
            # does it exist in the database?
            if (fdw, srv, usr) in self:
                stmts.append(self[(fdw, srv, usr)].diff_map(inump))
            else:
                # check for possible RENAME
                if hasattr(inump, 'oldname'):
                    oldname = inump.oldname
                    try:
                        stmts.append(self[(fdw, srv, oldname)].rename(
                            inump.name))
                        del self[(fdw, srv, oldname)]
                    except KeyError as exc:
                        exc.args = ("Previous name '%s' for user mapping '%s' "
                                    "not found" % (oldname, inump.name), )
                        raise
                else:
                    # create new user mapping
                    stmts.append(inump.create())
        # check database user mappings
        for (fdw, srv, usr) in self:
            # if missing, drop it
            if (fdw, srv, usr) not in inusermaps:
                stmts.append(self[(fdw, srv, usr)].drop())
        return stmts


class ForeignTable(DbObjectWithOptions, Table):
    """A foreign table definition"""

    objtype = "FOREIGN TABLE"
    privobjtype = "TABLE"

    def to_map(self, opts):
        """Convert a foreign table to a YAML-suitable format

        :param opts: options to include/exclude tables, etc.
        :return: dictionary
        """
        if hasattr(opts, 'excl_tables') and opts.excl_tables \
                and self.name in opts.excl_tables:
            return {}
        if not hasattr(self, 'columns'):
            return {}
        cols = []
        for i in range(len(self.columns)):
            col = self.columns[i].to_map(opts.no_privs)
            if col:
                cols.append(col)
        tbl = {'columns': cols, 'server': self.server}
        attrlist = ['options']
        if self.description is not None:
            attrlist.append('description')
        if not opts.no_owner:
            attrlist.append('owner')
        for attr in attrlist:
            if hasattr(self, attr):
                tbl.update({attr: getattr(self, attr)})
        if not opts.no_privs and self.privileges:
            tbl.update({'privileges': self.map_privs()})

        return tbl

    @grantable
    def create(self):
        """Return SQL statements to CREATE the foreign table

        :return: SQL statements
        """
        stmts = []
        cols = []
        options = []
        for col in self.columns:
            cols.append("    " + col.add()[0])
        if hasattr(self, 'options'):
            options.append(self.options_clause())
        stmts.append("CREATE FOREIGN TABLE %s (\n%s)\n    SERVER %s%s" % (
            self.qualname(), ",\n".join(cols), self.server,
            options and '\n    ' + ',\n    '.join(options) or ''))
        if self.owner is not None:
            stmts.append(self.alter_owner())
        if self.description is not None:
            stmts.append(self.comment())
        for col in self.columns:
            if col.description is not None:
                stmts.append(col.comment())
        return stmts

    def drop(self):
        """Return a SQL DROP statement for the foreign table

        :return: SQL statement
        """
        return "DROP %s %s" % (self.objtype, self.identifier())

    def diff_map(self, intable):
        """Generate SQL to transform an existing table

        :param intable: a YAML map defining the new table
        :return: list of SQL statements
        """
        stmts = super(ForeignTable, self).diff_map(intable)
        if intable.owner is not None:
            if intable.owner != self.owner:
                stmts.append(self.alter_owner(intable.owner))
        stmts.append(self.diff_description(intable))
        return stmts


class ForeignTableDict(ClassDict):
    "The collection of foreign tables in a database"

    cls = ForeignTable
    query = \
        """SELECT nspname AS schema, relname AS name, srvname AS server,
                  ftoptions AS options, rolname AS owner,
                  array_to_string(relacl, ',') AS privileges,
                  obj_description(c.oid, 'pg_class') AS description
           FROM pg_class c JOIN pg_foreign_table f ON (ftrelid = c.oid)
                JOIN pg_roles r ON (r.oid = relowner)
                JOIN pg_foreign_server s ON (ftserver = s.oid)
                JOIN pg_namespace ON (relnamespace = pg_namespace.oid)
           WHERE relkind = 'f'
                 AND (nspname != 'pg_catalog'
                      AND nspname != 'information_schema')
           ORDER BY nspname, relname"""

    def _from_catalog(self):
        """Initialize the dictionary of tables by querying the catalogs"""
        if self.dbconn.version < 90100:
            return
        for tbl in self.fetch():
            self[tbl.key()] = tbl

    def from_map(self, schema, inobjs, newdb):
        """Initalize the dictionary of tables by converting the input map

        :param schema: schema owning the tables
        :param inobjs: YAML map defining the schema objects
        :param newdb: collection of dictionaries defining the database
        """
        for key in inobjs:
            if not key.startswith('foreign table '):
                raise KeyError("Unrecognized object type: %s" % key)
            ftb = key[14:]
            self[(schema.name, ftb)] = ftable = ForeignTable(
                schema=schema.name, name=ftb)
            inftable = inobjs[key]
            if not inftable:
                raise ValueError("Foreign table '%s' has no specification" %
                                 ftb)
            try:
                newdb.columns.from_map(ftable, inftable['columns'])
            except KeyError as exc:
                exc.args = ("Foreign table '%s' has no columns" % ftb, )
                raise
            for attr in ['server', 'options', 'owner', 'description']:
                if attr in inftable:
                    setattr(ftable, attr, inftable[attr])
            if 'privileges' in inftable:
                ftable.privileges = privileges_from_map(
                    inftable['privileges'], ftable.allprivs, ftable.owner)

    def link_refs(self, dbcolumns):
        """Connect columns to their respective foreign tables

        :param dbcolumns: dictionary of columns
        """
        for (sch, tbl) in dbcolumns:
            if (sch, tbl) in self:
                assert isinstance(self[(sch, tbl)], ForeignTable)
                self[(sch, tbl)].columns = dbcolumns[(sch, tbl)]
                for col in dbcolumns[(sch, tbl)]:
                    col._table = self[(sch, tbl)]

    def diff_map(self, intables):
        """Generate SQL to transform existing foreign tables

        :param intables: a YAML map defining the new foreign tables
        :return: list of SQL statements

        Compares the existing foreign table definitions, as fetched
        from the catalogs, to the input map and generates SQL
        statements to transform the foreign tables accordingly.
        """
        stmts = []
        # check input tables
        for (sch, tbl) in intables:
            intbl = intables[(sch, tbl)]
            # does it exist in the database?
            if (sch, tbl) not in self:
                # check for possible RENAME
                if hasattr(intbl, 'oldname'):
                    oldname = intbl.oldname
                    try:
                        stmts.append(self[(sch, oldname)].rename(intbl.name))
                        del self[(sch, oldname)]
                    except KeyError as exc:
                        exc.args = ("Previous name '%s' for foreign table "
                                    "'%s' not found" % (oldname, intbl.name), )
                        raise
                else:
                    # create new table
                    stmts.append(intbl.create())

        # check database tables
        for (sch, tbl) in self:
            table = self[(sch, tbl)]
            # if missing, drop it
            if (sch, tbl) not in intables:
                stmts.append(table.drop())
            else:
                # compare table objects
                stmts.append(table.diff_map(intables[(sch, tbl)]))

        return stmts
