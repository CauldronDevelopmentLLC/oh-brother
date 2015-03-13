# Oh Brother!
Oh Brother! is a simple cross-platform utility written in Pything which can
update Brother printer firmwares.  It was born out of frustration with Brother
for not providing a tool which works in Linux.  This tool should work on any
platform that has Python with ```python-pysnmp4```.  It was tested with Python
v2.7.8.

I found information on how to do this
[here](https://cbompart.wordpress.com/2014/02/05/printer-update/) and
[here](http://pschla.blogspot.com/2013/08/resurrecting-brother-hl-2250dn-after.html).

# Install prerequisites on Debian or Ubuntu

```
sudo apt-get install python-pysnmp4
```

# What it does
Curently the script does the following:

  1. Queries the printers information via the SNMP protocol.
  2. Prints SNMP info to screen.
  3. Queries Brother servers for the latest firmware.
  4. Exits if the firmware is up to date.
  5. Otherwise, downloads the firmware from Brother.
  6. Uploads the firmware via FTP to the printer.

# How to use it
You need to know both the IP address of your printer and the *admin* password.


```
./oh-brother.py <ip address of printer>
```

# If it doesn't work for you
YMMV.  Please feel free to submit a pull-request.

An alternate bash script for firmware download can be found
[here](https://cbompart.wordpress.com/2014/05/26/brother-printer-firmware-part-2/)
