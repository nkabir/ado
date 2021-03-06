import ado.commands

def list_command(**kwargs):
    """
    List all non-archived elements of a given type.
    """
    if not kwargs:
        # print help
        print "Valid flags are:"
        print "  -all\t(for all objects)"
        for k, v in ado.commands.classes.iteritems():
            print "  -%s\t(for %s)" % (k, v.__name__)
    else:
        # print all the things
        c = ado.commands.conn()
        if "all" in kwargs:
            classes = ado.commands.classes.values()
            for klass in classes:
                [klass.printall(c) for k, v in kwargs.iteritems() if v]
        else:
            [ado.commands.abbrev(k).printall(c) for k, v in kwargs.iteritems() if v]

def search_command(query=None):
    """
    Lists all items which match the query.
    """
    c = ado.commands.conn()

    for klass in ado.commands.classes.values():
        objects = klass.search(c, query)
        for obj in objects:
            print obj.display_line()
