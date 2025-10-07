import re


def compare_postgresql_dumps(dump1, dump2):
    """
    Compare two postgresql dumps.

    :param dump1: path to postgresql dump to compare.
    :param dump2: path to postgresql dump to compare.
    """

    def read_sql_dump(dump):
        # read the expected non-empty non-comment lines
        lines = []
        with open(dump, "r") as dump_file:
            for line in dump_file.readlines():
                if not line.startswith("--") and not re.match(r"^\s*$", line):
                    lines.append(line)
        return lines

    dump1 = read_sql_dump(dump1)
    dump2 = read_sql_dump(dump2)

    assert len(dump1) == len(dump2)

    for d1, d2 in zip(dump1, dump2):
        assert d1 == d2


def compare_databases(expected_cur, test_cur):
    """
    Compare all tables of expected database with the expected database.

    :param expected_cur: cursor for the database with the expected data
    :param test_cur: cursor for the database to be tested
    """
    expected_cur.execute(
        "SELECT name FROM sqlite_master WHERE type ='table' AND name NOT LIKE 'sqlite_%';"
    )
    tables = expected_cur.fetchall()

    if len(tables) == 0:
        test_cur.execute(
            "SELECT name FROM sqlite_master WHERE type ='table' AND name NOT LIKE 'sqlite_%';"
        )
        test_tables = test_cur.fetchall()
        assert len(test_tables) == 0

    for table in tables:
        table = table[0]
        expected_cur.execute("SELECT * FROM {};".format(table))
        expected_result = expected_cur.fetchall()

        test_cur.execute("SELECT * FROM {};".format(table))
        result = test_cur.fetchall()

        assert expected_result == result
