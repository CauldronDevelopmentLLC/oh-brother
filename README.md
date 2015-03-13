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


# How to use it
You need to know both the IP address of your printer and the *admin* password.


```
./oh-brother.py <ip address of printer>
```

# If it doesn't work for you
YMMV.  Please feel free to submit a pull-request.
