"""A more Pythonic interface for geonames.

Offers the following abstraction over the geonames data:

- The world is divided into countries (see the Country class)
- Each country is divided into states (see the State class)
- A state includes multiple cities (see the City class)

Countries are at the very top level.
You may access them via the constructor directly.

>>> Country('ivory coast')
Country('Ivory Coast')

Common alternative names also work:

>>> Country('côte d’ivoire')
Country('Ivory Coast')

ISO abbreviations (both two- and three-letter,
`ISO-3166 alpha-1 and alpha-2
<https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes>`__,
respectively) also work:

>>> Country('civ')
Country('Ivory Coast')
>>> _.iso
'CI'

You can access the states of a country with the obvious syntax:

>>> Country('usa').states['idaho']
State.gid(5596512, 'ADM1', 'Idaho', 'US')
>>> 'idaho' in Country('usa').states
True

States are administrative divisions of a country.
They're called different things depending on the country
(e.g. territory, province, region, prefecture, etc.),
but most countries have such divisions for administrative purposes.

In geonames, there are multiple levels of administrative entities, such as:

    - ADM1
    - ADM2
    - ADM3
    - ADM4
    - ADMD

Pygeons groups all the administrative entities under the State class.

Common names and abbreviations work:

>>> Country('usa').states['id']
State.gid(5596512, 'ADM1', 'Idaho', 'US')

On the next level down, you have cities:

>>> Country('usa').states['idaho'].cities['moscow']
City.gid(5601538, 'Moscow', 'US')
>>> 'moscow' in Country('usa').states['idaho']
True

You can shortcut the state level altogether.
This is particularly useful if you don't know the state.

>>> 'moscow' in Country('russia')
True
>>> Country('russia').cities['moscow']
City.gid(524901, 'Moscow', 'RU')

You may be surprised that city names are not necessarily unique.
In such cases, use the find_cities function:

>>> find_cities("oslo")[:2]
[City.gid(3143244, 'Oslo', 'NO'), City.gid(5040425, 'Oslo', 'US')]

If there are multiple results, then they get sorted by decreasing population.

>>> oslo = find_cities("oslo", country='no')[0]
>>> oslo
City.gid(3143244, 'Oslo', 'NO')

The gid is the unique geonames ID for a place.
You can use it as a compact identifier to reconstruct place names:

>>> City.gid(3143244)
City.gid(3143244, 'Oslo', 'NO')

You can access all the fields from the geonames data model directly:

>>> oslo.latitude, oslo.longitude, oslo.population
(59.91273, 10.74609, 580000)

Calculating the distance between two cities::

>>> trondheim = find_cities('trondheim')[0]
>>> trondheim
City.gid(3133880, 'Trondheim', 'NO')

>>> round(oslo.distance_to(trondheim))
392

Testing for valid city and country combinations:

>>> 'sapporo' in Country('jp').cities
True
>>> 'auckland' in Country('nz').cities
True
>>> 'auckland' in Country('au').cities
False

Testing for valid state and country combinations:

>>> 'hokkaido' in Country('jp').states
True
>>> 'nsw' in Country('au').states
True
>>> 'new mexico' in Country('ca').states
False

Expanding country-specific abbreviations:

>>> [g.name for g in Country('au').expand('nsw')]
['State of New South Wales']
>>> [g.name for g in Country('usa').expand('co')]
['Colorado']

Pygeons understands names in English and languages local to a particular country:

>>> find_cities('札幌')[0]
City.gid(2128295, 'Sapporo', 'JP')

>>> find_cities('москва', country='ru')[0]
City.gid(524901, 'Moscow', 'RU')

>>> Country('jp').normalize(language='ja')
'日本'

"""

import io
import math

from typing import (
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
)

from pygeons import db

db.connect()
assert db.TRIE
assert db.CONN

DEFAULT_LANGUAGE = 'en'


def expand(abbreviation: str, country_code: Optional[str] = None) -> List[db.Geoname]:
    """
    >>> [g.name for g in expand('ca')]
    ['California', 'Provincia di Cagliari']
    """
    assert db.TRIE

    try:
        matches = db.TRIE[abbreviation.lower()]
    except KeyError:
        return []

    alt_name_ids = [m[3] for m in matches if m[3] != -1]

    assert db.CONN
    c = db.CONN.cursor()

    command = (
        'SELECT geonameid, isolanguage, isShortName FROM alternatename'
        ' WHERE alternateNameId IN (%s)' % ','.join('?' for _ in alt_name_ids)
    )

    def g():
        for (geonameid, isolanguage, is_short) in c.execute(command, alt_name_ids):
            if isolanguage == 'abbr' or is_short:
                yield geonameid

    geoname_ids = set(g())
    result = db.select_geonames_ids(geoname_ids, country_code=country_code)
    c.close()

    return result


