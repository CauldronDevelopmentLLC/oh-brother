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
    <OS>WIN_NATIVE</OS>
    <INSPECTMODE></INSPECTMODE>
  </FIRMUPDATETOOLINFO>
  <FIRMUPDATEINFO>
    <MODELINFO>
      <NAME></NAME>
      <SPEC></SPEC>
      <DRIVER>EWS</DRIVER>
      <FIRMINFO>
        <FIRM></FIRM>
      </FIRMINFO>
    </MODELINFO>
    <DRIVERCNT>1</DRIVERCNT>
    <LOGNO>2</LOGNO>
    <NEEDRESPONSE>1</NEEDRESPONSE>
  </FIRMUPDATEINFO>
</REQUESTINFO>
'''


def parse_snmp_table(table, verbose=False):
    """Parse SNMP walk result table into model/serial/spec/firmware info.
    
    table: list of list of (name, value) tuples from cmdgen.nextCmd()
    Returns: dict with keys: serial, model, spec, firmwares (list of {cat, version})
    """
    if verbose:
        print(table)
    
    serial = None
    model = None
    spec = None
    firmId = None
    firmwares = []
    
    for row in table:
        for name, value in row:
            value = str(value)
            if value.find('=') != -1:
                name, value = value.split('=')
                value = value.strip(' "\r\n')
                if name == 'MODEL':
                    model = value
                if name == 'SERIAL':
                    serial = value
                if name == 'SPEC':
                    spec = value
                if name == 'FIRMID':
                    firmId = value
                if name == 'FIRMVER' and firmId and value:
                    firmwares.append({'cat': firmId, 'version': value})
    
    return {'serial': serial, 'model': model, 'spec': spec, 'firmwares': firmwares}


def build_firmware_xml(model, spec, category, version, beta=False):
    """Build the XML request body for Brother's firmware update API.
    
    Returns: bytes (UTF-8 encoded XML)
    """
    import xml.etree.ElementTree as ET
    # Use the module-level reqInfo template
    xml = ET.ElementTree(ET.fromstring(reqInfo))
    
    toolInfo = xml.find('FIRMUPDATETOOLINFO')
    toolInfo.find('FIRMCATEGORY').text = category if category != 'FIRM' else 'MAIN'
    toolInfo.find('INSPECTMODE').text = '1' if beta else '0'
    
    modelInfo = xml.find('FIRMUPDATEINFO/MODELINFO')
    modelInfo.find('NAME').text = model
    modelInfo.find('SPEC').text = spec
    
    firm = modelInfo.find('FIRMINFO/FIRM')
    ET.SubElement(firm, 'ID').text = category if category != 'IFAX' else 'MAIN'
    ET.SubElement(firm, 'VERSION').text = version
    
    return ET.tostring(xml.getroot(), encoding='utf8')


def parse_brother_response(xml_bytes):
    """Parse Brother firmware API XML response.
    
    Returns: dict with keys:
        version_check: str or None — '1' means up to date
        firmware_url: str or None — download URL if update available
    """
    import xml.etree.ElementTree as ET
    
    xml = ET.fromstring(xml_bytes)
    
    version_check = xml.find('FIRMUPDATEINFO/VERSIONCHECK')
    version_check = version_check.text if version_check is not None else None
    
    firmware_url = xml.find('FIRMUPDATEINFO/PATH')
    firmware_url = firmware_url.text if firmware_url is not None else None
    
    return {'version_check': version_check, 'firmware_url': firmware_url}

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
parser.add_argument('--beta', action = 'store_true',
                    help = 'Download the latest beta firmware instead of the '
                    'default stable version.')
parser.add_argument('-p', '--password',
                    help = 'Upload firmware via FTP using printer admin password '
                    '(default is passwordless upload via TCP port 9100)')
parser.add_argument('-y', '--yes', action = 'store_true',
                    help = 'Skip all confirmation prompts (non-interactive mode)')


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

  requestInfo = build_firmware_xml(model, spec, cat, version, beta=args.beta)

  if args.verbose: print('request: %s' % requestInfo)

  # Request firmware data
  url = 'https://firmverup.brother.co.jp/'
  url += 'kne_bh7_update_nt_ssl/ifax2.asmx/fileUpdate'
  hdrs = {'Content-Type': 'text/xml', 'User-Agent': 'BrHttpc/1.00'}

  print('Looking up printer firmware info at vendor server...')
  sys.stdout.flush()

  req = urllib.request.Request(url, requestInfo, hdrs)
  response = urllib.request.urlopen(req)
  response = response.read()

  print('done')

  if args.verbose: print('response: %s' % response)

  result = parse_brother_response(response)
  if result['version_check'] == '1':
    print('Firmware already up to date')
    return
  if result['firmware_url'] is None:
    print('No firmware update info path found')
    return
  firmwareURL = result['firmware_url']
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
  if not args.yes:
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
  if not args.yes:
    input('Press Enter to continue...')


def main():
    global args, serial, model, spec, firmInfo
    args = parser.parse_args()

    # Provide information about requirements
    print('You may need to check the following in the printer\'s configuration:')
    print('  - SNMP service is enabled (for fetching model and versions)')
    if args.password:
      print('  - FTP service is enabled (for uploading firmware)')
      print('  - an administrator password is set (for connecting to FTP)')
    if not args.yes:
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
    info = parse_snmp_table(table, verbose=args.verbose)
    serial = info['serial']
    model = info['model']
    spec = info['spec']
    firmInfo = info['firmwares']

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

    for entry in firmInfo:
      print()
      update_firmware(entry['cat'], entry['version'])

    print()
    print('Success')


if __name__ == '__main__':
    main()
