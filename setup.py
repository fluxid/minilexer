from setuptools import setup, find_packages
import sys

if sys.version_info < (3,):
    print('Sorry, this package is developed for Python 3')
    exit(1)

setup(
    name = 'fxd.minilexer',
    version = '0.1',
    package_dir = {
        '': 'src',
    },
    namespace_packages = (
        'fxd',
    ),
    packages = find_packages('src'),
    author = 'Tomasz Kowalczyk',
    author_email = 'myself@fluxid.pl',
    description = 'Simple lexer',
    keywords = 'lexer parser',
)