def contains(large: Union[db.Geoname, db.CountryInfo], small: db.Geoname) -> bool:
    if isinstance(large, db.CountryInfo):
        return large.iso == small.country_code
    elif small.country_code != large.country_code:
        return False

    if large.feature_code == 'PCLI':
        return True
    elif large.feature_code.startswith('ADM1'):
        return small.admin1_code == large.admin1_code
    elif large.feature_code.startswith('ADM2'):
        return small.admin2_code == large.admin2_code
    elif large.feature_code.startswith('ADM3'):
        return small.admin3_code == large.admin3_code
    elif large.feature_code.startswith('ADM4'):
        return small.admin4_code == large.admin4_code

    return False


def _match(
    cities: List[db.Geoname],
    states: List[db.Geoname],
) -> Iterable[Tuple[db.Geoname, db.Geoname]]:
    for s in states:
        for c in cities:
            if contains(s, c):
                yield c, s


def csc_list(
    city: str,
    state: Optional[str] = None,
    country: Optional[str] = None,
) -> List[db.Geoname]:
    """
    >>> [g.country_code for g in csc_list('sydney')]
    ['AU', 'CA', 'US', 'US', 'ZA', 'VU', 'US', 'US', 'CA']
    >>> [g.name for g in csc_list('sydney', country='australia')]
    ['Sydney']
    >>> [g.timezone for g in csc_list('sydney', state='victoria')][:3]
    ['Australia/Sydney', 'America/Glace_Bay', 'America/Phoenix']
    """
    if state and country:
        cinfo = db.country_info(country)
        states = [
            g for g in db.select_geonames_name(state)
            if g.feature_class == 'A' and g.country_code == cinfo.iso
        ]
        cities = [
            g for g in db.select_geonames_name(city)
            if g.feature_class == 'P' and g.country_code == cinfo.iso
        ]
        city_matches = list(_match(cities, states))
        if city_matches:
            return [c for (c, _) in city_matches]

    #
    # Try omitting state.  If the country is specified, that alone may be sufficient.
    #
    if country:
        cinfo = db.country_info(country)
        cities = [
            g for g in db.select_geonames_name(city)
            if g.feature_class == 'P' and g.country_code == cinfo.iso
        ]
        if cities:
            return cities

    #
    # Perhaps state is really a city?
    #
    if state and country:
        cinfo = db.country_info(country)
        cities = [
            g for g in db.select_geonames_name(state)
            if g.country_code == cinfo.iso
        ]
        if cities:
            return cities

    #
    # Perhaps the specified country is wrong?
    #
    if state:
        states = [g for g in db.select_geonames_name(state) if g.feature_class == 'A']
        cities = [g for g in db.select_geonames_name(city) if g.feature_class == 'P']
        city_matches = list(_match(cities, states))
        if city_matches:
            return [c for (c, _) in city_matches]

    #
    # Perhaps city itself is unique?
    #
    cities = [g for g in db.select_geonames_name(city) if g.feature_class == 'P']
    if cities:
        return cities

    return list(db.select_geonames_name(city))


def sc_list(state: str, country: Optional[str] = None) -> List[db.Geoname]:
    """
    >>> [g.name for g in sc_list('or', None)]
    ['State of Odisha', 'Oregon', 'Provincia di Oristano']
    >>> [g.name for g in sc_list('or', 'US')]
    ['Oregon']
    >>> [g.name for g in sc_list('or', 'united states')]
    ['Oregon']
    """
    buf = io.StringIO()
    buf.write('WHERE feature_code in ("ADM1", "ADM2", "ADM3")')

    assert db.TRIE
    params = [t[2] for t in db.TRIE[state.lower()]]
    buf.write(' AND geonameid IN (%s)' % ','.join(['?' for _ in params]))

    if country:
        buf.write(' AND country_code = ?')
        params.append(db.country_info(country).iso)

    buf.write(' ORDER BY population DESC')
    subcommand = buf.getvalue()

    return db.select_geonames(subcommand, params)


