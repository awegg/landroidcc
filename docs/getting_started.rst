Getting Started
===============

Installation
------------
Installation using pip

.. code-block:: python

   pip install landroidcc


Commandline usage
-----------------
After installation the command 'landroidcc' is available and can be used for example
to get the status and start the mower:

.. code-block:: bash

   landroidcc username password --status --start

The output will look like:

.. code-block:: bash

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

API Usage
---------
For using the landroid client directly from another Python using the Landroid class. The
status returned has the type: LandroidStatus

.. code-block:: python

   from landroidcc import Landroid

   landroid = Landroid("user", "pass")
   status = landroid.get_status()
   print("Battery: {}%".format(status.get_battery().percent))
   landroid.start()  # Start mowing


Update callback
^^^^^^^^^^^^^^^
Once connected the status gets updated automatically once the mower is sending an update. To
get a notification it's possible to register a callback function. See :meth:`landroidcc.Landroid.set_statuscallback`