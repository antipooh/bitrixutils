import logging
import os
import re
import tempfile
from zipfile import ZipFile

import requests
import sys
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

ACTUAL_VERSION = '3.1'


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


def format_xml(text):
    import xml.dom.minidom
    return xml.dom.minidom.parseString(text).toprettyxml()


# TODO: Extract protocol as strategy class

class Tester:
    headers = {
        'User-Agent': '1C Tester',
        'Accept-Encoding': 'deflate'
    }
    archive_name = 'catalog.zip'
    session_id_regex = re.compile('sessid=([a-z0-9]+)')

    def __init__(self, url, login, password):
        self.url = url
        self.login = login
        self.password = password
        self.session = None
        self.session_id = None
        self.old_protocol = True

    def check_response(self, response):
        self.log_response(response)
        if response.status_code != 200:
            raise TestError(response.text)
        elif response.text.startswith('failure'):
            raise TestError(response.text)

    def import_catalog(self, catalog):
        logger.info(f'Used catalog {catalog}')
        with tempfile.TemporaryDirectory() as tmp_catalog:
            archive_filename = os.path.join(tmp_catalog, self.archive_name)
            data_files = pack_catalog(catalog, archive_filename)
            if len(data_files):
                logger.info(f'Found {len(data_files)} files for import')
                logger.info(f'Communicate with {self.url}')
                self.session = requests.Session()
                self.authorise()
                self.init('catalog')
                self.upload_file(archive_filename)
                for filename in data_files:
                    while self._import(filename):
                        pass
                self.finish()
            else:
                raise TestError('Not found files for import')

    def export_orders(self, old_protocol=False):
        logger.info(f'Communicate with {self.url}')
        self.old_protocol = False
        self.session = requests.Session()
        self.authorise()
        self.init('sale')
        result = self.get_orders()
        print(format_xml(result.text), file=sys.stdout, flush=True)
        self.finish()

    def authorise(self):
        logger.info('Authorisation')
        response = self.session.get(self.url,
                                    params={
                                        'type': 'sale',
                                        'mode': 'checkauth'
                                    },
                                    auth=HTTPBasicAuth(self.login, self.password),
                                    headers=self.headers)
        self.check_response(response)
        if not self.old_protocol:
            match = self.session_id_regex.search(response.text)
            if match:
                self.session_id = match.group(1)
            else:
                raise TestError('Selected new protocol version, but sessid not set')

    def init(self, mode):
        logger.info('Initialize')
        params = {
            'type': mode,
            'mode': 'init'
        }
        params.update(self.get_protocol_parameters())
        response = self.session.get(self.url, params=params, headers=self.headers)
        self.check_response(response)

    def get_protocol_parameters(self):
        if self.old_protocol:
            return {}
        else:
            return {
                'version': ACTUAL_VERSION,
                'sessid': self.session_id
            }

    def upload_file(self, filename):
        logger.info('Load file on server')
        with open(filename, 'rb') as file:
            response = self.session.post(self.url,
                                         params={
                                             'type': 'catalog',
                                             'mode': 'file',
                                             'filename': self.archive_name
                                         },
                                         data=file,
                                         headers=self.headers)
        self.check_response(response)

    def _import(self, filename):
        logger.info(f'Import {filename}')
        response = self.session.get(self.url,
                                    params={
                                        'type': 'catalog',
                                        'mode': 'import',
                                        'filename': filename

                                    },
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
        params = {
            'type': 'sale',
            'mode': 'success'
        }
        params.update(self.get_protocol_parameters())
        response = self.session.get(self.url, params=params, headers=self.headers)
        self.check_response(response)

    def get_orders(self):
        logger.info('Get orders list')
        params = {
            'type': 'sale',
            'mode': 'query'
        }
        params.update(self.get_protocol_parameters())
        response = self.session.get(self.url,
                                    params=params,
                                    headers=self.headers)
        self.check_response(response)
        return response


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
    parser.add_argument('login', type=str, help='Login')
    parser.add_argument('password', type=str, help='Password')
    parser.add_argument('-m', '--mode', type=str, choices=('catalog', 'sale'), default='catalog',
                        help='Test mode')
    parser.add_argument('catalog', type=exists_catalog, nargs='?',
                        help='Catalog with data for import')
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help='Show more information in process')
    parser.add_argument('--old', action='store_true', default=False,
                        help='Use old protocol version')

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    tester = Tester(args.url, args.login, args.password)
    try:
        if args.mode == 'sale':
            tester.export_orders(args.old)
        else:
            tester.import_catalog(args.catalog)
        logger.info('Exchange complete')
    except Exception as e:
        logger.error(e)


if __name__ == '__main__':
    main()
