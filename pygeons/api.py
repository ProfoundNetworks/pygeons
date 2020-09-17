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
    Iterator,
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
        'SELECT geonameid FROM alternatename '
        'WHERE (isolanguage == "abbr" OR isShortName) AND '
        'alternateNameId IN (%s)' % ','.join('?' for _ in alt_name_ids)
    )

    geoname_ids = {geonameid for (geonameid, ) in c.execute(command, alt_name_ids)}
    result = db.select_geonames_ids(geoname_ids, country_code=country_code)
    c.close()

    return result


def _contains(large: db.Geoname, small: db.Geoname) -> bool:
    large_code = '.'.join(v for (n, v) in _generate_admin_codes(large))
    small_code = '.'.join(v for (n, v) in _generate_admin_codes(small))
    return small_code.startswith(large_code)


def _match(
    cities: List[db.Geoname],
    states: List[db.Geoname],
) -> Iterable[Tuple[db.Geoname, db.Geoname]]:
    for s in states:
        for c in cities:
            if _contains(s, c):
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


def sc_list(
    state: str,
    country: Optional[str] = None,
    constraints: Optional[List[str]] = None,
) -> List[db.Geoname]:
    """
    >>> [g.name for g in sc_list('or', None)]
    ['State of Odisha', 'Oregon', 'Provincia di Oristano']
    >>> [g.name for g in sc_list('or', 'US')]
    ['Oregon']
    >>> [g.name for g in sc_list('or', 'united states')]
    ['Oregon']
    """
    assert db.TRIE
    try:
        params = [t[2] for t in db.TRIE[state.lower()]]
    except KeyError:
        return None

    buf = io.StringIO()
    buf.write('WHERE feature_code in ("ADM1", "ADM2", "ADM3") ')
    buf.write('AND geonameid IN (%s) ' % ','.join(['?' for _ in params]))

    if country:
        buf.write('AND country_code = ? ')
        params.append(db.country_info(country).iso)

    if constraints:
        constraints = list(constraints)

    if constraints:
        buf.write('AND admin1_code = ? ')
        params.append(constraints.pop(0))

    if constraints:
        buf.write('AND admin2_code = ? ')
        params.append(constraints.pop(0))

    if constraints:
        buf.write('AND admin3_code = ? ')
        params.append(constraints.pop(0))

    buf.write('ORDER BY population DESC')
    subcommand = buf.getvalue()

    return db.select_geonames(subcommand, params)


def _generate_admin_codes(
    geoname: db.Geoname,
    max_level: Optional[int] = None,
) -> Iterator[Tuple[str, str]]:
    if max_level is None:
        if geoname.feature_code == 'PCLI':
            max_level = 0
        elif geoname.feature_code == 'ADM1':
            max_level = 1
        elif geoname.feature_code == 'ADM2':
            max_level = 2
        elif geoname.feature_code == 'ADM3':
            max_level = 3
        else:
            max_level = 4

    assert max_level is not None
    yield 'country_code', geoname.country_code

    for level in (1, 2, 3, 4):
        if level > max_level:
            break
        field_name = 'admin%d_code' % level
        field_value = getattr(geoname, field_name)
        if field_value:
            yield field_name, field_value


def _wrap(geoname: db.Geoname) -> Union['Geoname', 'Country', 'State', 'City']:
    if geoname.feature_code == 'PCLI':
        return Country(geoname.country_code)
    elif geoname.feature_class == 'A':
        return State(geoname)
    elif geoname.feature_class == 'P':
        return City(geoname)
    else:
        return Geoname(geoname)


