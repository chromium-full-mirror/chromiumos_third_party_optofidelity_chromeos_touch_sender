"""
Copyright (c) 2019, OptoFidelity OY

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
    2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
    3. All advertising materials mentioning features or use of this software must display the following acknowledgement: This product includes software developed by the OptoFidelity OY.
    4. Neither the name of the OptoFidelity OY nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
from chromeos_tester.input import input_device
import glob
import sys
import logging

logger = logging.getLogger(__name__)


class DeviceChooser(object):
    """ Class that can be used to get InputDevice object for selected device.
        If device is not defined, it will be asked from user
    """

    def __init__(self):
        """ Initially class will try to open device from devpath.
            If devpath is not defined, open all and ask from user which one to use.
        """
        self._devices = []
        self._device = None
        self._dev_paths = glob.glob('/dev/input/event*')

    def _setDevice(self, devpath):
        if self._device is not None:
            if devpath == self._device.path:
                logger.debug("Device {} already in use".format(devpath))
                return
            else:
                logger.debug('Closing {} and opening {}'.format(self._device.path, devpath))
                self._device.shutdown()
                self._device = input_device.InputDevice(devpath)
                return

        elif devpath in self._dev_paths:
            self._device = input_device.InputDevice(devpath)

        else:
            logger.info('Device not available at the given path, not changing the device')

    def _askDevice(self):
        ind = -1

        for path in self._dev_paths:
            logger.debug('Opening {}'.format(path))
            device = input_device.InputDevice(path)
            self._devices.insert(0, device)

        for i in range(len(self._devices)):
            print '{}: {}, {}'.format(i, self._devices[i].path, self._devices[i].name)

        print('Choose device 0-{}:'.format(len(self._devices) - 1))
        try:
            ind = raw_input('>> ')
            ind = int(ind)
            if not 0 <= ind < len(self._devices):
                raise ValueError
        except ValueError:
            raise ValueError('Invalid device index: {}'.format(ind))

        device = self._devices[ind]

        # Close unnecessary devices
        for i in range(len(self._devices)):
            if self._devices[i] != device:
                self._devices[i].shutdown()

        return device

    def getDevice(self, devpath, ask_user=True):
        """ Return opened device object or let user decide which device will be used
        """

        # If device not defined, create a list of devices to choose from
        self._setDevice(devpath)

        if self._device is None and ask_user is True:
            self._device = self._askDevice()

        return self._device

    def getDeviceList(self):
        return self._dev_paths
