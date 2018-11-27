import psycopg2
import pytest

from tempdb import find_postgres_bin_dir, PostgresFactory


@pytest.fixture(scope="session")
def pg_bin_dir():
    d = find_postgres_bin_dir()
    if d is None:
        pytest.skip("Unable to locate a PostgreSQL installation")
    return d


@pytest.fixture(scope="module")
def factory(pg_bin_dir):
    return PostgresFactory(pg_bin_dir)


@pytest.fixture
def temp_cluster(factory):
    c = factory.create_temporary_cluster()
    try:
        yield c
    finally:
        c.close()


@pytest.fixture
def conn(temp_cluster):
    return psycopg2.connect(temp_cluster.create_database("tmp").dsn)


def test_create_database(temp_cluster):
    assert list(temp_cluster.iter_databases()) == []
    db = temp_cluster.create_database("tmp")
    assert db.uri.database == "tmp"
    assert list(temp_cluster.iter_databases()) == ["tmp"]


def test_get_database(temp_cluster):
    with pytest.raises(KeyError):
        temp_cluster.get_database("tmp")
    db = temp_cluster.create_database("tmp")
    assert db.uri == temp_cluster.get_database("tmp").uri


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
