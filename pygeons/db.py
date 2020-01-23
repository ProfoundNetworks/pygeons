"""Handles lower-level tasks like connecting to the DB, etc."""
import datetime
import logging
import os
import os.path as P

import yaml
import pymongo
import pymongo.errors

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

DEFAULT_HOST = "localhost"
"""The default hostname of the MongoDB server."""

DEFAULT_PORT = 27017
"""The default port that the MongoDB server listens on."""

DEFAULT_DBNAME = "geonames"
"""The default name of the database to read from."""

DEFAULT_AUTH_DBNAME = "admin"
"""The default name of the database to verify user information against."""

DEFAULT_USERNAME = None
"""The default username.  If None, will not authenticate."""

DEFAULT_PASSWORD = None
"""The default password.  If None, will not authenticate."""

CLIENT = None
"""The PyMongo client for connecting to the database."""

DB = None
"""The database object."""

EXPECTED_VERSION = datetime.datetime(2016, 11, 4, 13, 3, 8)
"""The expected database version.  If this is newer than the actual version
at runtime, a warning will be printed to standard error at runtime."""

ADM1 = "admin1"
"""Constant for the admin1 collection."""

ADM2 = "admin2"
"""Constant for the admin2 collection."""

ADMD = "admind"
"""Constant for the admind collection."""

CITY = "cities"
"""Constant for the cities collection."""


class Config(object):
    """Our writable namedtuple."""

    def __init__(
            self, host=DEFAULT_HOST, port=DEFAULT_PORT, dbname=DEFAULT_DBNAME,
            auth_dbname=DEFAULT_AUTH_DBNAME, username=DEFAULT_USERNAME,
            password=DEFAULT_PASSWORD):
        self.host = host
        self.port = port
        self.dbname = dbname
        self.auth_dbname = auth_dbname
        self.username = username
        self.password = password

    def __str__(self):
        return "Config(%r, %r, %r, %r, %r, \"*****\")" % (
            self.host, self.port, self.dbname, self.auth_dbname, self.username
        )


def _hide_password(conf):
    conf = dict(conf)
    if 'password' in conf:
        conf['password'] = '*' * len(conf['password'])
    return conf


def _load_configuration_helper(fin):
    conf = yaml.load(fin)
    if not conf:
        conf = {}
    LOGGER.info("conf: %r", _hide_password(conf))
    host = conf.get("host", DEFAULT_HOST)
    port = conf.get("port", DEFAULT_PORT)
    dbname = conf.get("dbname", DEFAULT_DBNAME)
    auth_dbname = conf.get("auth_dbname", DEFAULT_AUTH_DBNAME)
    username = conf.get("username", DEFAULT_USERNAME)
    password = conf.get("password", DEFAULT_PASSWORD)
    return Config(host, port, dbname, auth_dbname, username, password)


def _load_configuration():
    """Reload the configuration from $HOME/pygeons.yaml, if it exists."""
    default_path = P.expanduser("~/pygeons.yaml")
    config_path = P.abspath(os.environ.get("PYGEON_CONFIG_PATH", default_path))
    if P.isfile(config_path):
        LOGGER.info("loading configuration from %r", config_path)
        with open(config_path) as fin:
            return _load_configuration_helper(fin)
    else:
        LOGGER.warn("%r does not exist, using default config", config_path)
    return Config()

CONFIG = _load_configuration()


def reconnect(connect=True):
    """Reconnect to the database.  If using pygeon in a multi-threaded or
    multi-process application, call this function immediately after you fork.

    See
    http://api.mongodb.org/python/current/faq.html#using-pymongo-with-multiprocessing
    for details."""
    global CLIENT
    global DB
    CLIENT, DB = _reconnect_helper(connect)


def _reconnect_helper(connect=True):
    """Returns a client and database handle."""
    client = pymongo.MongoClient(CONFIG.host, CONFIG.port, connect=connect)
    db = client[CONFIG.dbname]
    if CONFIG.username and CONFIG.password and CONFIG.auth_dbname:
        db.authenticate(CONFIG.username, CONFIG.password,
                        source=CONFIG.auth_dbname)
    return client, db


def test_connection():
    """If we're not already connected, then connect. Otherwise, do nothing."""
    if not (CLIENT and DB):
        reconnect()

    #
    # Everything that touches the DB should first call _test_connection to
    # ensure a DB connection is available.
    #


def get_version():
    """Return the version of the database to use."""
    _test_connection()
    ver = DB.util.find_one({"name": "version"})
    if ver:
        return datetime.datetime.strptime(ver["value"], "%Y.%m.%d-%H.%M.%S")
    return None


def check_version():
    """Print a warning if the current version is not the expected version."""
    try:
        version = get_version()
    except pymongo.errors.OperationFailure as opf:
        LOGGER.error(opf)
        version = None
    if version is None or version < EXPECTED_VERSION:
        warnings.warn("unexpected version: %s" % repr(version), RuntimeWarning)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?")
    args = parser.parse_args()

    if args.command is None:
        print(CONFIG.dbname)
    elif args.command == "version":
        print(get_version())
    elif args.command == "expected-version":
        print("-".join([DEFAULT_DBNAME, EXPECTED_VERSION]))
    elif args.command == "db":
        print(CONFIG.dbname)
    else:
        parser.error("invalid command: %s" % args[0])

    sys.exit(0 if get_version() > EXPECTED_VERSION else 1)
