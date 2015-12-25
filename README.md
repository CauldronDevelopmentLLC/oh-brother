# Oh Brother!
Oh Brother! is a simple cross-platform utility written in Python which can
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
Currently the script does the following:

  * Query the printer's information via the SNMP protocol.
  * Print SNMP info to screen.
  * For each firmware type:
    * Query Brother servers for the latest firmware.
    * Download the firmware from Brother.
    * Upload the firmware via FTP to the printer.
    * Wait for user to signal that the update is done.

# How to use it
You need to know both the IP address of your printer and the *admin* password.
Run the script, enter the password when asked and press ```Enter``` after each
firmware has completed updating.


```
./oh-brother.py <ip address of printer>
```

# If it doesn't work for you
YMMV.  Please feel free to submit a pull-request.

An alternate bash script for firmware download can be found
[here](https://cbompart.wordpress.com/2014/05/26/brother-printer-firmware-part-2/).
