import argparse
import re
import os
import sys
import datetime
import time
import logging
import fnmatch
import dropbox

# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('dir', help='remote folder to scan')
parser.add_argument('-a', '--auth', dest='auth', action='store',
    required = True, help = 'Dropbox auth code')
parser.add_argument('-k', '--keep', dest='days', action='store', metavar='N',
    default = 3, type = int, help = 'keep files modified in recent N days (UTC date)')
parser.add_argument('-l', '--loglevel', dest='loglevel', action='store', metavar='L',
    default = "info", help = 'specify log level, defalt to INFO')

args = parser.parse_args()

# debug only, for argparse test
# print args
# sys.exit()

# config logging
log_levels = {
    "info": logging.INFO,
    "debug": logging.DEBUG,
    "error": logging.ERROR,
    "warning": logging.WARN,
    "warn": logging.WARN
}

FORMAT = "%(asctime)s %(name)s %(levelname)s: %(message)s"
logging.basicConfig(format=FORMAT,
    datefmt = '%Y-%m-%dT%H:%M:%S',
    level = log_levels[args.loglevel.lower()], filename = '%s/log/dbx-purge.log'%(os.path.expanduser('~')))

logging.info('== START')

date_threshhold = datetime.datetime.utcnow().date() - datetime.timedelta(days = args.days)
logging.debug('date_threshhold: %s', date_threshhold)

def purge_folder(dbx, folder, subfolder):
    """List a folder.
    Return a dict mapping unicode filenames to
    FileMetadata|FolderMetadata entries.
    """
    path = '/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'))
    while '//' in path:
        path = path.replace('//', '/')
    path = path.rstrip('/')

    try:
        res = dbx.files_list_folder(path)
    except dropbox.exceptions.ApiError as err:
        logging.error('Folder listing failed for %s\n%s', path, err)
        return (True)
    else:
        is_empty = True
        for entry in res.entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                if entry.client_modified.date() < date_threshhold:
                    path_to_delete = '%s/%s' % (path, entry.name)
                    logging.debug('deleting %s', path_to_delete)
                    dbx.files_delete(path_to_delete)
                else:
                    logging.debug('Old file %s: %s >= %s', entry.name, entry.client_modified, date_threshhold)
                    is_empty = False

            elif isinstance(entry, dropbox.files.FolderMetadata):
                (is_child_empty) = purge_folder(dbx, path, entry.name)
                if is_child_empty:
                    path_to_delete = '%s/%s' % (path, entry.name)
                    logging.debug('deleting folder %s', path_to_delete)
                    dbx.files_delete(path_to_delete)
                else:
                    is_empty = False

        return (is_empty)

# get auth token
if args.auth.startswith('@'):
    # read the auth token from the file
    with open(os.path.expanduser(args.auth[1:]), 'r') as f:
        auth_token = f.readline().rstrip()
else:
    auth_token = args.auth

dbx = dropbox.Dropbox(auth_token)

purge_folder(dbx, args.dir, '')

