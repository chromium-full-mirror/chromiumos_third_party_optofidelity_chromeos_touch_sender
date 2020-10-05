# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE_chromiumos file.

import sys
import select
import errno
import math
import logging
import threading
import time

from evdev import ecodes
from threading import Lock
from .event import MtEvent
from .state_machine import MtaStateMachine, MtbStateMachine, StylusStateMachine
from .sockethandler import SocketHandler
from .guihandler import JavascriptGUI
from .util import devicechooser
from .util import config_utils as util

MTA = 'mta'
MTB = 'mtb'
STYLUS = 'stylus'

logger = logging.getLogger(__name__)


class SnapshotSender(object):
    """ Class for sending snapshot stream with to other application via socket.
        Works with stylus and MTB-devices
    """

    def __init__(self, configfile):

        self.ip = None
        self.port = 50007
        self.device_type = 'stylus'
        self.devpath = None
        self.max_tcp_freq = 10.0
        self.screen_w = 0
        self.screen_h = 0
        self.require_gui = True
        self.device = None
        self.sm = None

        self.devicechooser = devicechooser.DeviceChooser()
        self.configfile = configfile
        self.configFromFile(configfile)

        self.events = []
        self.collect_events = True
        self.running = True
        self.paused = True
        self.changing_device = False
        self.should_grab_device = False
        self.screen_enabled = True
        self.event_lock = Lock()
        self.device_lock = Lock()

        self.startDevice()
        self.event_collector = threading.Thread(target=self.collectEvents)

        logger.debug('Creating GUI')
        self.gui = JavascriptGUI(config_callback=self.guiCallback)

        logger.debug('Creating socket')
        self.socket = SocketHandler(
            self.ip, self.port, self.max_tcp_freq, cmd_callback=self.sequencerCB)

        logger.info('Initialization done')

    def checkConfig(self):
        if not self.require_gui:
            if self.ip is None:
                raise ValueError('IP is required, if GUI is not')
            if self.screen_w <= 0:
                raise ValueError('Valid screen width is required, if GUI is not')
            if self.screen_h <= 0:
                raise ValueError('Valid screen height is required, if GUI is not')

    def collectEvents(self):
        while self.collect_events:
            if self.changing_device or self.device is None:
                time.sleep(0.1)
                continue

            with self.device_lock:
                # Grab the device if it is not active and should be grabbed
                if self.should_grab_device and not self.device.touch_active():
                    self.device.grab()
                    self.should_grab_device = False

                ev = self.device.read_one()

                if ev is not None and not self.paused:
                    # Create MtEvent and add it to eventlist
                    event = self.createEvent(ev)
                    with self.event_lock:
                        self.events.append(event)

    def configFromFile(self, filename):
        """ This function reads configuration file and sets class variables
            to desired values. """
        conf = util.get_file_config(filename)
        self.configFromDict(conf)
        self.checkConfig()

        self.sm = self.getStateMachine()
        if self.sm is None:
            logger.error('Invalid device type "{}", program exits'
                         .format(self.device_type))
            sys.exit()

    def configFromDict(self, conf):
        """ This function reads configuration from dictionary """
        self.ip = conf.get('ip', self.ip)
        self.port = int(conf.get('port', self.port))
        self.device_type = conf.get('device_type', self.device_type)
        self.devpath = conf.get('device_path', self.devpath)
        self.max_tcp_freq = float(conf.get('max_tcp_freq', self.max_tcp_freq))
        self.screen_w = int(conf.get('screen_width', self.screen_w))
        self.screen_h = int(conf.get('screen_height', self.screen_h))
        self.require_gui = util.str2bool(conf.get('require_gui', str(self.require_gui)))

    def configToFile(self):
        """ Function writes a new configuration file based on class current
            configuration. New configuration variables may be added as
            a new keyword argument to the write_config_file -function """
        filename = self.configfile
        section = 'settings'
        util.write_config_file(filename, section,
                               ip=self.ip, port=self.port,
                               device_type=self.device_type,
                               device_path=self.devpath,
                               max_tcp_freq=self.max_tcp_freq,
                               screen_width=self.screen_w,
                               screen_height=self.screen_h
                               )

    def createEvent(self, ev):
        """ Create MtEvent from raw event """
        event = MtEvent(timestamp=ev.timestamp(), event_type=ev.type,
                        event_code=ev.code, value=ev.value)
        return event

    def createMessage(self, snapshot):
        """ Create a data list from snapshot information
        """

        # Actions:
        # 0 = touch started (ACTION_DOWN)
        # 1 = touch ended (ACTION_UP)
        # 2 = touch moved (Usual case, ACTION_MOVE)
        # 3 = touch cancelled (touch not lifted up, but ended. ACTION_CANCEL)
        # 9 = hovering started (ACTION_HOVER_DOWN)
        # 7 = hovering (ACTION_HOVER_MOVE)
        # 10 = hovering ended (ACTION_HOVER_UP)
        actions = self.sm.get_current_action_state()

        datas = []

        # Seconds to milliseconds
        time = int(float(snapshot[0]) * 1000)

        if self.device_type == STYLUS:
            # Usually only one stylus at a time, but loop through just to be
            # sure
            for pointer in snapshot[2]:
                pointerID = str(pointer[0])
                # Check that x-coordinate is not None
                if pointer[2] is not None:
                    x = float(pointer[2])
                else:
                    x = None
                # Check that y-coordinate is not None
                if pointer[3] is not None:
                    y = float(pointer[3])
                else:
                    y = None
                # Check that pressure is not None
                p = 0.0
                if pointer[4] is not None:
                    p = float(pointer[4])

                # Scale coordinates to pixels
                (x, y) = self.scaleData(x, y)

                # Get tilt and yaw angles of stylus
                (tilt, yaw) = self.sm.get_tilt_and_yaw()
                act = actions[int(pointer[0])]

                # Create datalist and add it to list
                data = [x, y, p, pointerID, 0, time, act, yaw, tilt, 0]
                datas.append(data)

        elif self.device_type == MTB:
            # Loop through all fingers
            for finger in snapshot[2]:
                slot = self.sm.get_slot_of_tid(finger[0])
                # Use slot as pointerID
                pointerID = str(slot)
                # Scale coordinates to pixels
                (x, y) = self.scaleData(float(finger[2]), float(finger[3]))
                p = float(finger[4])
                tilt = 0.0
                yaw = 0.0
                act = actions[slot]
                data = [x, y, p, pointerID, 0, time, act, yaw, tilt, 0]
                datas.append(data)

        else:
            datas = None

        return datas

    def dataToString(self, data):
        """ Create a string from data list
        """
        # Data string: x     y      force key time phase azim. alt.   ang
        # dist
        data_str = '({:.2f},{:.2f},{:.2f},{:s},{:d},{:d},{:d},{:.5f},{:.5f},{:d}),'.format(
            *data)
        return data_str

    def getDeviceDataLimits(self):
        try:
            # Get device min/max info
            self.min_x = self.device.absinfo(ecodes.ABS_X).min
            self.max_x = self.device.absinfo(ecodes.ABS_X).max
            self.min_y = self.device.absinfo(ecodes.ABS_Y).min
            self.max_y = self.device.absinfo(ecodes.ABS_Y).max

            # Get initial values of coordinates from device, if available
            if self.device_type == STYLUS:
                self.sm.x = self.device.absinfo(ecodes.ABS_X).value
                self.sm.y = self.device.absinfo(ecodes.ABS_Y).value
                self.sm.p = self.device.absinfo(ecodes.ABS_PRESSURE).value

        except:
            logger.warn(sys.exc_info()[0])

        logger.info('x-min: {}'.format(self.min_x))
        logger.info('x-max: {}'.format(self.max_x))
        logger.info('y-min: {}'.format(self.min_y))
        logger.info('y-max: {}'.format(self.max_y))

    def getStateMachine(self):
        if self.device_type == STYLUS:
            logger.info('Using stylus state machine')
            if isinstance(self.sm, StylusStateMachine):
                sm = self.sm
            else:
                sm = StylusStateMachine()
        elif self.device_type == MTA:
            logger.error('Using MTA state machine (not implemented)')
            if isinstance(self.sm, MtaStateMachine):
                sm = self.sm
            else:
                sm = None
        elif self.device_type == MTB:
            logger.info('Using MTB state machine')
            if isinstance(self.sm, MtbStateMachine):
                sm = self.sm
            else:
                sm = MtbStateMachine()
        else:
            sm = None

        return sm

    def getNextEvent(self):
        """ Get next event from the device.
        """

        # If all events are read, wait and ask again
        while len(self.events) == 0 and self.running:
            time.sleep(0.01)

        if not self.running:
            return None

        # When events available, return first event and remove it from list
        with self.event_lock:
            event = self.events[0]
            self.events.pop(0)

        return event

    def getSnapshot(self):
        """ Get latest event """

        while self.running:
            # Get next raw event
            event = self.getNextEvent()

            if event is None:
                return None

            self.sm.add_event(event)

            is_syn = event.is_SYN_MT_REPORT() or event.is_SYN_REPORT()

            if is_syn:

                if self.sm.buffer_overrun:
                    logger.warn('Device buffer overflow')
                    self.sm.buffer_overrun = False
                    logger.info('Device connection reseted')

                else:
                    snap = self.sm.get_current_snapshot()
                    return snap

    def guiCallback(self, data):
        """ This function will be given to GUI object.
            It will be called by GUI object when data is received. """

        datas = data.split(';')
        for data in datas:
            if data == '':
                continue

            elif data == 'query_config':
                available_devices = self.devicechooser.getDeviceList()
                self.gui.set_config(ip=self.ip, port=self.port, devpath=self.devpath, devpaths=available_devices)
                logger.info('Current configuration sent to GUI')

            elif data == 'stop':
                if not self.paused:
                    logger.info('Stopping...')
                    self.should_grab_device = False
                    logger.info('Ungrabbing device...')
                    self.device.ungrab()
                    self.paused = True
                    logger.info('Closing socket connection...')
                    self.socket.close()
                    logger.info('Stopped (paused)')

            elif data == 'pause':
                if not self.paused:
                    logger.info('Pausing...')
                    self.should_grab_device = False
                    logger.info('Ungrabbing device...')
                    self.device.ungrab()
                    self.paused = True
                    logger.info('Closing socket connection...')
                    self.socket.close()
                    logger.info('Updating connection status to GUI...')
                    self.updateConnectionStatus()
                    logger.info('Paused')

            elif data.startswith('config:'):
                conf = util.get_json_config(data.split(':', 1)[1])
                logger.debug('Closing socket')
                self.socket.close()
                self.gui.set_connection_status('Connecting')
                logger.debug('Socket closed, updating configuration')
                self.configFromDict(conf)
                logger.debug('Setted configuration from dictionary')
                self.configToFile()
                logger.debug('Wrote config to file')
                self.startDevice()
                self.should_grab_device = True
                logger.debug('Device started')
                self.socket.ip = self.ip
                self.socket.port = self.port
                logger.info('Configuration updated, starting socket')

                self.socket.run(retries=1)

                if self.socket.connection_ok:
                    self.updateConnectionStatus()
                    self.paused = False

                else:
                    self.gui.set_connection_status('Failed')

            elif data == 'latency':
                self.device.ungrab()

            else:
                logger.warn('Received unknown message: {}'.format(data))

    def matchDeviceAndSM(self):
        """ Check device type and choose state machine accordingly """
        if self.device is None:
            pass
        elif self.device.is_mt_b():
            self.device_type = MTB
        elif self.device.is_mt_a():
            self.device_type = MTA
            raise NotImplementedError('Mta devices not supported!')
        else:
            self.device_type = STYLUS

        self.sm = self.getStateMachine()

    def startDevice(self):
        """ Open device from self.devpath and update state machine, if necessary
        """
        device = self.devicechooser.getDevice(self.devpath, ask_user=not self.require_gui)
        if device == self.device:
            logger.debug('Using current device')
            self.matchDeviceAndSM()
            return
        elif self.device is not None:
            self.device.shutdown()
        self.changing_device = True
        with self.device_lock:
            logger.info('Changing device to {}'.format(self.devpath))
            self.device = device
            logger.info('Device changed, getting limits')
            self.getDeviceDataLimits()
            logger.debug('Device datalimits obtained, updating current device path')
            self.devpath = self.device.path
            logger.info('Device path is currently {}'.format(self.devpath))
            self.matchDeviceAndSM()

        self.changing_device = False

    def run(self):
        """ Run program in loop. Read snapshot, create a message from it and send it forward.
        """
        logger.info('Starting to collect events')
        self.event_collector.start()

        logger.info('Starting GUI connection')
        if self.require_gui:
            retries = -1
        else:
            retries = 3

        self.gui.run_gui(retries=retries)

        if not self.gui.connection_ok:
            self.paused = False
            self.socket.run()

        # Wait for user to start measurements from GUI, or exit the program
        while self.paused and self.running:
            time.sleep(0.1)

        self.runLoop()

    def runLoop(self):
        while self.running:
            # Get one snapshot
            snapshot = self.getSnapshot()
            if snapshot is None:
                if self.sm.btn_touch and self.running:
                    logger.warn('Snapshot is None for unknown reason')
                continue

            datas = self.createMessage(snapshot)
            if datas is not None:
                for data in datas:
                    self.sendViaSocket(data)
                    logger.debug(data)

                if self.gui.connection_ok: self.showData(datas)

    def scaleData(self, x, y):
        """ Scale coordinates to [0-max_value]
        """
        if x is not None:
            x = x * self.screen_w / self.max_x
        else:
            x = 0.0

        if y is not None:
            y = y * self.screen_h / self.max_y
        else:
            y = 0.0

        return (x, y)

    def sendViaSocket(self, data):
        """ Transforma data to string and send it with socket
            Socket used is a class that handles connection and limits traffic
        """
        try:
            msg = self.dataToString(data)

        except ValueError:
            logger.warn(
                'Data is in invalid format. Check createMessage-function')
            raise ValueError(data)

        self.socket.send(msg)

    def sequencerCB(self, msg):
        """ Callback function for messages coming from Sequencer """
        pass

    def showData(self, datas):

        # Default: ACTION_END
        major_action = 1

        for data in datas:
            # If some touch is moving, action is always ACTION_MOVE
            if data[6] == 2:
                major_action = 2
                break

            # If action is not ACTION_MOVE, assign current value.
            # However, if touch is starting, consider it as major action.
            # Thus ACTION_START overrides ACTION_END, ACTION_CANCEL and all
            # hover actions.
            elif major_action != 0:
                major_action = data[6]

        x = []
        y = []
        p = []

        for data in datas:
            x.append(data[0])
            y.append(data[1])
            p.append(data[2])

        self.gui.set_info(x, y, p, major_action)
        self.updateConnectionStatus()

    def updateConnectionStatus(self):
        """ Update datasocket connection status to GUI """
        status = 'Lost'
        if self.socket.connection_ok:
            status = 'OK'
        self.gui.set_connection_status(status)

    def shutdown(self):
        logger.info('Shutting down...')
        if self.gui.connection_ok or self.require_gui:
            logger.info('Stopping GUI connection')
            self.gui.stop_gui()
        logger.info('Stopping event collector...')
        self.collect_events = False
        time.sleep(0.2)
        if self.event_lock.locked():
            self.event_lock.release()
        if self.event_collector.isAlive():
            self.event_collector.join()
        logger.info('Stopping socket connection')
        self.socket.close()
        if self.device is not None:
            logger.info('Ungrabbing device')
            self.device.ungrab()
            logger.info('Stopping input device')
            self.device.shutdown()
        logger.info('Shutdown ready')