#
# Wraps the db.Geoname namedtuple to provide additional behavior.
#
class Geoname:
    """Represents a record in the ``geoname`` table.

    Every place name in the ``geonames.org`` dataset, including countries,
    states, etc. corresponds to one of these.

    Corresponds directly to the data model described at
    http://download.geonames.org/export/dump/.
    """
    def __init__(self, geoname: db.Geoname) -> None:
        self.geoname = geoname
        self._cursor = None
        self._params = [self.geoname.geonameid]

        buf = io.StringIO()
        buf.write('SELECT * FROM geoname WHERE geonameid != ? ')
        for field_name, field_value in _generate_admin_codes(self.geoname):
            buf.write('AND %s = ? ' % field_name)
            self._params.append(field_value)
        buf.write('ORDER BY population DESC')
        self._command = buf.getvalue()

    @property
    def geonameid(self) -> int:
        """integer id of record in geonames database"""
        return self.geoname.geonameid

    @property
    def name(self) -> str:
        """name of geographical point"""
        return self.geoname.name

    @property
    def asciiname(self) -> str:
        """name of geographical point in plain ascii characters"""
        return self.geoname.asciiname

    @property
    def latitude(self) -> float:
        """latitude in decimal degrees (wgs84)"""
        return self.geoname.latitude

    @property
    def longitude(self) -> float:
        """longitude in decimal degrees (wgs84)"""
        return self.geoname.longitude

    @property
    def feature_class(self) -> str:
        """see http://www.geonames.org/export/codes.html"""
        return self.geoname.feature_class

    @property
    def feature_code(self) -> str:
        """see http://www.geonames.org/export/codes.html"""
        return self.geoname.feature_code

    @property
    def country_code(self) -> str:
        """ISO-3166 2-letter country code, 2 characters"""
        return self.geoname.country_code

    @property
    def cc2(self) -> str:
        """alternate country codes, comma separated"""
        return self.geoname.cc2

    @property
    def admin1_code(self) -> str:
        """fipscode (subject to change to iso code)"""
        return self.geoname.admin1_code

    @property
    def admin2_code(self) -> str:
        """code for the second administrative division"""
        return self.geoname.admin2_code

    @property
    def admin3_code(self) -> str:
        """code for third level administrative division"""
        return self.geoname.admin3_code

    @property
    def admin4_code(self) -> str:
        """code for fourth level administrative division"""
        return self.geoname.admin4_code

    @property
    def population(self) -> int:
        """"""
        return self.geoname.population

    @property
    def elevation(self) -> str:
        """in meters"""
        return self.geoname.elevation

    @property
    def dem(self) -> str:
        """digital elevation model, srtm3 or gtopo30"""
        return self.geoname.dem

    @property
    def timezone(self) -> str:
        """the iana timezone id (see file timeZone.txt)"""
        return self.geoname.timezone

    @property
    def modification_date(self) -> str:
        """date of last modification in yyyy-MM-dd format"""
        return self.geoname.modification_date

    def normalize(self, language: str = DEFAULT_LANGUAGE) -> str:
        """Returns the preferred name of this place."""
        if language == 'en':
            return self.geoname.name

        c = db.CONN.cursor()

        def _lookup(subcommand):
            command = (
                'SELECT alternate_name FROM alternatename '
                'WHERE geonameid = ? AND isolanguage = ? AND '
            ) + subcommand
            result = c.execute(command, (self.geonameid, language))
            try:
                return next(result)[0]
            except StopIteration:
                return None

        preferred = _lookup('isPreferredName = 1')
        if preferred:
            return preferred

        alt = _lookup(
            'isHistoric != 1 AND isColloquial != 1 '
            'ORDER BY length(alternate_name) DESC'
        )
        if alt:
            return alt

        return self.geoname.name

    @property
    def country(self) -> 'Country':
        """Returns the country that contains this place."""
        return Country(self.country_code)

    @property
    def names(self) -> List[Tuple[str, str]]:
        """Returns all the names of this place, for all languages."""
        return db.get_alternatenames(self.geonameid)

    def _get_parent_adm(self, level):
        c = db.CONN.cursor()

        feature_code = 'ADM%d' % level
        params = [self.country_code, feature_code]

        buf = io.StringIO()
        buf.write('SELECT * FROM geoname WHERE ')
        buf.write('country_code = ? AND feature_code = ? ')

        if level >= 1 and self.admin1_code:
            buf.write('AND admin1_code = ? ')
            params.append(self.admin1_code)

        if level >= 2 and self.admin2_code:
            buf.write('AND admin2_code = ? ')
            params.append(self.admin2_code)

        if level >= 3 and self.admin3_code:
            buf.write('AND admin3_code = ? ')
            params.append(self.admin3_code)

        if level == 4 and self.admin4_code:
            buf.write('AND admin4_code = ? ')
            params.append(self.admin4_code)

        command = buf.getvalue()

        result = c.execute(command, params)
        return db.Geoname(*next(result))

    @property
    def admin1(self) -> Optional['State']:
        """Navigate to the first level of the administrative hierarchy.

        >>> Country('us').cities['boston'].admin1.name
        'Massachusetts'
        """
        if self.feature_code == 'PCLI':
            return Collection(self, feature_code='ADM1')
        elif self.feature_code == 'ADM1':
            return self
        elif self.admin1_code:
            return State(self._get_parent_adm(1))
        else:
            return None

    @property
    def admin2(self) -> Optional[Union['State', 'Collection']]:
        """Navigate to the second level of the administrative hierarchy.

        For entities that exist above that level, this will be a collection
        of second-level descendants:

        >>> [a2.name for a2 in Country('us').admin1['ma'].admin2][:3]
        ['Middlesex County', 'Worcester County', 'Essex County']

        For entities that exist below that level, this will be the
        second-level ancestor:

        >>> Country('us').cities['boston'].admin2.name
        'Suffolk County'
        """
        if self.feature_code in ('PCLI', 'ADM1'):
            return Collection(self, feature_code='ADM2')
        elif self.feature_code == 'ADM2':
            return self
        elif self.admin2_code:
            return State(self._get_parent_adm(2))
        else:
            return None

    @property
    def admin3(self) -> Optional[Union['State', 'Collection']]:
        """Navigate to the third level of the administrative hierarchy.

        For entities that exist above that level, this will be a collection
        of third-level descendants:

        >>> [a3.name for a3 in Country('us').admin1['ma'].admin2['suffolk'].admin3][:3]
        ['City of Boston', 'City of Revere', 'City of Chelsea']

        For entities that exist below that level, this will be the third-level
        ancestor:

        >>> Country('us').cities['boston'].admin3.name
        'City of Boston'
        """
        if self.feature_code in ('PCLI', 'ADM1', 'ADM2'):
            return Collection(self, feature_code='ADM3')
        elif self.feature_code == 'ADM3':
            return self
        elif self.admin3_code:
            return State(self._get_parent_adm(3))
        else:
            return None

    @property
    def admin4(self) -> Optional[Union['State', 'Collection']]:
        if self.feature_code in ('PCLI', 'ADM1', 'ADM2', 'ADM3'):
            return Collection(self, feature_code='ADM4')
        elif self.feature_code == 'ADM4':
            return self
        elif self.admin4_code:
            return State(self._get_parent_adm(4))
        else:
            return None

    @property
    def state(self):
        return self.admin1

    @property
    def full_admin_code(self) -> str:
        values = [value for (unused_name, value) in _generate_admin_codes(self.geoname)]
        return '.'.join(values)

    def distance_to(self, other: 'Geoname') -> float:
        """Returns the distance to the other place."""
        return _haversine_dist(self.latitude, self.longitude, other.latitude, other.longitude)

    def __repr__(self):
        return 'Geoname.gid(%r, %r, %r)' % (self.geonameid, self.name, self.country_code)

    def __str__(self):
        return 'Geoname(%r, %r)' % (self.name, self.country_code)

    def __iter__(self):
        return self

    def __next__(self) -> db.Geoname:
        if self._cursor is None:
            self._cursor = db.CONN.cursor()
            self._cursor.execute(self._command, self._params)

        while True:
            result = next(self._cursor)
            geoname = db.Geoname(*result)
            if _contains(self.geoname, geoname):
                return _wrap(geoname)

    def __len__(self):
        cursor = db.CONN.cursor()
        command = self._command.replace('SELECT *', 'SELECT COUNT(*)')
        return next(cursor.execute(command, self._params))[0]

    def __getitem__(self, key):
        for geoname in db.select_geonames_name(key):
            if self.geoname != geoname and _contains(self.geoname, geoname):
                return _wrap(geoname)
        raise KeyError('could not find %r in %r' % (key, self))

    def __contains__(self, other):
        if isinstance(other, str):
            try:
                self[other]
            except KeyError:
                return False
            else:
                return True
        elif isinstance(other, Geoname):
            return _contains(self.geoname, other.geoname)
        elif isinstance(other, db.Geoname):
            return _contains(self.geoname, other)
        return False


