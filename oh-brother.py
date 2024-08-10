#!/usr/bin/env python3
#
# Oh Brother, Brother printer firmware update program
# Copyright (C) 2015-2023 Cauldron Development LLC
# Author Joseph Coffland
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

from pysnmp.entity.rfc3413.oneliner import cmdgen
import urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import argparse
import sys
import socket
from ftplib import FTP
import ssl
import getpass
from functools import wraps


# Yes indeed, "SELIALNO"
# (as used both in this here document and in script parts below)
# is a spelling issue crime committed by original vendor parts
# and thus expected to remain exactly as wrongly written.
# Thus it obviously should *not* be "corrected" here.
reqInfo = '''
<REQUESTINFO>
  <FIRMUPDATETOOLINFO>
    <FIRMCATEGORY></FIRMCATEGORY>
    <OS>LINUX</OS>
    <INSPECTMODE>1</INSPECTMODE>
  </FIRMUPDATETOOLINFO>
  <FIRMUPDATEINFO>
    <MODELINFO>
      <SELIALNO></SELIALNO>
      <NAME></NAME>
      <SPEC></SPEC>
      <DRIVER>EWS</DRIVER>
      <FIRMINFO>
        <FIRM></FIRM>
      </FIRMINFO>
    </MODELINFO>
    <DRIVERCNT>1</DRIVERCNT>
    <LOGNO>2</LOGNO>
    <ERRBIT></ERRBIT>
    <NEEDRESPONSE>1</NEEDRESPONSE>
  </FIRMUPDATEINFO>
</REQUESTINFO>
'''

# Parse args
usage = '%(prog)s [OPTIONS] <printer IP address>'
description = 'A platform independent tool for updating Brother firmwares'

parser = argparse.ArgumentParser(usage = usage, description = description)

parser.add_argument('ip', metavar = 'IP', help = 'printer IP address')
parser.add_argument('-v', '--verbose', action = 'store_true',
                    help = 'Verbose output')
parser.add_argument('-c', '--category',
                    help = 'Force a specific firmware category')
parser.add_argument('-m', '--model',
                    help = 'Force a specific printer model')
parser.add_argument('-C', '--community', default = 'public',
                    help = 'SNMP community (default: %(default)s)')
parser.add_argument('-f', '--version', default = 'B0000000000',
                    help = 'Force a specific firmware version, must be used '
                    'with --category')
parser.add_argument('-t', '--test', action = 'store_true',
                    help = 'Test only, don\'t do upgrades')
parser.add_argument('-p', '--password',
                    help = 'Upload firmware via FTP using printer admin password '
                    '(default is passwordless upload via TCP port 9100)')

args = parser.parse_args()

# Provide information about requirements
print('You may need to check the following in the printer\'s configuration:')
print('  - SNMP service is enabled (for fetching model and versions)')
if args.password:
  print('  - FTP service is enabled (for uploading firmware)')
  print('  - an administrator password is set (for connecting to FTP)')
input('Press Ctrl-C to exit or Enter to continue...')

# Get SNMP data
print('Getting SNMP data from printer at %s...' % args.ip)
sys.stdout.flush()

cg = cmdgen.CommandGenerator()
error, status, index, table = cg.nextCmd(
  cmdgen.CommunityData(args.community),
  cmdgen.UdpTransportTarget((args.ip, 161)),
  '1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2')

print('done')

if error: raise Exception(error)
if status:
  raise Exception('ERROR: %s at %s' % (
    status.prettyPrint(), index and table[-1][int(index) - 1] or '?'))

# Process SNMP data
serial   = None
model    = None
spec     = None
firmId   = None
firmInfo = []

if args.verbose: print(table)

for row in table:
  for name, value in row:
    value = str(value)

    if value.find('=') != -1:
      name, value = value.split('=')
      value = value.strip(' "\r\n')

      if name == 'MODEL':  model  = value
      if name == 'SERIAL': serial = value
      if name == 'SPEC':   spec   = value
      if name == 'FIRMID': firmId = value
      if name == 'FIRMVER' and firmId and value:
        firmInfo.append({'cat': firmId, 'version': value})

# Override model
if args.model: model = args.model

# Override category and version
if args.category:
  firmInfo = [{'cat': args.category, 'version': args.version}]

# Print SNMP info
print()
print('    serial =', serial)
print('     model =', model)
print('      spec =', spec)
print('   firmwares')

for entry in firmInfo:
  print('    category = %(cat)s, version = %(version)s' % entry)

print()


# We need SSLv3
def sslwrap(func):
  @wraps(func)
  def bar(*args, **kw):
    kw['ssl_version'] = ssl.PROTOCOL_TLS_CLIENT
    return func(*args, **kw)

  return bar

