#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'marisa_trie',
    'pySmartDL',
    'pyyaml',
    'smart_open',
]

setup_requirements = [
    'pytest-runner',
    # TODO(mpenkov): put setup requirements (distutils extensions, etc.) here
]

test_requirements = [
    'pytest',
    'parameterizedtestcase',
    'mock',
    'nose',
    # TODO: put package test requirements here
]

setup(
    name='pygeons',
    version='0.9.0',
    description="Geographical queries made easy.",
    long_description=readme + '\n\n' + history,
    author="Michael Penkov",
    author_email='m@penkov.dev',
    url='https://github.com/ProfoundNetworks/pygeons',
    packages=find_packages(include=['pygeons']),
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords='pygeons',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    test_suite='tests',
    tests_require=test_requirements,
    setup_requires=setup_requirements,
)
