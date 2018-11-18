import pytest

from tempdb.utils import Version


@pytest.mark.parametrize("args", [
    (),
    (None,),
    (1, "2"),
    (1, 2, "3"),
])
def test_invalid_type(args):
    with pytest.raises(TypeError):
        Version(*args)


def test_invalid_order():
    with pytest.raises(ValueError):
        Version(1, None, 3)
