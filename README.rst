=======
pygeons
=======

.. image:: https://img.shields.io/pypi/v/pygeons.svg
        :target: https://pypi.python.org/pypi/pygeons

.. image:: https://img.shields.io/travis/mpenkov/pygeons.svg
        :target: https://travis-ci.org/mpenkov/pygeons

.. image:: https://readthedocs.org/projects/pygeons/badge/?version=latest
        :target: https://pygeons.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://pyup.io/repos/github/mpenkov/pygeons/shield.svg
     :target: https://pyup.io/repos/github/mpenkov/pygeons/
     :alt: Updates

Geographical queries made simple.

* Free software: MIT license
* Documentation: https://pygeons.readthedocs.io.

Some examples::

    >>> from pygeons.api import Country, find_cities
    >>> Country('ivory coast')
    Country('Ivory Coast')
    >>> Country('côte d’ivoire')
    Country('Ivory Coast')
    >>> Country('civ')
    Country('Ivory Coast')
    >>> _.iso
    'CI'
    >>> Country('ivory coast').capital.name
    'Yamoussoukro'
    >>> Country('ivory coast').neighbors
    [Country('Liberia'), Country('Ghana'), Country('Guinea'), Country('Burkina Faso'), Country('Mali')]
    >>>
    >>> Country('us').cities['moscow']
    City.gid(5601538, 'Moscow', 'US')
    >>> Country('us').cities['moscow'].admin2
    State.gid(5598264, 'ADM2', 'Latah County', 'US')
    >>> Country('us').cities['moscow'].admin1
    State.gid(5596512, 'ADM1', 'Idaho', 'US')
    >>> Country('us').cities['moscow'].distance_to(Country('ru').cities['moscow'])
    8375.215117486288
    >>>
    >>> find_cities("oslo")[:2]
    [City.gid(3143244, 'Oslo', 'NO'), City.gid(5040425, 'Oslo', 'US')]

Features
--------

* Determine if a (city, state and country) combination corresponds to an existing place name
* Scrub (city, state, country) combinations
* Normalize city, state and country names to their canonical representations
* Frame queries in English as well as languages native to each particular country

Credits
---------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage

