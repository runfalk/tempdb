from tempdb import find_postgres_bin_dir


def test_find_non_existant_version():
    # Nobody will have version 1 installed, right?
    assert find_postgres_bin_dir("1") is None
