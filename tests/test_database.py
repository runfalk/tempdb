import pytest

from tempdb import find_postgres_bin_dir, PostgresFactory


@pytest.fixture
def pg_bin_dir():
    d = find_postgres_bin_dir()
    if d is None:
        pytest.skip("Unable to locate a PostgreSQL installation")
    return d


@pytest.fixture
def factory(pg_bin_dir):
    return PostgresFactory(pg_bin_dir)


@pytest.fixture
def temp_cluster(factory):
    c = factory.create_temporary_cluster()
    try:
        yield c
    finally:
        c.close()


def test_temporary(temp_cluster):
    assert list(temp_cluster.iter_databases()) == []
