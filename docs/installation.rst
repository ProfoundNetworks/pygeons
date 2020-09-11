.. highlight:: shell

============
Installation
============


Stable release
--------------

To install pygeons, run this command in your terminal:

.. code-block:: console

    $ pip install pygeons

This is the preferred method to install pygeons, as it will always install the most recent stable release.

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


From sources
------------

The sources for pygeons can be downloaded from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone git://github.com/mpenkov/pygeons

Or download the `tarball`_:

.. code-block:: console

    $ curl  -OL https://github.com/mpenkov/pygeons/tarball/master

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ python setup.py install


.. _Github repo: https://github.com/mpenkov/pygeons
.. _tarball: https://github.com/mpenkov/pygeons/tarball/master

Populating the Database
-----------------------

Pygeons requires data from GeoNames.org_.
This data is free for sharing and adaptations as long as you abide by the `GeoNames license`_.

Pygeons includes scripts that download and import the data into a local sqlite3 DB.
To download the data, run::

    python -m pygeons.initialize

This will download approx. 500MB of data from geonames.org.
Once the data is imported, the database will live under ``.pygeons`` in your home directory.
Use the ``PYGEONS_HOME`` environment variable to modify this behavior.
The data takes several GB, so make sure you have enough space.

.. _GeoNames.org: http://www.geonames.org
.. _GeoNames license: https://creativecommons.org/licenses/by/4.0/
