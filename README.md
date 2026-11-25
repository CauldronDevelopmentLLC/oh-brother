# Oh Brother!
Oh Brother! is a simple cross-platform utility written in Python which can
update Brother printer firmwares.  It was born out of frustration with Brother
for not providing a tool which works in Linux.  This tool should work on any
platform that has Python 3 with ``python-pysnmp4`` and ``python-pyasn1``.

I found information on how to do this
[here](https://cbompart.wordpress.com/2014/02/05/printer-update/) and
[here](http://pschla.blogspot.com/2013/08/resurrecting-brother-hl-2250dn-after.html).

# Disclaimer
I hope people find this project useful but I am not getting paid for it.  If you want to support this project, please [![donate](https://www.paypalobjects.com/en_US/i/btn/btn_donate_SM.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=J23DKKKYZRTA4).  If you think Brother should support this project [please tell them so](https://support.brother.com/g/b/contacttop.aspx).  Read the license for the full disclaimer.

# Install prerequisites

The `requirements.txt` file contains the required dependency versioning for
the PySNMP dependency. It can be installed with:

```
pip install -r requirements.txt
```

## On Debian-based distributions (e.g. Debian/Mint/Ubuntu)

```
sudo apt-get install -y python3-pysnmp4
```

## On RedHat-based distributions (e.g. Fedora/CentOS)

```
sudo yum install python-pysnmp
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
    * Upload the firmware to the printer via either TCP port 9100 (passwordless) or FTP (with admin password).
    * Wait for user to signal that the update is done.

# How to use it
You need to know both the IP address of your printer, and the *admin* password
if uploading firmware via FTP.
Run the script and press ```Enter``` after each
firmware has completed updating.


```
./oh-brother.py <ip address of printer>
```

# If it doesn't work for you
YMMV.

In order to send firmware updates via TCP port 9100, "Raw Port" must be
enabled in the printer's management interface. In order to send firmware
updates via FTP, you must have first set an admin password on the
printer via the web interface.

## Use ``--category``
Try specifying ``--category`` on the command line.  E.g.:

    ./oh-brother.py --category MAIN <printer IP>

This will force the script to update a specific firmware regardless of the
version you currently have.

## Download firmware without the printer

The vendor's update server resolves the firmware image from model and SPEC
alone, so the tool can download the image without a printer being present
on the network:

    ./oh-brother.py --download-only -m "Brother HL-L2375DW series" -S <SPEC> -c MAIN -f 1.77

``--model``, ``--spec`` and ``--category`` are required in this mode.  SPEC is a per
model/region code; if you do have the printer reachable, read it via
SNMP instead:

    snmpget -v1 -c public <printer-ip> 1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2

Note that the version passed with ``-f`` should be a real lower version
currently installed (e.g. ``1.77``); placeholder values such as ``0`` or
``1.0`` are rejected by the vendor server with a ``VERSIONCHECK=2``
response.

If the server rejects the model/SPEC combination, the tool now prints a
clear error instead of exiting silently.  On models with an NC-9300h
network card, the SNMP agent lives on the network card and expects the
community ``public``; unknown communities are silently dropped, which
looks like a timeout.

## Label printers (QL series)

QL label printers are not known to the vendor service used for laser and
inkjet models, which answers ``VERSIONCHECK=2`` for them.  The tool detects
QL models automatically (or use ``--label-printer`` to force it) and instead
queries the service used by the vendor's P-touch Update Software.

For label printers the tool only downloads the firmware; it never uploads it.
It saves the ``.PDZ`` package and extracts the ``.PD3`` firmware image from
it, ready to be sent with the vendor's tools or SDK:

    ./oh-brother.py --test <printer IP>
    ./oh-brother.py --download-only -m QL-820NWB -S ALL_USA -c FP-MAIN

The vendor server offers firmware as a sequence of steps rather than jumping
straight to the newest release: it answers with the next version the printer
should install (e.g. ``FP-MAIN_01`` goes V0215, then V0219).  Query with the
version the printer reports and check again after each update.  Without
``-f`` the tool sends ``V0000``, which returns the first step that is still
offered, not necessarily the newest firmware.

To only check whether an update exists, without downloading anything, use
``--check``.  For label printers it also shows the release title, size and
notes:

    ./oh-brother.py --check <printer IP>
    ./oh-brother.py --check -m QL-820NWB -S ALL_USA -c FP-MAIN

``--check`` works for laser and inkjet models too.

Printers of the same model can report different firmware categories (e.g. ``FP-MAIN``
and ``FP-MAIN_01`` for different hardware revisions), each with its own
firmware line, so read the category from the printer when possible.

## Submit a PR
Please feel free to submit a pull-request.

## Other options
An alternate bash script for firmware download can be found
[here](https://cbompart.wordpress.com/2014/05/26/brother-printer-firmware-part-2/).