#
# Wraps both the db.Geoname and db.CountryInfo namedtuples and provides
# additional useful behavior.
#
class Country(Geoname):
    """Represents a country.

    On top of the regular :class:`Geoname` fields, also exposes country information.
    See http://download.geonames.org/export/dump/countryInfo.txt
    """
    def __init__(self, name: str) -> None:
        self.info = db.country_info(name)
        geoname = db.select_geonames_ids([self.info.geonameid])[0]

        super().__init__(geoname)

        #
        # The collection to go through depends on the country.
        # e.g. for Australia, it makes sense to go through admin1.
        # For GB, it makes more sense to go through admin2, because the
        # top level contains country names like England, Scotland, etc.
        #
        self._state_feature_code = 'ADM1'

    @property
    def iso(self) -> str:
        return self.info.iso

    @property
    def iso3(self) -> str:
        return self.info.iso3

    @property
    def iso_numeric(self) -> int:
        return self.info.iso_numeric

    @property
    def fips(self) -> str:
        return self.info.fips

    @property
    def country(self) -> str:
        return self.info.country

    @property
    def capital(self) -> 'City':
        c = db.CONN.cursor()
        command = (
            'SELECT * FROM geoname '
            'WHERE (name = ? OR asciiname = ?) '
            'AND country_code = ? AND feature_code = "PPLC"'
        )
        result = c.execute(command, (self.info.capital, self.info.capital, self.iso))
        return City(db.Geoname(*next(result)))

    @property
    def area(self) -> int:
        return self.info.area

    @property
    def continent(self) -> str:
        return self.info.continent

    @property
    def tld(self) -> str:
        return self.info.tld

    @property
    def currency_code(self) -> str:
        return self.info.currency_code

    @property
    def currency_name(self) -> str:
        return self.info.currency_name

    @property
    def phone(self) -> str:
        return self.info.phone

    @property
    def postal_code_format(self) -> str:
        return self.info.postal_code_format

    @property
    def postal_code_regex(self) -> str:
        return self.info.postal_code_regex

    @property
    def languages(self) -> List[str]:
        return self.info.languages.split(',')

    @property
    def neighbors(self) -> List['Country']:
        return [Country(x) for x in self.info.neighbors.split(',') if x]

    @property
    def equivalent_fips_code(self) -> str:
        return self.info.equivalent_fips_code

    def __repr__(self):
        return 'Country(%r)' % self.country

    def __str__(self):
        return 'Country(%r)' % self.country

    def __contains__(self, item):
        if isinstance(item, (Geoname, db.Geoname)):
            return item.country_code == self.country_code
        elif isinstance(item, str):
            for g in db.select_geonames_name(item):
                if _contains(self.geoname, g):
                    return True
        return False

    def expand(self, abbreviation):
        return expand(abbreviation, country_code=self.iso)

    @property
    def states(self) -> 'Collection':
        return Collection(parent=self, feature_code=self._state_feature_code)

    @property
    def admin1(self) -> 'Collection':
        return Collection(parent=self, feature_code='ADM1')

    @property
    def admin2(self) -> 'Collection':
        return Collection(parent=self, feature_code='ADM2')

    @property
    def admind(self) -> 'Collection':
        return Collection(parent=self, feature_code='ADMD')

    @property
    def cities(self) -> 'Collection':
        return Collection(parent=self, feature_class='P')


