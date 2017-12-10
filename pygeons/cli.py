#
# -*- coding: utf-8 -*-
# (C) Copyright: Profound Networks, LLC 2016
#
import argparse
import json
import logging
import os
import os.path as P
import tempfile

from . import download
from . import derive
from . import process


def _download_subparser(subparsers):
    cmd = 'download'
    desc = 'Download files from the GeoNames.org server'
    epilog = 'Prints the subdirectory to standard output'
    parser = subparsers.add_parser(cmd, help='%s --help' % cmd, description=desc, epilog=epilog)
    parser.add_argument('--subdir', help='The temporary directory to store files in')
    parser.set_defaults(function=_download)


def _download(args):
    tmp_dir = args.subdir if args.subdir else tempfile.mkdtemp(prefix='pygeons')
    if not P.isdir(tmp_dir):
        os.makedirs(tmp_dir)

    download.download(tmp_dir)
    print(P.abspath(tmp_dir))


def _process_subparser(subparsers):
    cmd = 'process'
    desc = 'Process files in preparation for inserting into the DB'
    epilog = ''
    parser = subparsers.add_parser(cmd, help='%s --help' % cmd, description=desc, epilog=epilog)
    parser.add_argument('subdir', help='The temporary directory where downloaded files are')
    parser.set_defaults(function=_process)


def _process(args):
    process.process(args.subdir)


def _register_function(subparsers, function):

    def wrapper(args):
        fun_args = json.loads(args.args) if args.args else {}
        fun_kwargs = json.loads(args.kwargs) if args.kwargs else {}
        function(*fun_args, **fun_kwargs)

    cmd = function.__name__
    desc = 'Calls the internal %r function with the specified arguments' % function.__name__
    epilog = ''
    parser = subparsers.add_parser(cmd, help='%s --help' % cmd, description=desc, epilog=epilog)
    parser.add_argument('--subdir', help='The temporary directory to store files in')
    parser.add_argument('--args', help='A JSON list')
    parser.add_argument('--kwargs', help='A JSON dictionary')
    parser.set_defaults(function=wrapper)


def _create_top_parser():
    desc = 'Command-line interface to the pygeons project'
    epilog = ''
    parser = argparse.ArgumentParser(
        description=desc, epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--loglevel', default=logging.INFO)
    subparsers = parser.add_subparsers(help='sub-command --help')
    constructors = tuple(v for (k, v) in sorted(globals().items()) if k.endswith('_subparser'))
    for func in constructors:
        func(subparsers)
    _register_function(subparsers, process.tsv2json)
    _register_function(subparsers, process.append_alt_names)
    _register_function(subparsers, process.append_admin_names)
    _register_function(subparsers, derive.derive)
    return parser


def main():
    parser = _create_top_parser()
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)
    logging.debug('args: %r', args)
    try:
        function = args.function
    except AttributeError:
        parser.error('try --help')
    else:
        function(args)


if __name__ == '__main__':
    main()
