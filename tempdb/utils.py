import os
import re

from collections import OrderedDict
from subprocess import check_output

from ._compat import (
    bstr,
    is_python2,
    ustr,
    url_quote,
    url_parse_qsl,
    url_unquote,
)


__all__ = [
    "get_version",
    "is_executable",
    "Version",
]


def get_version(postgres_path):
    version = check_output([postgres_path, "--version"]).decode("utf-8")
    try:
        return next(Version.iter_str(version))
    except StopIteration:
        raise RuntimeError(
            "Unable to extract version from postgres --version"
        )

def int_or_none(thing):
    try:
        return int(thing)
    except TypeError:
        return None


def is_executable(path):
    """Return True if the given path is executable"""
    return os.access(path, os.X_OK)


class Version(tuple):
    __slots__ = ()

    _version_re = re.compile(r"(\d+)(?:\.(\d+)(?:\.(\d+))?)?")

    def __new__(cls, major, minor=None, micro=None):
        if not isinstance(major, int):
            raise TypeError("Major version must be int")
        if not isinstance(minor, int) and minor is not None:
            raise TypeError("Minor version must be int or None")
        if not isinstance(micro, int) and micro is not None:
            raise TypeError("Micro version must be int or None")

        if micro is not None and minor is None:
            raise ValueError(
                "Micro version must not be set if minor version is None"
            )

        return super(Version, cls).__new__(cls, (major, minor, micro))

    @classmethod
    def _from_match(cls, m):
        return cls(
            major=int_or_none(m.group(1)),
            minor=int_or_none(m.group(2)),
            micro=int_or_none(m.group(3)),
        )

    @classmethod
    def from_str(cls, s):
        if isinstance(s, bstr):
            s = s.decode("utf8")
        m = cls._version_re.match(s)
        if m is None:
            raise ValueError("{!r} is not a valid version string".format(s))
        return cls._from_match(m)

    @classmethod
    def iter_str(cls, s):
        for m in cls._version_re.finditer(s):
            yield cls._from_match(m)

    @property
    def major(self):
        return self[0]

    @property
    def minor(self):
        return self[1]

    @property
    def micro(self):
        return self[2]

    def iter_variants(self):
        if self.minor is not None:
            yield self
        if self.minor is not None:
            yield Version(self[0], self[1])
        yield Version(self[0])

    def __repr__(self):
        return "Version(major={}, minor={}, micro={})".format(*self)

    def __str__(self):
        parts = [ustr(self.major)]
        if self.minor is not None:
            parts.append(ustr(self.minor))
            if self.micro is not None:
                parts.append(ustr(self.micro))
        return u".".join(parts)

    __unicode__ = __str__


class Uri(object):
    __slots__ = (
        "scheme",
        "user",
        "password",
        "host",
        "port",
        "database",
        "is_ipv6",
        "params",
    )

    _uri_re = re.compile(r"""
        (?P<scheme>[\w\+]+)://
        (?:
            (?P<user>[^:/]*)
            (?::(?P<password>.*))?
        @)?
        (?:
            (?:
                \[(?P<ipv6host>[^/]+)\] |
                (?P<ipv4host>[^/:]+)
            )?
            (?::(?P<port>\d+))?
        )?
        (?:/(?P<database>[^?]+))?
        (?:\?(?P<query_string>.*))?
    """, re.X)

    def __init__(
        self,
        scheme,
        user=None,
        password=None,
        host=None,
        port=None,
        database=None,
        is_ipv6=False,
        params=None,
        **kwargs
    ):
        self.scheme = scheme
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.database = database
        self.is_ipv6 = is_ipv6

        if params is None:
            params = OrderedDict()
        self.params = params
        self.params.update(**kwargs)

    @classmethod
    def parse(cls, s):
        m = cls._uri_re.match(s)
        if m is None:
            raise ValueError("Invalid URI format")

        components = m.groupdict()

        scheme = None
        if components["scheme"] is not None:
            scheme = url_unquote(components["scheme"])

        user = None
        if components["user"] is not None:
            user = url_unquote(components["user"])

        password = None
        if components["password"] is not None:
            password = url_unquote(components["password"])

        is_ipv6 = False
        host = None
        if components["ipv6host"] is not None:
            is_ipv6 = True
            host = url_unquote(components["ipv6host"])
        elif components["ipv4host"] is not None:
            host = url_unquote(components["ipv4host"])

        port = None
        if components["port"] is not None:
            port = int(components["port"])

        # TODO: Use parts?
        database = None
        if components["database"] is not None:
            database = url_unquote(components["database"])

        params = OrderedDict()
        if components["query_string"] is not None:
            for k, v in url_parse_qsl(components["query_string"]):
                params[url_unquote(k)] = url_unquote(v)

        # TODO: Consider fragment support

        return cls(
            scheme,
            user=user,
            password=password,
            host=host,
            port=port,
            database=database,
            params=params,
            is_ipv6=is_ipv6,
        )

    def __repr__(self):
        uri = self
        if self.password is not None:
            uri = self.replace(password="***")
        return u"<Uri {!r}>".format(ustr(uri))

    def __eq__(self, other):
        if not isinstance(other, Uri):
            return NotImplemented
        return (
            self.scheme == other.scheme
            and self.user == other.user
            and self.password == other.password
            and self.host == other.host
            and self.port == other.port
            and self.database == other.database
            and self.params == other.params
            and self.is_ipv6 == other.is_ipv6
        )

    def __ne__(self, other):
        if not isinstance(other, Uri):
            return NotImplemented
        return not (self == other)

    def __unicode__(self):
        parts = [self.scheme, u"://"]
        if self.user is not None:
            parts.append(url_quote(self.user))

        if self.password is not None:
            parts.append(u":{}".format(url_quote(self.password)))

        if len(parts) != 2:
            parts.append(u"@")

        if self.host is not None and self.is_ipv6:
            parts.append(u"[")

        if self.host is not None:
            parts.append(url_quote(self.host, safe=":" if self.is_ipv6 else ""))

        if self.host is not None and self.is_ipv6:
            parts.append(u"]")

        if self.port is not None:
            parts.append(u":{}".format(self.port))

        if self.database is not None:
            parts.append(u"/{}".format(url_quote(self.database)))

        if self.params:
            parts.append(u"?")
            parts.append(u"&".join(
                u"{}={}".format(url_quote(k), url_quote(v))
                for k, v in self.params.items()
            ))

        return u"".join(parts)

    def replace(self, **kwargs):
        return Uri(
            scheme=kwargs.get("scheme", self.scheme),
            user=kwargs.get("user", self.user),
            password=kwargs.get("password", self.password),
            host=kwargs.get("host", self.host),
            port=kwargs.get("port", self.port),
            database=kwargs.get("database", self.database),
            is_ipv6=kwargs.get("is_ipv6", self.is_ipv6),
        )

    if not is_python2:
        __str__ = __unicode__
        del __unicode__
