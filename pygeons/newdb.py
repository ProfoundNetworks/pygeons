import collections
import io
import os.path as P
import sqlite3

from typing import (
    Any,
    Iterable,
    List,
    Optional,
)

import marisa_trie  # type: ignore

_CONN = None
_TRIE = None
_COUNTRYINFO = None


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
    assert _CONN
    c = _CONN.cursor()
    result = [
        CountryInfo(*result)
        for result in c.execute('SELECT * FROM countryinfo')
    ]
    c.close()
    return result


def connect(subdir: str = '.') -> None:
    global _CONN
    global _TRIE
    global _COUNTRYINFO

    if _CONN is None:
        _CONN = sqlite3.connect(P.join(subdir, 'db.sqlite3'))
        _COUNTRYINFO = _load_country_info()
    if _TRIE is None:
        _TRIE = marisa_trie.RecordTrie('ii').load(P.join(subdir, 'trie.ii'))


def _select_geonames(subcommand: str, params: Iterable[Any]) -> List[Geoname]:
    assert _CONN
    c = _CONN.cursor()
    command = 'SELECT * FROM geoname %s' % subcommand
    result = [Geoname(*r) for r in c.execute(command, params)]
    c.close()
    return result


def _select_geonames_ids(ids: Iterable[int]) -> List[Geoname]:
    # assert len(ids)

    if not ids:
        return []

    assert _CONN
    c = _CONN.cursor()
    command = (
        'SELECT * FROM geoname WHERE geonameid IN'
        ' (%s) ORDER BY population DESC' % ','.join('?' for _ in ids)
    )
    result = [Geoname(*r) for r in c.execute(command, tuple(ids))]
    c.close()
    return result


def _select_geonames_name(name: str) -> List[Geoname]:
    def g():
        try:
            matches = _TRIE[name.lower()]
        except KeyError:
            pass
        else:
            for (_, geoname_id) in matches:
                yield geoname_id

    geoname_ids = set(g())
    return _select_geonames_ids(geoname_ids)


def country_info(name: str) -> CountryInfo:
    """
    >>> connect()
    >>> i = country_info('ru')
    >>> (i.country, i.population, i.currency_name)
    ('Russia', 144478050, 'Ruble')
    """
    assert _TRIE
    assert _COUNTRYINFO

    ids = {geonameid for (_, geonameid) in _TRIE[name.lower()]}
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


def expand(abbreviation: str) -> List[Geoname]:
    """
    >>> connect()
    >>> [g.name for g in expand('ca')]
    ['California', 'Provincia di Cagliari']
    """
    assert _TRIE
    assert _CONN

    try:
        alt_name_ids, _ = zip(*_TRIE[abbreviation.lower()])
    except KeyError:
        return []

    c = _CONN.cursor()

    command = (
        'SELECT geonameid, isolanguage, isShortName '
        'FROM alternatename WHERE alternateNameId IN '
        '(%s)' % ','.join('?' for _ in alt_name_ids)
    )

    def g():
        for (geonameid, isolanguage, is_short) in c.execute(command, alt_name_ids):
            if isolanguage == 'abbr' or is_short:
                yield geonameid

    geoname_ids = set(g())
    result = _select_geonames_ids(geoname_ids)
    c.close()

    return result


def csc_list(
    city: str,
    state: Optional[str] = None,
    country: Optional[str] = None,
) -> List[Geoname]:
    """
    >>> connect()
    >>> [g.country_code for g in csc_list('sydney')]
    ['AU', 'AU', 'CA', 'US', 'US']
    >>> [g.name for g in csc_list('sydney', country='australia')]
    ['Sydney', 'City of Sydney']
    >>> [g.name for g in csc_list('sydney', state='victoria')]
    ['Sydney', 'City of Sydney']
    """
    cities = _select_geonames_name(city)
    states = _select_geonames_name(state) if state else []
    country = country_info(country) if country else None
    # breakpoint()

    if states and country:
        pass
    elif states:
        #
        # check that states are actually states (A as opposed to P)
        #
        # matches = [c for c in cities if c. ]
        pass
    elif country:
        matches = [c for c in cities if c.country_code == country.iso]
        if matches:
            return matches

    return cities


def sc_list(state: str, country: Optional[str] = None) -> List[Geoname]:
    """
    >>> connect()
    >>> [g.name for g in sc_list('or', None)]
    ['State of Odisha', 'Oregon', 'Provincia di Oristano']
    >>> [g.name for g in sc_list('or', 'US')]
    ['Oregon']
    >>> [g.name for g in sc_list('or', 'united states')]
    ['Oregon']
    """
    assert _CONN
    assert _TRIE

    buf = io.StringIO()
    buf.write('WHERE feature_code in ("ADM1", "ADM2", "ADM3")')

    params = [t[1] for t in _TRIE[state.lower()]]
    buf.write(' AND geonameid IN (%s)' % ','.join(['?' for _ in params]))

    if country:
        buf.write(' AND country_code = ?')
        params.append(country_info(country).iso)

    buf.write(' ORDER BY population DESC')
    subcommand = buf.getvalue()

    return _select_geonames(subcommand, params)