context = ssl.create_default_context()
ssl.wrap_socket = sslwrap(context.wrap_socket)


def update_firmware(cat, version):
  global args

  print('Updating %s version %s' % (cat, version))

  # Build XML request info
  xml = ET.ElementTree(ET.fromstring(reqInfo))

  # At least for MFC-J4510DW M1405200717:EFAC (see Internet dumps)
  # and MFC-J4625DW, and MFC-J4420DW
  # this element's value is *not* equal to per-firmware cat[egory] value
  # (a "MAIN"-deviating "FIRM" in these cases!),
  # but rather a *fixed* "MAIN" value which is a completely unrelated item.
  #
  # According to verCheck response, FIRMCATEGORY should be MAIN when FIRM/ID
  # equals FIRM
  #  From response dump:
  #     <ID>FIRM</ID> <NAME>MAIN</NAME>
  #

  e = xml.find('FIRMUPDATETOOLINFO/FIRMCATEGORY')
  e.text = cat if cat != 'FIRM' else 'MAIN'

  modelInfo = xml.find('FIRMUPDATEINFO/MODELINFO')
  modelInfo.find('SELIALNO').text = serial
  modelInfo.find('NAME').text = model
  modelInfo.find('SPEC').text = spec

  firm = modelInfo.find('FIRMINFO/FIRM')
  ET.SubElement(firm, 'ID').text = cat if cat != 'IFAX' else 'MAIN'
  ET.SubElement(firm, 'VERSION').text = version

  requestInfo = ET.tostring(xml.getroot(), encoding = 'utf8')

  if args.verbose: print('request: %s' % requestInfo)

  # Request firmware data
  url = 'https://firmverup.brother.co.jp/'
  url += 'kne_bh7_update_nt_ssl/ifax2.asmx/fileUpdate'
  hdrs = {'Content-Type': 'text/xml'}

  print('Looking up printer firmware info at vendor server...')
  sys.stdout.flush()

  req = urllib.request.Request(url, requestInfo, hdrs)
  response = urllib.request.urlopen(req)
  response = response.read()

  print('done')

  if args.verbose: print('response: %s' % response)

  # Parse response
  xml = ET.fromstring(response)

  # Check version
  versionCheck = xml.find('FIRMUPDATEINFO/VERSIONCHECK')
  if versionCheck is not None and versionCheck.text == '1':
    print('Firmware already up to date')
    return

  # Get firmware URL
  firmwareURL = xml.find('FIRMUPDATEINFO/PATH')
  if firmwareURL is None:
    print('No firmware update info path found')
    return

  firmwareURL = firmwareURL.text
  filename = firmwareURL.split('/')[-1]

  # Download firmware
  f = open(filename, 'wb')

  print('Downloading firmware file %s from vendor server...' % filename)
  sys.stdout.flush()

  req = urllib.request.Request(firmwareURL)
  response = urllib.request.urlopen(req)

  while True:
    block = response.read(102400)
    if not block: break
    f.write(block)
    sys.stdout.write('.')
    sys.stdout.flush()

  print('done')
  f.close()

  if args.test: return

  print('About to upload the firmware to printer.')
  print('This is a dangerous action since it is potentially destructive.')
  print('Thus please double-check / review to ensure that:')
  print('- firmware file version is compatible with your hardware')
  print('- network connection is reliable (prefer wired connection to WLAN)')
  print('- power is reliable')
  input('Press Ctrl-C to prevent upgrade or Enter to continue...')

  # Upload firmware to printer
  print('Now uploading firmware to printer (DO NOT REMOVE POWER!)...')
  sys.stdout.flush()

  if args.password is None:
    ai = socket.getaddrinfo(args.ip, 9100, proto=socket.SOL_TCP)[0]
    try:
      with socket.socket(ai[0], ai[1], ai[2]) as sock:
        sock.connect(ai[4])
        sock.sendfile(open(filename, 'rb'))

    except OSError as e:
      print('Firmware update aborted due to error while uploading')
      print(e)
  else:
    try:
      ftp = FTP(args.ip, user = args.password) # Yes send password as user
      ftp.storbinary('STOR ' + filename, open(filename, 'rb'))
      ftp.quit()
    except ConnectionRefusedError as e:
      print('Firmware update aborted due to connection refused')

  print('done')
  print()
  print('Wait for printer to finish updating and reboot before continuing.')
  input('Press Enter to continue...')

for entry in firmInfo:
  print()
  update_firmware(entry['cat'], entry['version'])

print()
print('Success')
