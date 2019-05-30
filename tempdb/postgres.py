import getpass
import os
import platform
import psycopg2
import sys
import tempfile

from glob import glob
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT, quote_ident
from subprocess import check_output, PIPE, Popen
from time import sleep

from ._compat import ustr
from .utils import is_executable, Uri, Version


__all__ = [
    "PostgresFactory",
    "PostgresCluster",
]

class PostgresFactory(object):
    def __init__(self, pg_bin_dir, superuser=None):
        # Temporary value until the first time we request it
        self._version = None

        self.initdb = os.path.join(pg_bin_dir, "initdb")
        if not is_executable(self.initdb):
            raise ValueError(
                "Unable to find initdb command in {}".format(pg_bin_dir)
            )

        self.postgres = os.path.join(pg_bin_dir, "postgres")
        if not is_executable(self.postgres):
            raise ValueError(
                "Unable to find postgres command in {}".format(pg_bin_dir)
            )

        if superuser is None:
            superuser = getpass.getuser()
        self.superuser = superuser

    @property
    def version(self):
        if self._version is None:
            self._version = get_version(self.postgres)
        return self._version

    def init_cluster(self, data_dir=None):
        """
        Create a postgres cluster that trusts all incoming connections.

        This is great for testing, but a horrible idea for production usage.

        :param data_dir: Directory to create cluster in. This directory will
                         be automatically created if necessary.
        :return: Path to the created cluster that can be used by load_cluster()
        """
        if data_dir is None:
            data_dir = tempfile.mkdtemp()

        # If the target directory is not empty we don't want to risk wiping it
        if os.listdir(data_dir):
            raise ValueError((
                "The given data directory {} is not empty. A new cluster will "
                "not be created."
            ).format(data_dir))

        check_output([
            self.initdb,
            "-U", self.superuser,
            "-A", "trust",
            data_dir
        ])

        return data_dir

    def create_temporary_cluster(self):
        data_dir = self.init_cluster()

        # Since we know this database should never be loaded again we disable
        # safe guards Postgres has to prevent data corruption
        return self.load_cluster(
            data_dir,
            is_temporary=True,
            fsync=False,
            full_page_writes=False,
        )

    def load_cluster(self, data_dir, is_temporary=False, **params):
        uri = Uri(
            scheme="postgresql",
            user=self.superuser,
            host=data_dir,
            params=params,
        )
        return PostgresCluster(self.postgres, uri, is_temporary)


class PostgresCluster(object):
    def __init__(self, postgres_bin, uri, is_temporary=False):
        if uri.host is None or not uri.host.startswith("/"):
            msg = "{!r} doesn't point to a UNIX socket directory"
            raise ValueError(msg.format(uri))

        self.uri = uri
        self.is_temporary = is_temporary
        self.returncode = None

        cmd = [
            postgres_bin,
            "-D", uri.host,
            "-k", uri.host,
            "-c", "listen_addresses=",
        ]

        # Add additional configuration from kwargs
        for k, v in uri.params.items():
            if isinstance(v, bool):
                v = "on" if v else "off"
            cmd.extend(["-c", "{}={}".format(k, v)])

        # Start cluster
        self.process = Popen(
            cmd,
            stdout=PIPE,
            stderr=PIPE,
        )

        # Wait for a ".s.PGSQL.<id>" file to appear before continuing
        while not glob(os.path.join(uri.host, ".s.PGSQL.*")):
            sleep(0.1)

        # Superuser connection
        self.conn = psycopg2.connect(
            ustr(self.uri.replace(database="postgres"))
        )
        self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    def __del__(self):
        self.close()

    def iter_databases(self):
        with self.conn.cursor() as c:
            default_databases = {"postgres", "template0", "template1"}
            c.execute("SELECT datname FROM pg_database")
            for name, in c:
                if name not in default_databases:
                    yield name

    def create_database(self, name, template=None):
        if name in self.iter_databases():
            raise KeyError("The database {!r} already exists".format(name))

        with self.conn.cursor() as c:
            sql = "CREATE DATABASE {}".format(quote_ident(name, c))
            if template is not None:
                sql += " TEMPLATE {}".format(quote_ident(template, c))

            c.execute(sql)

        return PostgresDatabase(self, self.uri.replace(database=name))

    def get_database(self, name):
        if name not in self.iter_databases():
            raise KeyError("The database {!r} doesn't exist".format(name))
        return PostgresDatabase(self, self.uri.replace(database=name))

    def close(self):
        if self.process is None:
            return

        # Kill all connections but this control connection. This prevents
        # the server waiting for connections to close indefinately
        with self.conn.cursor() as c:
            c.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE pid != pg_backend_pid()
            """)

        self.conn.close()
        self.process.terminate()
        self.returncode = self.process.wait()

        # Remove temporary clusters when closing
        if self.is_temporary:
            for path, dirs, files in os.walk(self.uri.host, topdown=False):
                for f in files:
                    os.remove(os.path.join(path, f))
                for d in dirs:
                    os.rmdir(os.path.join(path, d))
            os.rmdir(self.uri.host)

        self.process = None


class PostgresDatabase(object):
    def __init__(self, cluster, uri):
        self.cluster = cluster
        self.uri = uri

    @property
    def dsn(self):
        return ustr(self.uri)
