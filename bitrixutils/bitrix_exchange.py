import logging
import os
import tempfile
from zipfile import ZipFile

import requests
import sys
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class TestError(Exception): pass


def pack_catalog(catalog, zip_filename):
    files = []
    with ZipFile(zip_filename, 'w') as zip:
        for base, dirs, filenames in os.walk(catalog):
            for filename in filenames:
                abs_filename = os.path.join(base, filename)
                rel_filename = os.path.relpath(abs_filename, catalog)
                if os.path.splitext(filename)[-1] == '.xml':
                    files.append(rel_filename)
                zip.write(abs_filename, rel_filename)
    return files


def sort(files):
    ls = []
    for name in files:
        key = os.path.split(name)[-1].split('_')[0]
        weight = {
            'import': 1,
            'offers': 2,
            'rests': 3,
            'prices': 4
        }.get(key)
        if weight:
            ls.append((weight, name))
    return [it[1] for it in sorted(ls, key=lambda x: x[0])]


class Tester:
    headers = {
        'User-Agent': '1C Tester',
        'Accept-Encoding': 'deflate'
    }
    archive_name = 'catalog.zip'

    def __init__(self, url, login, password, catalog):
        self.catalog = catalog
        self.url = url
        self.login = login
        self.password = password
        self.session = None

    def check_response(self, response):
        self.log_response(response)
        if response.status_code != 200:
            raise TestError(response.text)

    def process(self):
        logger.info(f'Used catalog {self.catalog}')
        with tempfile.TemporaryDirectory() as tmp_catalog:
            filename = os.path.join(tmp_catalog, self.archive_name)
            data_files = pack_catalog(self.catalog, filename)
            if len(data_files):
                logger.info(f'Found {len(data_files)} files for import')
                self.communicate(filename, data_files)
            else:
                raise TestError('Not found files for import')

    def communicate(self, archive, data_files):
        logger.info(f'Communicate with {self.url}')
        self.session = requests.Session()
        self.check_auth()
        self.init()
        self.load_file(archive)
        for filename in data_files:
            while self.import_(filename):
                pass
        self.finish()

    def check_auth(self):
        logger.info('Authorisation')
        response = self.session.get(f'{self.url}?type=sale&mode=checkauth',
                                    auth=HTTPBasicAuth(self.login, self.password),
                                    headers=self.headers)
        self.check_response(response)

    def init(self):
        logger.info('Initialize')
        response = self.session.get(f'{self.url}?type=catalog&mode=init', headers=self.headers)
        self.check_response(response)

    def load_file(self, filename):
        logger.info('Load file on server')
        with open(filename, 'rb') as file:
            response = self.session.post(f'{self.url}?type=catalog&mode=file&filename={self.archive_name}',
                                         data=file,
                                         headers=self.headers)
        self.check_response(response)

    def import_(self, filename):
        logger.info(f'Import {filename}')
        response = self.session.get(f'{self.url}?type=catalog&mode=import&filename={filename}',
                                    headers=self.headers)
        self.check_response(response)
        return response.text.startswith('progress')

    def log_response(self, response):
        if response.text:
            ls = response.text.split('\n')
            if len(ls) > 1:
                logger.debug(ls[0])
                logger.info(ls[-1])
            else:
                logger.info(response.text)

    def finish(self):
        logger.info('Finalize')
        response = self.session.get(f'{self.url}?type=sale&mode=success', headers=self.headers)
        self.check_response(response)


DEFAULT_SCHEMA = 'http'
DEFAULT_PATH = '/bitrix/admin/1c_exchange.php'


def main(argv=sys.argv):
    import argparse
    from urllib.parse import urlparse, urlunparse

    def import_url(value):
        url = urlparse(value)
        scheme = url.scheme or DEFAULT_SCHEMA
        if url.netloc:
            netloc = url.netloc
            path = url.path or DEFAULT_PATH
        else:
            if url.path:
                netloc = url.path
                path = DEFAULT_PATH
            else:
                raise argparse.ArgumentTypeError(f'<{value}> is not properly url')
        return urlunparse((scheme, netloc, path, None, None, None))

    def exists_catalog(value):
        catalog = os.path.abspath(os.path.expanduser(value))
        if os.path.isdir(catalog):
            return catalog
        else:
            raise argparse.ArgumentTypeError(f'[{catalog}] is not catalog')

    parser = argparse.ArgumentParser(description='Test import catalog to 1C Bitrix.')
    parser.add_argument('url', type=import_url, help='Import url, can be site url or full url to import script')
    parser.add_argument('catalog', type=exists_catalog, help='Catalog with data for import')
    parser.add_argument('login', type=str, help='Login')
    parser.add_argument('password', type=str, help='Password')
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help='Show more information in process')

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    tester = Tester(args.url, args.login, args.password, args.catalog)
    try:
        tester.process()
        logger.info('Exchange complete')
    except Exception as e:
        logger.error(e)

if __name__ == '__main__':
    main()
