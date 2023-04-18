#!/usr/bin/env python3
""" neocities api client library and cli """

import os
import json
import http.client
import getpass
import base64
import pathlib
import mimetypes
import argparse

def decor_return(func):
    """ common decorator for Neocities API get and post methods """
    def result(self, args):
        func(self, args)
        self.res = json.load(self.https.getresponse())
        return self.res
    return result

class NeocitiesAPI:
    """ neocities client api implementation """
    ALLOWED = [ # file suffixes / types
        '.txt', '.text', '.csv', '.tsv', '.md', '.markdown',
        '.html', '.htm', '.css', '.js', '.json', '.geojson', '.xml',
        '.svg', '.jpg', '.png', '.gif', '.ico', '.mid', '.midi',
        '.eot', '.ttf', '.woff', '.woff2', ]

    def __init__(self, key_filename):
        # MAYBE: allow choosing between Basic and Bearer auth
        self.https = http.client.HTTPSConnection('neocities.org')
        try:
            self.res = json.load(open(key_filename))
        except FileNotFoundError:
            self.get_key()
            if self.res['result'] != 'success':
                raise
            json.dump(self.res, open(key_filename, 'w'))
            os.chmod(key_filename, 0o600)
        self.api_key = self.res['api_key']
        self.auth = {'Authorization' : 'Bearer ' + self.api_key}

    @decor_return
    def get_key(self, user=getpass.getuser(), passwd=getpass.getpass()):
        """ request api key """
        login = bytes(user + ':' + passwd, 'utf-8')

        self.https.request('GET', '/api/key', None, {
            'Authorization': 'Basic ' + base64.b64encode(login).decode('ascii')})

    @decor_return
    def get_list(self, path=None):
        """ request file listing,
        a path may be supplied, defaults to all """
        self.https.request('GET', '/api/list' +
                           ('?path=' + path if path else ''), None, self.auth)

    @decor_return
    def get_info(self, sitename=None):
        """ request site information,
        a specific sitename may be supplied, defaults to own site """
        self.https.request('GET', '/api/info' +
                           ('?sitename=' + sitename if sitename else ''), None, self.auth)

    @decor_return
    def post_delete(self, filenames):
        """ delete of one or more filenames """
        self.https.request('POST', '/api/delete',
                           '&'.join(['filenames[]=' + name for name in filenames]), self.auth)

    @decor_return
    def post_upload(self, files, boundary=None):
        """ upload one or more files using multipart/form-data, ugh... """
        if not boundary:
            boundary = self.api_key

        def multipart_form_data():
            begin_disposition = bytes('\r\n--%s\r\n' % boundary, 'utf-8')
            disposition_fmt = (
                'Content-Disposition: form-data; name="%s"; filename="%s"\r\n' +
                'Content-Type: %s\r\n\r\n')

            end_multipart = bytes('\r\n--%s--\r\n' % boundary, 'utf-8')

            for filename, name in files:
                if pathlib.Path(filename).suffix not in self.ALLOWED:
                    print(filename, 'suffix not allowed, file ignored.')
                    continue

                mime, encoding = mimetypes.guess_type(filename)

                yield (
                    begin_disposition +
                    bytes(disposition_fmt % (
                        name, pathlib.Path(filename).name,
                        mime if mime else 'application/octet-stream')) +
                    open(filename, 'rb', -1, encoding).read())
            yield end_multipart

        self.https.request('POST', '/api/upload', multipart_form_data(), {
            **self.auth, 'Content-Type': 'multipart/form-data; boundary=' + boundary})

if __name__ == "__main__": # commandline usage
    NC = NeocitiesAPI(os.environ['HOME'] + '/.neocities_key.json')

    AP = argparse.ArgumentParser()
    SUB = AP.add_subparsers()

    def subparser(cmd, arg, *, nargs=None, const=None, typ=None, metavar=None, func=None):
        """ shorthand wrapper for adding (sub)commands """
        tmp = SUB.add_parser(cmd)
        tmp.add_argument(arg, nargs=nargs, const=const, type=typ, metavar=metavar)
        tmp.set_defaults(func=func)

    def upload_tuple(arg):
        """ parse commandline argument string to tuple """
        filename, _, name = arg.partition(',')
        return (filename, name if name else filename)

    subparser('list', 'path', nargs='?', const='',
              func=lambda args: NC.get_list(args.path))
    subparser('info', 'sitename', nargs='?', const='',
              func=lambda args: NC.get_info(args.sitename))
    subparser('delete', 'filenames', nargs='+',
              func=lambda args: NC.post_delete(args.filenames))
    subparser('upload', 'files', nargs='+', typ=upload_tuple,
              func=lambda args: NC.post_upload(args.files))

    PA = AP.parse_args()
    if 'func' in PA:
        RES = PA.func(PA)
        print('\033[31m' if 'error_type' in RES else '\033[32m',
              json.dumps(RES, indent='\t'),
              '\033[0m', sep='\n')
