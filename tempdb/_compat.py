__all__ = [
    "bstr",
    "is_python2",
    "url_parse_qsl",
    "url_quote",
    "url_unquote",
    "ustr",
]

is_python2 = False

bstr = bytes
try:
    ustr = unicode
    is_python2 = True
except NameError:
    ustr = str

try:
    from urllib.parse import (
        quote as _url_quote,
        parse_qsl as url_parse_qsl,
        unquote as url_unquote,
    )
except ImportError:
    from urlparse import parse_qsl as url_parse_qsl
    from urllib import (
        quote as _url_quote,
        unquote as url_unquote,
    )

def url_quote(s, safe=""):
    return _url_quote(s.encode("utf8"), safe=safe)
