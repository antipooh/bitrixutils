Bitrix import utils
===============================

version number: 0.0.1
author: Oleg Komkov

Overview
--------

Set utils for testing [exchange with 1C and Bitrix](http://v8.1c.ru/edi/edi_stnd/131/).

Installation
------------
Python 3.6 and above only.

To install use pip:

    $ pip install bitrixutils


Or clone the repo:

    $ git clone https://github.com/antipooh/bitrixutils.git
    $ python setup.py install


Usage
-------

    $ bitrix_exchange -h

    usage: bitrix_exchange [-h] [-v] url catalog login password

    Test import catalog to 1C Bitrix.

    positional arguments:
      url            Import url, can be site url or full url to import script
      catalog        Catalog with data for import
      login          Login
      password       Password

    optional arguments:
      -h, --help     show this help message and exit
      -v, --verbose  Show more information in process



    $ bitrix_hash <password>
    create bitrix hash for password, insert this in table b_user