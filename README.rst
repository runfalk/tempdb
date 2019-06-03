TempDB
======
Spawn temporary PostgreSQL clusters for use in unit tests. This is alpha quality
software and the API may change between version.


Usage
-----
The following example shows how to create a temporary database with ``pytest``.

.. code-block:: python

    import psycopg2
    import pytest

    from contextlib import closing
    from tempdb import find_postgres_bin_dir, PostgresFactory


    @pytest.fixture
    def conn():
        # Try to discover a directory where PostgreSQL is installed. If you
        # have installed it in a non-standard location you must replace
        # pg_bin_dir with the path to the binary directory for your
        # installation.
        #
        # It is possible to provide a specific version as an argument if there
        # are multiple versions to choose from. The highest available version
        # is chosen by default.
        pg_bin_dir = find_postgres_bin_dir()
        if pg_bin_dir is None:
            pytest.skip("Unable to locate a PostgreSQL installation")

        # The factory is bound to a particular PostgreSQL version and can be
        # used to create an arbitrary number of clusters
        factory = PostgresFactory(pg_bin_dir)

        # A cluster is an actual running instance of PostgreSQL. By default a
        # cluster doesn't have any databases apart from the defaults. It is
        # possible to create new databases using the method
        # .create_database(name, template=None)
        with closing(factory.create_temporary_cluster()) as cluster:
            tmp_db = cluster.create_database("tmp")
            yield psycopg2.connect(tmp_db.dsn)


    def test_create_tables(conn):
        with conn.cursor() as c:
            c.execute("""
                CREATE TABLE test(
                    id SERIAL,
                    name VARCHAR
                )
            """)
            c.execute("INSERT INTO test(name) VALUES (%s), (%s)", [
                "Abel",
                "Cain",
            ])
            c.execute("SELECT name FROM test ORDER BY id")

            assert [name for name, in c.fetchall()] == [
                "Abel",
                "Cain",
            ]


Changelog
---------

Version 0.1.0
~~~~~~~~~~~~~
Released on 3rd June, 2019

- Initial release
