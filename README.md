Landroid Cloud Client
=====================

[![Build Status](https://travis-ci.org/awegg/landroidcc.svg?branch=master)](https://travis-ci.org/awegg/landroidcc)
[![Build Status](https://readthedocs.org/projects/landroidcc/badge/?version=latest)](https://landroidcc.readthedocs.io/en/latest/)

Python library and command line tool to communicate with mowers like:
- WR141E / Landroid M500
- WR142E / Landroid M700
- WR143E / Landroid M1000

Installation
------------
Installation using pip

```
pip install landroidcc
```

Commandline usage
-----------------
After installation the command 'landroidcc' is available and can be used for example
to get the status and start the mower:

```
landroidcc username password --status --start
```

The output will look like:

```
2019-05-12 22:25:32 __init__ _api_authentificate INFO     Successfully logged in
2019-05-12 22:25:33 __init__ on_connect INFO     Successfully connected to the cloud
landroid info
#############
Name:   Schaf
Serial: xxxxxxxxxxxxxxxxxxxx
Type:   WR141E

landroid status
###############
LastUpdate: 22:25:34 12/05/2019
State:      Home
Error:      No error
Battery:    100%/9.2C/19.63v
```

API Usage
---------
For using the landroid client directly from another Python using the Landroid class. The
status returned has the type: LandroidStatus

```python

   from landroidcc import Landroid

   landroid = Landroid("user", "pass")
   status = landroid.get_status()
   print("Battery: {}%".format(status.get_battery().percent))
   landroid.start()  # Start mowing
```