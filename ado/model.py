import datetime
import sqlite3

class Model(object):
    FIELDS = {}
    SEARCH_FIELDS = None

    @classmethod
    def printall(klass, conn, by=None):
        for obj in klass.all(conn, by):
            print obj.display_line()

    @classmethod
    def all_due(klass, conn):
        all_due = []
        for obj in klass.all(conn):
            if hasattr(obj, 'is_due'):
                if obj.is_due():
                    all_due.append(obj)
        return all_due

    @classmethod
    def all(klass, conn, by=None):
        if not by:
            order_by = ""
        elif by == 'id':
            order_by = ""
        else:
            if not by in klass.FIELDS.keys():
                raise Exception("No field found for %s" % by)
            order_by = " ORDER BY %s" % by

        if "archived_at" in klass.FIELDS:
            sql = "SELECT * from %s WHERE archived_at is null%s" % (klass.table_name(), order_by)
        else:
            sql = "SELECT * from %s%s" % (klass.table_name(), order_by)
        return [klass.load(conn, row) for row in conn.execute(sql)]

    @classmethod
    def search(klass, conn, search, by=None):
        """
        Return all items which meet the search criteria.
        """
        if not by:
            order_by = ""
        elif by == 'id':
            order_by = ""
        else:
            if not by in klass.FIELDS.keys():
                raise Exception("No field found for %s" % by)
            order_by = " ORDER BY %s" % by

        if klass.SEARCH_FIELDS:
            search_fields = " OR ".join("%s like ?" % f for f in klass.SEARCH_FIELDS)
            sql = "SELECT * from %s WHERE (%s) and archived_at is null%s"
            sqlargs = (klass.table_name(), search_fields, order_by)
            rows = conn.execute(sql%sqlargs, ["%%%s%%" % search]*len(klass.SEARCH_FIELDS))
            return [klass.load(conn, row) for row in rows]
        else:
            return []

    @classmethod
    def get(klass, conn, rowid):
        """
        Retrieve the element with specified rowid.
        """
        sql = "select * from %s where id = ?" % klass.table_name()
        row = conn.execute(sql, [rowid]).fetchone()
        if not row:
            raise Exception("No %s found with id %s" % (klass.__name__, rowid))
        return klass.load(conn, row)

    @classmethod
    def update(klass, conn, rowid, kwargs):
        sql = "UPDATE %(table)s SET %(fields_and_qs)s WHERE id = ?"
        args = {
            'fields_and_qs' : ",".join("%s=?" % k for k in sorted(kwargs)),
            'table' : klass.table_name()
        }
        values = [kwargs[k] for k in sorted(kwargs)] + [rowid]
        conn.execute(sql % args, values)
        conn.commit()

    @classmethod
    def keys(klass):
        return sorted(klass.FIELDS)

    def is_due(self, conn=None):
        if not conn:
            conn = self.conn

        if self.frequency == 'None':
            # No frequency specified, so it cannot be due.
            return False

        latest = self.latest()

        if latest:
            if hasattr(latest, 'created_at'):
                return (datetime.datetime.now() - latest.created_at) > self.frequency_delta()
            elif hasattr(latest, 'started_at'):
                return (datetime.datetime.now() - latest.started_at) > self.frequency_delta()
            else:
                raise Exception("Don't know how to calculate is_due for '%s'" % latest.__class__)
        else:
            return True

    def frequency_delta(self):
        """
        Returns a timedelta object for the specified frequency.
        """
        if "m" in self.frequency:
            minutes = int(self.frequency.replace("m", ""))
            return datetime.timedelta(minutes=minutes)
        elif "h" in self.frequency:
            hours = int(self.frequency.replace("h", ""))
            return datetime.timedelta(hours=hours)
        elif "w" in self.frequency:
            weeks = int(self.frequency.replace("w", ""))
            return datetime.timedelta(weeks=weeks)
        elif "d" in self.frequency:
            days = int(self.frequency.replace("d", ""))
            return datetime.timedelta(days=days)
        else:
            try:
                days = int(self.frequency)
                return datetime.timedelta(days=days)
            except ValueError:
                raise Exception("Invalid frequency '%s'" % self.frequency)

    def display_line(self):
        if hasattr(self, 'name'):
            return "%s %4d) %s" % (self.__class__.__name__, self.id, self.name)
        else:
            return "%s %4d" % (self.__class__.__name__, self.id)

    def validate(self):
        return True

    def reload(self, conn):
        return self.get(conn, self.id)

    def persist(self, conn):
        sql, values = self.persist_instance_sql()
        return conn.execute(sql, values)

    def persist_instance_sql(self):
        sql = "INSERT INTO %(table)s (%(fields)s) VALUES (%(qs)s)"
        values = [getattr(self, k, None) for k in self.keys()]

        args = {
            'table' : self.table_name(),
            'fields' : ",".join(self.keys()),
            'qs' : ("?," * len(self.keys()))[:-1]
        }
        return sql % args, values

    @classmethod
    def insert_instance_sql(klass):
        """Returns SQL for an insert statement."""
        keys = ['id'] + klass.keys()
        keys_list = ",".join(keys)
        quote_values_list = ",".join("'||quote(" + k + ")||'" for k in keys)
        args = {
            "table_name" : klass.table_name(),
            "fields" : keys_list,
            "quote_values" : quote_values_list
        }
        sql = "SELECT 'INSERT INTO %(table_name)s (%(fields)s) VALUES (%(quote_values)s);' from %(table_name)s" % args
        return sql

    @classmethod
    def create(klass, conn, **kwargs):
        """
        Create a new instance of this model class and persist it to the db.
        """
        o = klass()
        for key, value in kwargs.iteritems():
            setattr(o, key, value)
        cursor = o.persist(conn)
        o.id = cursor.lastrowid
        conn.commit()
        o.conn = conn
        return o

    @classmethod
    def load(klass, conn, row):
        """
        Create a new instance of this model class and populate it based on db values.
        """
        o = klass()
        for key in row.keys():
            setattr(o, key, row[key])
        o.conn = conn
        return o

    @classmethod
    def setup_db(self, filename=None):
        if not filename:
            filename = ":memory:"
        conn = sqlite3.connect(filename, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def setup_tables(self, c, klasses):
        for klass in klasses:
            klass.create_table(c)
        c.commit()

    @classmethod
    def table_name(klass):
        return klass.__name__

    @classmethod
    def create_table_sql(klass):
        sql = "CREATE TABLE %s (id INTEGER PRIMARY KEY AUTOINCREMENT, %s)"
        fields = ["%s %s" % (k, v) for k, v in klass.FIELDS.items()]
        return sql % (klass.table_name(), ", ".join(fields))

    @classmethod
    def create_table(self, conn):
        try:
            conn.execute(self.create_table_sql())
        except sqlite3.OperationalError:
            pass

    def elapsed(self):
        """
        For classes with a created_at attribute, returns the time elapsed since creation.
        """
        return datetime.datetime.now() - self.created_at

    def elapsed_seconds(self):
        return self.elapsed().total_seconds()

    def elapsed_minutes(self):
        return int(self.elapsed_seconds() / 60)

    def elapsed_hours(self):
        return int(self.elapsed_seconds() / 3600)

    def elapsed_days(self):
        return self.elapsed().days

    def elapsed_time(self):
        elapsed = self.elapsed()
        hours = int(elapsed.seconds/3600)
        minutes = int((elapsed.seconds - hours*3600)/60)
        return "%s:%s:%s" % (elapsed.days, hours, minutes)

    @classmethod
    def delete(klass, conn, rowid):
        sql = "delete from %s where id=?" % klass.table_name()
        conn.execute(sql, [int(rowid)])
        conn.commit()

    @classmethod
    def archive(klass, conn, rowid):
        """
        Archive this item so it no longer shows up in search results.
        """
        now = datetime.datetime.now()
        klass.update(conn, rowid, { 'archived_at' : now })

    def validate_complete(self, conn):
        return True

    def complete(self, conn):
        if not self.validate_complete(conn):
            raise Exception("This item can't be marked as completed.")
        now = datetime.datetime.now()
        self.update(conn, self.id, { 'completed_at' : now })
        # Also archive this.
        self.archive(conn, self.id)

    def days_until_due(self):
        return round((self.due_at - datetime.datetime.now()).total_seconds() / (60*60*24))
