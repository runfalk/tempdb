import pytest

from tempdb._compat import ustr
from tempdb.utils import Uri


some_uris = pytest.mark.parametrize("uri", [
    "postgresql://",
    "postgresql:///db",
    "postgresql://localhost/db",
    "postgresql://user@host:9001/db",
    "postgresql://user:password@host:9001/db?param1=123&param2=321",
    "postgresql://%2Fvar%2Flib%2Fpostgresql/dbname",
])


@some_uris
def test_symmetry(uri):
    assert ustr(Uri.parse(uri)) == uri


@some_uris
def test_repr(uri):
    obj = Uri.parse(uri)
    if obj.password is None:
        assert uri in repr(obj)
    else:
        assert obj.password not in repr(obj)


def test_url_encoding():
    uri = Uri.parse("s://u:p@h:1/d?k=v")
    assert uri.scheme == "s"
    assert uri.user == "u"
    assert uri.password == "p"
    assert uri.host == "h"
    assert uri.port == 1
    assert uri.database == "d"
    assert "k" in uri.params
    assert uri.params["k"] == "v"


def test_equality():
    assert Uri.parse("s://localhost") == Uri("s", host="localhost")


def test_inequality():
    assert Uri.parse("a://localhost") != Uri("b", host="localhost")
