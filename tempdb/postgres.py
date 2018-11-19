import getpass
import os
import platform
import psycopg2
import sys
import tempfile

from glob import glob
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
            stdout=sys.stdout,
            stderr=sys.stdout,
        )

        # Wait for a ".s.PGSQL.<id>" file to appear before continuing
        while not glob(os.path.join(self.data_dir, ".s.PGSQL.*")):
            sleep(0.1)

        # Superuser connection
        self.conn = psycopg2.connect(host=self.data_dir, database="postgres")

    def __del__(self):
        self.close()

    @property
    def data_dir(self):
        return self.uri.host

    def iter_databases(self):
        with self.conn.cursor() as c:
            default_databases = {"postgres", "template0", "template1"}
            c.execute("SELECT datname FROM pg_database")
            for name, in c:
                if name not in default_databases:
                    yield name

    def close(self):
        if self.process is None:
            return

        self.conn.close()
        self.process.terminate()
        self.returncode = self.process.wait()

        # Remove temporary clusters when closing
        if self.is_temporary:
            for path, dirs, files in os.walk(self.data_dir, topdown=False):
                for f in files:
                    os.remove(os.path.join(path, f))
                for d in dirs:
                    os.rmdir(os.path.join(path, d))
            os.rmdir(self.data_dir)

        self.process = None
