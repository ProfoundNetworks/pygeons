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
[ISO-3166 alpha-1 and alpha-2](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes),
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
They're called different things depending on the country (e.g. territory, province, region, prefecture, etc.), but most countries have such divisions for administrative purposes.

In geonames, there are multiple levels of administrative entities, such as:

    - ADM1
    - ADM2
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

>>> find_cities("oslo")
[City.gid(3143244, 'Oslo', 'NO'), City.gid(5040425, 'Oslo', 'US'), City.gid(4167241, 'Oslo', 'US'), City.gid(5040424, 'Oslo', 'US'), City.gid(6674712, 'Oslo', 'PE')]

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

>>> Country('au').expand('nsw')
'State of New South Wales'
>>> Country('usa').expand('co')
'Colorado'

Pygeons understands names in English and languages local to a particular country:

>>> find_cities('札幌')[0]
City.gid(2128295, 'Sapporo', 'JP')

>>> find_cities('москва', country='ru')[0]
City.gid(524901, 'Moscow', 'RU')

>>> Country('jp').normalize(language='ja')
'日本'

"""

from pygeons import newdb as db

db.connect()

DEFAULT_LANGUAGE = 'en'


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

        if isinstance(item, str):
            #
            # FIXME:
            #
            return False

    def normalize(self, language=DEFAULT_LANGUAGE):
        if language == DEFAULT_LANGUAGE:
            return self.name.lower()
        return self.names_lang[language][0]

    def expand(self, abbreviation):
        return db.expand(abbreviation)

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


class StateCollection:
    def __init__(self, country_code, feature_code):
        self.country_code = country_code
        self.feature_code = feature_code

        self._cursor = db._CONN.cursor()
        command = (
            'SELECT * FROM geoname'
            ' WHERE country_code = ? AND feature_code = ?'
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
        cursor = db._CONN.cursor()
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
        return 'State.gid(%(geonameid)r, %(feature_code)r, %(name)r, %(country_code)r)' % self.data._asdict()

    def __str__(self):
        return 'State(%(feature_code)r, %(name)r, %(country_code)r)' % self.data._asdict()

    def __contains__(self, item):
        if isinstance(item, str):
            #
            # FIXME: abusing the indexed admin1names field here
            #
            return False

    def normalize(self, language=DEFAULT_LANGUAGE):
        return self.names_lang[language][0]

    @property
    def country(self):
        return Country(self.country_code)

    @staticmethod
    def gid(geonames_id, *args, **kwargs):
        c = db._CONN.cursor()
        result = c.execute('SELECT * FROM geoname WHERE geonameid = ?', (geonames_id,))
        return State(db.Geoname(*next(result)))

    @property
    def cities(self):
        return CityCollection(parent=self)


class CityCollection:
    def __init__(self, parent):
        self.parent = parent

        self._cursor = db._CONN.cursor()

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

            self._where = 'country_code = ? AND ? = ? AND feature_class = "P"'
            self._params = (self.parent.country_code, self._admin_field, self._admin_code)

        command = 'SELECT * FROM geoname WHERE ' + self._where
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

    def __contains__(self, key):
        #
        # FIXME:
        #
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

    @property
    def state(self):
        pass

    @property
    def country(self):
        return Country(self.country_code)

    @staticmethod
    def gid(geonames_id, *args, **kwargs):
        c = db._CONN.cursor()
        result = c.execute('SELECT * FROM geoname WHERE geonameid = ?', (geonames_id,))
        return State(db.Geoname(*next(result)))

    def distance_to(self, other):
        # FIXME:
        return -1
        return pygeons._haversine_dist(
            self.latitude, self.longitude,
            other.latitude, other.longitude,
        )


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
    cities = [City(data) for data in db.csc_list(name, state, country)]
    return sorted(cities, key=lambda s: s.population, reverse=True)


def find_states(name, country=None):
    states = [State(data) for data in db.sc_list(name, country)]
    return sorted(states, key=lambda s: s.population, reverse=True)
