## Chromium OS tap test app ##

This is repository of testing app for Chromium OS.

Python script reads kernel events from specified device and sends parsed information to server via socket.

GUI is Chromium OS application written in javascript. It creates a socket server to port 50008, to which the python app will try to connect.
Using of GUI is optional, but recommended, since controlling and configurating the app is a lot easier with it.

- - - -

### Configuration ###

This section describes how to configure the program. 

#### App configuration ####

The default configuration file of application may be found from [config/default.cfg](config/default.cfg).
The configuration file is read with [ConfigParser](https://docs.python.org/3.6/library/configparser.html).
Section names are ignored and may be overwritten.

Available parameters are:
```
ip
port
device_path
max_tcp_freq
screen_width
screen_height
require_gui
client_id
```

- Collected touch data is sent to defined IP-address and port.
- Device path (e.g. `/dev/input/event4`) can be defined. If not, app will list devices to user and user will choose the device when launching the app.
- Maximum TCP-packet sending frequency can be set with max_tcp_freq parameter. App will then send more data in one package and reduce traffic in network.
- Screen width and height are display resolution integers.
- Require_gui is used to determine if the program should wait for GUI to connect and control the execution.
- Client ID is used to differentiate DUTs connected to the same server.  Each DUT should have a unique ID.

##### Mandatory parameters
If GUI is required, no parameter is mandatory. Necessary parameters are obtained from the device and GUI.
**Mandatory** parameters (when running headless) are:
```
ip
screen_width
screen_height
```

##### Default parameters
Other parameters will get default values, if not defined in configuration file:
- port = 50007
- device\_type = stylus
- max\_tcp\_freq = 10
- client_id = 0

##### Other
- Device\_path has no default, it will be asked from user if the script is started manually


#### Logger configuration ####

Logger configuration is read by default from file [config/logging.json](config/logging.json).
It includes different loggers and their settings.
By default, it will log with level DEBUG to file `log/devicelog.log`.
Maximum size is 1MB and can be changed. 10 log files are saved and file rotation used.
Size may be raised according to needs.

- - - -

### Usage ###

1. Create or modify configuration files mentioned above [config/default.cfg](config/default.cfg) and [config/logging.json](config/logging.json).
2. Copy folder `OptoFidelity Touch Test` to DUT home (`~`) folder.
    - Optional: Copy `start_touch_test.conf` to `/etc/init/` to start python script when user logs in.
3. Install GUI app to chrome at `chrome://extensions`
   - Option 1: Install OF Touch Test GUI.crx.
   - Option 2:
      - Make sure that [Developer mode is on](https://developer.chrome.com/extensions/getstarted#unpacked).
      - Load unpacked extension from the folder [OF Touch Test GUI](OF Touch Test GUI) you copied to DUT.
3. Start app with command:
    ```
    python start.py [-c <path_to_your_config_file>] [-l <path_to_your_logging_conf>]
    For example:
    python start.py -c config/default.cfg -l config/logging.json
    ```
   - App parses option `-c` or `--config` as app configuration file.
   - Other parsed option is `-l` or `--log_config` which defines logging configuration file.
   - Help is printed with flag `-h` or `--help`
- Launch the GUI application


#### Using the GUI ####

Chromium OS GUI app is quite similar to other OptoFidelity Touch Test applications. There are two input fields, one for ip and another for port number. These are used when DUT is connecting to Sequencer.
In addition to those, the input device can be choosed from dropdown list. These devices are listed as `/dev/input/event*`.

After the GUI has connected to the background Python-script, the "Start testing" button will be enabled. Also the default ip and port will be inserted to according fields when default values are received from Python script.

After pushing the Start testing -button, DUT will connect to the Sequencer with given address and port.

Testing screen may be exited by swiping the screen with non-measured device.
This means that if the stylus is tested, touching the screen with finger will stop measurement, and other way around.
Measured device (eg. stylus device) cannot emit the touch events, since the device is grabbed to Python script. Thus only other devices will work.

---
### Miscellaneous
- Project should not depend on any libraries or modules that are not Python standard libraries.