class Country:
    def __init__(self, name):
        self.data = db.country_info(name)
        for key, value in self.data._asdict().items():
            setattr(self, key, value)

        #
        # The collection to go through depends on the country.
        # e.g. for Australia, it makes sense to go through admin1.
        # For GB, it makes more sense to go through admin2, because the
        # top level contains country names like England, Scotland, etc.
        #
        self._state_feature_code = 'ADM1'

    def __repr__(self):
        return 'Country(%r)' % self.country

    def __str__(self):
        return 'Country(%r)' % self.country

    def __contains__(self, item):
        if isinstance(item, (City, State)):
            return item.countryCode == self.iso
        elif isinstance(item, str):
            for g in db.select_geonames_name(item):
                if contains(self.data, g):
                    return True
        return False

    def normalize(self, language=DEFAULT_LANGUAGE):
        return _normalize(self.geonameid, language)

    def expand(self, abbreviation):
        return expand(abbreviation, country_code=self.iso)

    @property
    def states(self):
        return StateCollection(country_code=self.iso, feature_code=self._state_feature_code)

    @property
    def admin1(self):
        return StateCollection(country_code=self.iso, feature_code='ADM1')

    @property
    def admin2(self):
        return StateCollection(country_code=self.iso, feature_code='ADM2')

    @property
    def admind(self):
        return StateCollection(country_code=self.iso, feature_code='ADMD')

    @property
    def cities(self):
        return CityCollection(parent=self)

    @property
    def postcodes(self):
        def gen():
            query = {'countryCode': self.iso}
            for info in db.DB.postcodes.find(query):
                yield Postcode(info)

        return list(gen())

    @property
    def names(self):
        return db.get_alternatenames(self.geonameid)


class StateCollection:
    def __init__(self, country_code, feature_code):
        self.country_code = country_code
        self.feature_code = feature_code

        self._cursor = db.CONN.cursor()
        command = (
            'SELECT * FROM geoname'
            ' WHERE country_code = ? AND feature_code = ?'
            ' ORDER BY population DESC'
        )
        self._cursor.execute(command, (self.country_code, self.feature_code))

    def __iter__(self):
        return self

    def __next__(self):
        result = next(self._cursor)
        return State(db.Geoname(*result))

    def __getitem__(self, key):
        return find_states(key, country=self.country_code)[0]

    def __contains__(self, key):
        return bool(find_states(key, country=self.country_code))

    def __str__(self):
        return 'StateCollection(%r, %r)' % (self.country_code, self.feature_code)

    def __repr__(self):
        return 'StateCollection(%r, %r)' % (self.country_code, self.feature_code)

    def __len__(self):
        cursor = db.CONN.cursor()
        command = (
            'SELECT COUNT(*) FROM geoname'
            ' WHERE country_code = ? AND feature_code = ?'
        )
        return cursor.execute(command, (self.country_code, self.feature_code))


class State:
    def __init__(self, data):
        self.data = data
        for key, value in self.data._asdict().items():
            setattr(self, key, value)

    def __repr__(self):
        return 'State.gid(%r, %r, %r, %r)' % (
            self.geonameid, self.feature_code, self.name, self.country_code,
        )

    def __str__(self):
        return 'State(%r, %r, %r)' % (self.feature_code, self.name, self.country_code)

    def __contains__(self, item):
        if isinstance(item, str):
            for g in db.select_geonames_name(item):
                if contains(self.data, g):
                    return True
        return False

    def normalize(self, language=DEFAULT_LANGUAGE):
        return _normalize(self.geonameid, language)

    @property
    def country(self):
        return Country(self.country_code)

    @staticmethod
    def gid(geonames_id, *args, **kwargs):
        c = db.CONN.cursor()
        result = c.execute('SELECT * FROM geoname WHERE geonameid = ?', (geonames_id,))
        return State(db.Geoname(*next(result)))

    @property
    def cities(self):
        return CityCollection(parent=self)

    @property
    def names(self):
        return db.get_alternatenames(self.geonameid)


class CityCollection:
    def __init__(self, parent):
        self.parent = parent

        self._cursor = db.CONN.cursor()

        if isinstance(self.parent, Country):
            self._where = 'country_code = ? AND feature_class = "P"'
            self._params = (self.parent.iso, )
        else:
            the_map = {
                'ADM1': 'admin1_code',
                'ADM2': 'admin2_code',
                'ADM3': 'admin3_code',
                'ADM4': 'admin4_code',
            }
            self._admin_field = the_map[parent.feature_code]
            self._admin_code = getattr(parent, self._admin_field)

            self._where = 'country_code = ? AND %s = ? AND feature_class = "P"' % self._admin_field
            self._params = (self.parent.country_code, self._admin_code)

        command = 'SELECT * FROM geoname WHERE %s ORDER BY population DESC' % self._where
        self._cursor.execute(command, self._params)

    def __iter__(self):
        return self

    def __next__(self):
        result = next(self._cursor)
        return City(db.Geoname(*result))

    def __getitem__(self, key):
        if isinstance(self.parent, Country):
            return find_cities(key, country=self.parent.iso)[0]
        else:
            return find_cities(key, state=self.parent.name, country=self.parent.country_code)[0]

    def __contains__(self, item):
        if isinstance(self.parent, Country):
            country_code = self.parent.iso
        else:
            country_code = self.parent.country_code

        if isinstance(item, str):
            for g in db.select_geonames_name(item):
                if g.country_code == country_code:
                    return True

        return False

    def __str__(self):
        return 'CityCollection(%r)' % self.parent

    def __repr__(self):
        return 'CityCollection(%r)' % self.parent

    def __len__(self):
        command = 'SELECT * FROM geoname WHERE ' + self._where
        return self._cursor.execute(command, self._params)[0]


