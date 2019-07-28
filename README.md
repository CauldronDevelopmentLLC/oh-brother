# Oh Brother!
Oh Brother! is a simple cross-platform utility written in Python which can
update Brother printer firmwares.  It was born out of frustration with Brother
for not providing a tool which works in Linux.  This tool should work on any
platform that has Python with ``python-pysnmp4`` and ``python-pyasn1``.  It was tested with Python
v2.7.8 and v2.7.5.

I found information on how to do this
[here](https://cbompart.wordpress.com/2014/02/05/printer-update/) and
[here](http://pschla.blogspot.com/2013/08/resurrecting-brother-hl-2250dn-after.html).

# Disclaimer
I hope people find this project useful but I am not getting paid for it.  If you want to support this project, please [![donate](https://www.paypalobjects.com/en_US/i/btn/btn_donate_SM.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=J23DKKKYZRTA4).  If you think Brother should support this project [please tell them so](http://www.brother-usa.com/askus/).  Read the license for the full disclaimer.

# Install prerequisites

## On Debian-based distributions (e.g. Debian/Mint/Ubuntu)

```
sudo apt-get install -y python-pysnmp4
```

## On RedHat-based distributions (e.g. Fedora/CentOS)

The [EPEL](https://fedoraproject.org/wiki/EPEL) repositories offer ``pysnmp``
packages for RHEL/CentOS 6 and 7.

Fedora does not appear to offer a package providing a Python 2 version of
``pysnmp``, instead offering the ``python3-pysnmp`` package. The Python package
installer ``pip`` may be used to install ``pysnmp``.

```
sudo pip install pysnmp
```

A virtual environment can be used instead to avoid system-wide changes.
Creating a Python 2 virtual environment requires installation of the
``virtualenv`` command via the ``python3-virtualenv`` package.

```
sudo dnf install python3-virtualenv
```

The virtual environment can be created, activated, and ``pysnmp`` installed in
that environment as follows. This example below creates the environment in the
directory ``venv-pysnmp``.

```
virtualenv --python /usr/bin/python2 venv_pysnmp
source venv_pysnmp/bin/activate
pip install pysnmp
deactivate
```

The virtual environment must be active when running the ``oh-brother.py``
script. The ``deactivate`` command can be used to return to the normal system
Python environment.

```
source venv_pysnmp/bin/activate
./oh-brother.py <ip address of printer>
deactivate
```

## On OSX or Windows with Python installer (PIP)

```
pip install pysnmp
```

# What it does
Currently the script does the following:

  * Query the printer's information via the SNMP protocol.
  * Print SNMP info to screen.
  * For each firmware type:
    * Query Brother servers for the latest firmware.
    * Download the firmware from Brother.
    * Display firmware info, then ask user whether to proceed with updating.
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
YMMV.

## Set admin password
Make sure you've set the admin password on the printer via the web interface.

## Use ``--category``
Try specifying ``--category`` on the command line.  E.g.:

    ./oh-brother.py --category MAIN <printer IP>

This will force the script to update a specific firmware regardless of the
version you currently have.

## Submit a PR
Please feel free to submit a pull-request.

## Other options
& An alternate bash script for firmware download can be found [here](https://cbompart.wordpress.com/2014/05/26/brother-printer-firmware-part-2/).
