"""Implements low-level database structures and functions.

Expects you to call :func:`connect` before you do anything with the DB.

Expects the database to be initialized.  If it is not, see :mod:`pygeons.initialize`.

By default, the database lives under ``$HOME/.pygeons``.
You can modify this behavior using the ``PYGEONS_HOME`` environment variable.
You can also specify the subdirectory explicitly when you call :func:`connect`.
"""
import collections
import io
import os
import os.path as P
import sqlite3

from typing import (
    Any,
    Iterable,
    List,
    Optional,
    Tuple,
)

import marisa_trie  # type: ignore

CONN = None
TRIE = None
_COUNTRYINFO = None

MARISA_FORMAT = 'c2sii'
MARISA_FILENAME = 'marisa_trie.' + MARISA_FORMAT
ENCODING = 'utf-8'

DEFAULT_SUBDIR = os.environ.get('PYGEONS_HOME', P.expanduser('~/.pygeons'))

Geoname = collections.namedtuple(
    'Geoname',
    [
        'geonameid',
        'name',
        'asciiname',
        'alternatenames',
        'latitude',
        'longitude',
        'feature_class',
        'feature_code',
        'country_code',
        'cc2',
        'admin1_code',
        'admin2_code',
        'admin3_code',
        'admin4_code',
        'population',
        'elevation',
        'dem',
        'timezone',
        'modification_date',
    ]
)

CountryInfo = collections.namedtuple(
    'CountryInfo',
    [
        'iso',
        'iso3',
        'iso_numeric',
        'fips',
        'country',
        'capital',
        'area',
        'population',
        'continent',
        'tld',
        'currency_code',
        'currency_name',
        'phone',
        'postal_code_format',
        'postal_code_regex',
        'languages',
        'geonameid',
        'neighbors',
        'equivalent_fips_code',
    ]
)


def _load_country_info() -> List[CountryInfo]:
    assert CONN
    c = CONN.cursor()
    result = [
        CountryInfo(*result)
        for result in c.execute('SELECT * FROM countryinfo')
    ]
    c.close()
    return result


def connect(subdir: str = DEFAULT_SUBDIR) -> None:
    global CONN
    global TRIE
    global _COUNTRYINFO

    if CONN is None:
        CONN = sqlite3.connect(P.join(subdir, 'db.sqlite3'))
        _COUNTRYINFO = _load_country_info()
    if TRIE is None:
        TRIE = marisa_trie.RecordTrie(MARISA_FORMAT).load(P.join(subdir, MARISA_FILENAME))


def select_geonames(subcommand: str, params: Iterable[Any]) -> List[Geoname]:
    assert CONN
    c = CONN.cursor()
    command = 'SELECT * FROM geoname %s' % subcommand
    result = [Geoname(*r) for r in c.execute(command, params)]
    c.close()
    return result


def select_geonames_ids(
    ids: Iterable[int],
    country_code: Optional[str] = None,
) -> List[Geoname]:
    if not ids:
        return []

    params: List[Any] = list(ids)

    assert CONN
    c = CONN.cursor()

    buf = io.StringIO()
    buf.write('SELECT * FROM geoname WHERE')
    buf.write(' geonameid IN (%s)' % ','.join('?' for _ in params))
    if country_code:
        buf.write(' AND country_code = ?')
        params.append(country_code)
    buf.write(' ORDER BY population DESC')
    command = buf.getvalue()

    result = [Geoname(*r) for r in c.execute(command, params)]
    c.close()
    return result


def select_geonames_name(name: str) -> List[Geoname]:
    def g():
        try:
            matches = TRIE[name.lower()]
        except KeyError:
            pass
        else:
            for m in matches:
                if m[0] in (b'A', b'P'):
                    yield m[2]

    geoname_ids = set(g())
    return select_geonames_ids(geoname_ids)


def country_info(name: str) -> CountryInfo:
    """
    >>> connect()
    >>> i = country_info('ru')
    >>> (i.country, i.population, i.currency_name)
    ('Russia', 144478050, 'Ruble')
    """
    assert TRIE
    assert _COUNTRYINFO

    try:
        ids = {m[2] for m in TRIE[name.lower()]}
    except KeyError:
        ids = set()

    candidates = [
        ci
        for ci in _COUNTRYINFO
        if ci.geonameid in ids
        or name.lower() in (ci.iso.lower(), ci.iso3.lower())
    ]
    if not candidates:
        raise ValueError('no such country: %r' % name)
    elif len(candidates) == 1:
        return candidates[0]
    else:
        raise ValueError('ambiguous country name: %r' % name)


def get_alternatenames(geonameid: str) -> List[Tuple[str, str]]:
    assert CONN
    c = CONN.cursor()
    command = (
        'SELECT isolanguage, alternate_name FROM alternatename'
        ' WHERE geonameid = ?'
    )

    def g():
        for isolanguage, alternate_name in c.execute(command, (geonameid, )):
            yield isolanguage, alternate_name

    return list(g())
