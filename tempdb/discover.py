import os
import platform

from collections import defaultdict
from glob import glob
from subprocess import check_output

from ._compat import bstr, ustr
from .utils import get_version, Version


__all__ = [
    "find_postgres_bin_dir",
    "iter_postgres_bin_dirs",
]


def find_postgres_bin_dir(version=None):
    """
    Try to locate the postges base directory using some heuristics.

    :param version: Version string, number or Version object to
                         prioritize. If that version can't be found
    :return: Path to bin dir if successful, otherwise None
    """
    if isinstance(version, (bstr, ustr)):
        version = Version.from_str(version)
    elif isinstance(version, int):
        version = Version(version)

    dirs_by_version = defaultdict(list)
    for d, v in iter_postgres_bin_dirs():
        dirs_by_version[v].append(d)

    if not dirs_by_version:
        raise RuntimeError("Unable to find any postgres installation")

    ordered_dirs = sorted(dirs_by_version.items(), reverse=True)

    # If there is no requested version we just pick the latest
    if version is None:
        return ordered_dirs[0][1][0]

    for v, d in ordered_dirs:
        if version.major != v.major:
            continue

        if version.minor is not None and version.minor != v.minor:
            continue

        if version.micro is not None and version.micro != v.micro:
            continue

        return d[0]


def iter_postgres_bin_dirs():
    """
    Use heuristics to locate as many PostgreSQL installations as possible on
    this system.

    :return: An iterator that yield ``(version, path)`` pairs.
    """
    system = platform.system()
    dirs = []
    if system == "Linux":
        # Debian
        dirs.append("/usr/lib/postgresql/*/bin")

        # CentOS/RHEL/Fedora
        dirs.append("/usr/pgsql-*/bin")
    elif system == "Darwin":
        # Homebrew
        try:
            cellar = check_output(["brew", "--cellar"]).strip().decode("utf8")
            dirs.append(os.path.join(cellar, "postgresql/*/bin"))
        except OSError:
            pass

        # MacPorts
        dirs.append("/opt/local/lib/postgresql*/bin")

        # Postgres.app in $HOME/Applications
        dirs.append(os.path.expanduser(
            "~/Applications/Postgres.app/Contents/Versions/*/bin"
        ))

        # Postgres.app in /Applications
        dirs.append("/Applications/Postgres.app/Contents/Versions/*/bin")
    else:
        raise RuntimeError("Unsupported system {!r}".format(system))

    # Official installation path
    dirs.append("/usr/local/pgsql/bin")

    # Other plausible paths
    dirs.append("/usr/local/pgsql/bin")
    dirs.append("/usr/local/bin")
    dirs.append("/usr/bin")

    # Files required to be in the directory for us to consider it as a valid
    # Postgresql bin directory
    required_bins = {"initdb", "postgres"}

    # Go through each directory and return the first matching one
    for pattern in dirs:
        for d in glob(pattern):
            if not os.path.isdir(d):
                continue
            if set(os.listdir(d)).issuperset(required_bins):
                yield d, get_version(os.path.join(d, "postgres"))