COUNTRIES = [Country(i.iso) for i in db.COUNTRYINFO]


class Collection:
    """Represents an abstract collection of places."""
    def __init__(
        self,
        parent: Optional[Geoname],
        feature_class: Optional[str] = None,
        feature_code: Optional[str] = None,
    ) -> None:
        self._parent = parent
        self._feature_class = feature_class
        self._feature_code = feature_code

        self._params = []
        self._cursor = None

        buf = io.StringIO()
        buf.write('SELECT * FROM geoname ')

        def generate_constraints():
            if feature_code:
                yield 'feature_code', feature_code
            if feature_class:
                yield 'feature_class', feature_class
            if self._parent:
                for name, value in _generate_admin_codes(self._parent.geoname):
                    yield name, value

        constraints = list(generate_constraints())
        if constraints:
            field_names, self._params = zip(*constraints)
            buf.write('WHERE ')
            for i, name in enumerate(field_names):
                buf.write('%s = ? ' % name)
                if i != len(field_names) - 1:
                    buf.write('AND ')

        buf.write('ORDER BY population DESC')
        self._command = buf.getvalue()

    def __iter__(self):
        return self

    def __next__(self) -> Union['Geoname', 'State', 'City']:
        if self._cursor is None:
            self._cursor = db.CONN.cursor()
            self._cursor.execute(self._command, self._params)

        result = next(self._cursor)
        return _wrap(db.Geoname(*result))

    def __len__(self):
        cursor = db.CONN.cursor()
        command = self._command.replace('SELECT *', 'SELECT COUNT(*)')
        return cursor.execute(command, self._params)[0]

    def __getitem__(self, key):
        for g in db.select_geonames_name(key):
            if self._parent is None or (self._parent != g and _contains(self._parent, g)):
                return _wrap(g)
        raise KeyError('could not find %r in %r' % (key, self))

    def __contains__(self, other):
        if isinstance(other, str):
            try:
                self[other]
            except KeyError:
                return False
            else:
                return True
        elif isinstance(other, Geoname):
            if not self._parent:
                return True
            return _contains(self._parent, other.geoname)
        elif isinstance(other, db.Geoname):
            if not self._parent:
                return True
            return _contains(self._parent, other)
        return False

    def __repr__(self):
        return 'Collection(%r, %r, %r)' % (
            self._parent,
            self._feature_class,
            self._feature_code,
        )


G = Collection(None)


class State(Geoname):
    def __repr__(self):
        return 'State.gid(%r, %r, %r, %r)' % (
            self.geonameid, self.feature_code, self.name, self.country_code,
        )

    def __str__(self):
        return 'State(%r, %r, %r)' % (self.feature_code, self.name, self.country_code)

    @staticmethod
    def gid(geonames_id, *args, **kwargs):
        return State(db.select_geonames_ids([geonames_id])[0])

    @property
    def cities(self):
        return Collection(parent=self, feature_class='P')


class City(Geoname):
    def __repr__(self):
        return 'City.gid(%r, %r, %r)' % (self.geonameid, self.name, self.country_code)

    def __str__(self):
        return 'City(%r, %r)' % (self.name, self.country_code)

    @staticmethod
    def gid(geonames_id, *args, **kwargs):
        return City(db.select_geonames_ids([geonames_id])[0])


class Postcode:
    #
    # FIXME: implement me
    #
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
    return [State(data) for data in sc_list(name, country)]


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
