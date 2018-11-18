import getpass
import os
import platform
import tempfile

from dsnparse import ParseResult as Dsn
from glob import glob
from subprocess import check_output, PIPE, Popen

from ._compat import ustr
from .utils import is_executable, Version


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
        self.superuser = user

    @property
    def version(self):
        if self._version is None
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
        return self.load_existing(
            data_dir,
            is_temporary=True,
            fsync=False,
            full_page_writes=False,
        )

    def load_cluster(self, data_dir, is_temporary=False, **params):
        cmd = [
            self.postgres,
            "-D", data_dir,
            "-k", data_dir,
            "-c", "listen_addresses=",
        ]

        # Add additional configuration from kwargs
        for k, v in params.items():
            if isinstance(v, bool):
                v = "on" if v else "off"
            cmd.extend(["-c", "{}={}".format(k, v)])

        process = Popen(
            stdout=PIPE,
            stderr=PIPE,
        )
        uri = Uri(
            user=self.superuser,
            host=data_dir,
        )
        return PostgresCluster(process, data_dir, is_temporary)


class PostgresCluster(object):
    def __init__(self, process, uri, is_temporary=False):
        self.is_temporary = is_temporary
        self.returncode = None

        self.conn = psycopg2.connect(host=uri.host, database="postgresql")

    def __del__(self):
        self.close()

    def list_databases(self):
        with self.conn.cursor() as c:
            c.execute("SELECT * FROM pg_database")
            for r in c:
                print(r)

    def kill(self):
        if self.process is not None:
            self.process.kill()
            self.returncode = self.process.wait()
            self.process = None

    def close(self):
        if self.process is not None:
            self.process.terminate()
            self.returncode = self.process.wait()
            self.process = None