class City:
    def __init__(self, info):
        self.data = info
        for key, value in self.data._asdict().items():
            setattr(self, key, value)

    def __repr__(self):
        return 'City.gid(%r, %r, %r)' % (self.geonameid, self.name, self.country_code)

    def __str__(self):
        return 'City(%r, %r)' % (self.name, self.country_code)

    def _get_adm(self, level):
        c = db.CONN.cursor()
        admin_field = 'admin%d_code' % level
        admin_code = getattr(self, admin_field)
        feature_code = 'ADM%d' % level
        command = (
            'SELECT * FROM geoname WHERE '
            'country_code = ? AND feature_code = ? AND %s = ?' % admin_field
        )
        params = (self.country_code, feature_code, admin_code)
        result = c.execute(command, params)
        return db.Geoname(*next(result))

    @property
    def admin1(self):
        return State(self._get_adm(1))

    @property
    def admin2(self):
        return State(self._get_adm(2))

    @property
    def admin3(self):
        return State(self._get_adm(3))

    @property
    def admin4(self):
        return State(self._get_adm(4))

    @property
    def state(self):
        return self.admin1

    @property
    def country(self):
        return Country(self.country_code)

    @staticmethod
    def gid(geonames_id, *args, **kwargs):
        c = db.CONN.cursor()
        result = c.execute('SELECT * FROM geoname WHERE geonameid = ?', (geonames_id,))
        return City(db.Geoname(*next(result)))

    def distance_to(self, other):
        return _haversine_dist(
            self.latitude,
            self.longitude,
            other.latitude,
            other.longitude,
        )

    @property
    def names(self):
        return db.get_alternatenames(self.geonameid)

    def normalize(self, language=DEFAULT_LANGUAGE):
        return _normalize(self.geonameid, language)


def _normalize(geonameid, language):
    c = db.CONN.cursor()

    canonical = db.select_geonames_ids([geonameid])[0].name
    if language == 'en':
        return canonical

    def _lookup(subcommand):
        command = (
            'SELECT alternate_name FROM alternatename '
            'WHERE geonameid = ? AND isolanguage = ? AND '
        ) + subcommand
        result = c.execute(command, (geonameid, language))
        try:
            return next(result)[0]
        except StopIteration:
            return None

    preferred = _lookup('isPreferredName = 1')
    if preferred:
        return preferred

    alt = _lookup(
        'isHistoricName != 1 AND isColloquial != 1 '
        'ORDER BY length(alternate_name) DESC'
    )
    if alt:
        return alt

    return canonical


class Postcode:
    def __init__(self, info):
        self.data = info

    def __repr__(self):
        return 'Postcode(%(postCode)r, %(placeName)r)' % self.data

    def __str__(self):
        return 'Postcode(%(postCode)r, %(placeName)r)' % self.data

    def normalize(self, language=DEFAULT_LANGUAGE):
        #
        # FIXME
        #
        return self.data['placeName']


def find_cities(name, state=None, country=None):
    """
    >>> find_cities('yono', country='JP')[0].state.name
    'Saitama-ken'
    """
    cities = [City(data) for data in csc_list(name, state, country)]
    return sorted(cities, key=lambda s: s.population, reverse=True)


def find_states(name, country=None):
    states = [State(data) for data in sc_list(name, country)]
    return sorted(states, key=lambda s: s.population, reverse=True)


def _to_radian(degrees: float) -> float:
    return math.pi * degrees / 180


def _haversine_dist(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate the distance between two latitude-long pairs."""
    #
    # https://en.wikipedia.org/wiki/Haversine_formula
    #
    def hav(theta):
        """The haversine function."""
        return math.pow(math.sin(theta / 2), 2)

    R = 6371
    fi1, lam1, fi2, lam2 = [_to_radian(x) for x in [lat1, lng1, lat2, lng2]]
    d = 2 * R * math.asin(
        math.sqrt(
            hav(fi2 - fi1) + math.cos(fi1) * math.cos(fi2) * hav(lam2 - lam1)
        )
    )
    return d
