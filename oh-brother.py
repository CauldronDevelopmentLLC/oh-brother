#!/usr/bin/env python
#
# Oh Brother, Brother printer firmware update program
# Copyright (C) 2015 Cauldron Development LLC
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
            <DRIVER></DRIVER>
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

password = None
verbose = False

from pysnmp.entity.rfc3413.oneliner import cmdgen
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import sys


def print_pretty(elem):
    s = ET.tostring(elem, 'utf-8')
    print minidom.parseString(s).toprettyxml(indent = ' ')


# Parse args
if len(sys.argv) < 2:
  print 'Usage: %s [OPTIONS] <printer IP address>' % sys.argv[0]
  print
  print 'Options:'
  print '  -v          Verbose mode'
  sys.exit(1)

for arg in sys.argv[1:]:
  if arg == '-v': verbose = True
  else: ip = arg


# Get SMNP data
print 'Getting SNMP data from printer at %s...' % ip,
sys.stdout.flush()

cg = cmdgen.CommandGenerator()
error, status, index, table = cg.nextCmd(
    cmdgen.CommunityData('public'),
    cmdgen.UdpTransportTarget((ip, 161)),
    '1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2')

print 'done'

if error: raise error
if status:
    raise 'ERROR: %s at %s' % (status.prettyPrint(),
                        index and table[-1][int(index) - 1] or '?')


# Process SNMP data
serial = None
model = None
spec = None
firmId = None
firmInfo = []

if verbose: print table

for row in table:
    for name, value in row:
        value = value.prettyPrint()

        if value.find('=') != -1:
            name, value = value.split('=')
            value = value.strip('" ')

            if name == 'MODEL': model = value
            if name == 'SERIAL': serial = value
            if name == 'SPEC': spec = value
            if name == 'FIRMID': firmId = value
            if name == 'FIRMVER':
                firmInfo.append({'cat': firmId, 'version': value})


# Print SNMP info
print
print '      serial =', serial
print '       model =', model
print '        spec =', spec

print '   firmwares'
for entry in firmInfo:
    print '            category = %(cat)s, version = %(version)s' % entry

print


# We need SSLv3
import ssl
from functools import wraps
def sslwrap(func):
    @wraps(func)
    def bar(*args, **kw):
        kw['ssl_version'] = ssl.PROTOCOL_TLSv1
        return func(*args, **kw)
    return bar

ssl.wrap_socket = sslwrap(ssl.wrap_socket)


def update_firmware(cat, version):
  global password

  print 'Updating %s version %s' % (cat, version)

  # Build XML request info
  xml = ET.ElementTree(ET.fromstring(reqInfo))

  # At least for MFC-J4510DW M1405200717:EFAC (see Internet dumps)
  # and MFC-J4625DW,
  # this element's value is *not* equal to per-firmware cat[egory] value
  # (a "MAIN"-deviating "FIRM" in these cases!),
  # but rather a *fixed* "MAIN" value which is a completely unrelated item,
  # thus I assume this to model-unconditionally have been a BUG
  # (which causes a failure response of the web service request).
  #xml.find('FIRMUPDATETOOLINFO/FIRMCATEGORY').text = cat
  xml.find('FIRMUPDATETOOLINFO/FIRMCATEGORY').text = 'MAIN'

  modelInfo = xml.find('FIRMUPDATEINFO/MODELINFO')
  modelInfo.find('SELIALNO').text = serial
  modelInfo.find('NAME').text = model
  modelInfo.find('SPEC').text = spec

  firm = modelInfo.find('FIRMINFO/FIRM')
  ET.SubElement(firm, 'ID').text = cat
  ET.SubElement(firm, 'VERSION').text = version

  requestInfo = ET.tostring(xml.getroot(), encoding = 'utf8')


  # Request firmware data
  url = 'https://firmverup.brother.co.jp/kne_bh7_update_nt_ssl/ifax2.asmx/' + \
      'fileUpdate'
  hdrs = {'Content-Type': 'text/xml'}

  print 'Looking up printer firmware...',
  sys.stdout.flush()

  import urllib2
  req = urllib2.Request(url, requestInfo, hdrs)
  response = urllib2.urlopen(req)
  response = response.read()

  print 'done'


  # Parse response
  xml = ET.fromstring(response)

  if verbose: print_pretty(xml)

  # Check version
  versionCheck = xml.find('FIRMUPDATEINFO/VERSIONCHECK')
  if versionCheck is not None and versionCheck.text == '1':
    print 'Firmware already up to date'
    return


  # Get firmware URL
  firmwareURL = xml.find('FIRMUPDATEINFO/PATH')
  if firmwareURL is None:
    print 'No firmware update info path found'
    sys.exit(1)
  firmwareURL = firmwareURL.text
  filename = firmwareURL.split('/')[-1]


  # Download firmware
  f = open(filename, 'w')

  print 'Downloading firmware %s...' % filename,
  sys.stdout.flush()

  req = urllib2.Request(firmwareURL)
  response = urllib2.urlopen(req)

  while True:
      block = response.read(102400)
      if not block: break
      f.write(block)
      sys.stdout.write('.')
      sys.stdout.flush()

  print 'done'
  f.close()


  # Get printer password
  if password is None:
    import getpass
    print
    password = getpass.getpass('Enter printer admin password: ')


  # Upload firmware to printer
  from ftplib import FTP

  print 'Uploading firmware to printer...',
  sys.stdout.flush()

  ftp = FTP(ip, user = password) # Yes send password as user
  ftp.storbinary('STOR ' + filename, open(filename, 'r'))
  ftp.quit()

  print 'done'

  print
  print 'Wait for printer to finish updating and reboot before continuing.'
  raw_input("Press Enter to continue...")


for entry in firmInfo:
  print
  update_firmware(entry['cat'], entry['version'])


print
print 'Success'
