import argparse
import logging
import os
import os.path as P
import tempfile

from . import download


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
