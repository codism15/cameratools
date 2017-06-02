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
parser.add_argument('file', help='file to be uploaded')
parser.add_argument('-a', '--auth', dest='auth', action='store',
    required = True, help = 'Dropbox auth code')
parser.add_argument('-d', '--dir', dest='baseDir', action='store', metavar='Dir',
    help = 'local base directory, used to derive the server path')
parser.add_argument('-f', '--remoteFolder', dest='remoteFolder', action='store', metavar='F',
    help = 'remote folder')
parser.add_argument('-r', '--replace', dest='replace', action='append',
    metavar=('regex', 'str'), nargs = 2, help = 'replace part of the path')

args = parser.parse_args()

# debug only, for argparse test
# print args
# sys.exit()

# config logging
FORMAT = "%(asctime)s %(name)s %(levelname)s: %(message)s"
logging.basicConfig(format=FORMAT,
    datefmt = '%Y-%m-%dT%H:%M:%S',
    level = logging.INFO, filename = '%s/log/dbx-upload.log'%(os.path.expanduser('~')))

logging.info('== START')

# validate the file must start with base dir
file_abspath = os.path.abspath(args.file)
base_abspath = os.path.abspath(args.baseDir)

if not file_abspath.startswith(base_abspath):
    sys.exit('file [%s] is not in base dir [%s]' % (file_abspath, base_abspath))

# get the file relative path to the base
file_relative_path = file_abspath[len(base_abspath):]

# test to see if replace pattern needs to be processed
if args.replace is not None:
    new_path = file_relative_path
    for pat, str in args.replace:
        new_path = re.sub(pat, str, new_path)
    
    if new_path != file_relative_path:
        logging.info('transalted file name %s -> %s', file_relative_path, new_path)
        file_relative_path = new_path

# get server path
remote_folder = '' if args.remoteFolder is None else args.remoteFolder

if remote_folder.endswith('/') or remote_folder.endswith('\\'):
    remote_folder = remote_folder[:-1]

if remote_folder.startswith('/') or remote_folder.startswith('\\'):
    remote_folder = remote_folder[1:]

file_server_path = (('/' + remote_folder + file_relative_path)
    .replace('\\', '/')
    .replace('//', '/'))

logging.info('uploading %s to %s', os.path.basename(file_abspath), file_server_path)

# get auth token
if args.auth.startswith('@'):
    # read the auth token from the file
    with open(args.auth[1:], 'r') as f:
        auth_token = f.readline().rstrip()
else:
    auth_token = args.auth

# upload the file
mtime = os.path.getmtime(file_abspath)

with open(file_abspath, 'rb') as f:
    data = f.read()

try:
    dbx = dropbox.Dropbox(auth_token)
    res = dbx.files_upload(data, file_server_path,
        dropbox.files.WriteMode.add,
        client_modified=datetime.datetime(*time.gmtime(mtime)[:6]),
        mute=True)
    # print('uploaded as', res.name.encode('utf8'))
except dropbox.exceptions.ApiError as err:
    logging.error('Error when upload %s\n%s', os.path.basename(file_abspath), err)
    raise

logging.info('== END')