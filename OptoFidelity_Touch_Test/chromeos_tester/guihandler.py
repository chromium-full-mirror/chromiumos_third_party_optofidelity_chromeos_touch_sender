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
import time
import threading
import logging
import socket
import select
import errno

from threading import Lock
from chromeos_tester.util import config_utils as util

logger = logging.getLogger(__name__)


def emptyFunc(*args):
    pass


class JavascriptGUI(object):
    """ Class for handling communication between Python tester software and
        Javascript GUI. """

    def __init__(self, ip='127.0.0.1', port=50008, timeout=3, measure_latency=False, config_callback=emptyFunc):

        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.measure_latency = measure_latency
        self.connection_ok = False
        self.s = None
        self.seq_connection_status = False
        self.config_callback = config_callback
        self.msgs = []
        self.msg_lock = Lock()
        self.sock_thread = threading.Thread(target=self.handleSocket)
        self.running = True

    def init_connection(self, retries=-1):
        """ Initialize socket TCP-connection to defined ip and port
            Retries is number of connecting attempts, -1 meaning infinite
        """
        logger.debug('Connecting to GUI socket')
        logger.info('Please launch OptoFidelity Touch Tester app')

        self.s = None
        self.connection_ok = False
        self.seq_connection_status = False

        logger.debug('Connecting to: {}:{}'.format(self.ip, self.port))

        while not self.s and retries != 0 and self.running:
            retries -= 1
            try:

                # Create a socket and try to connect

                self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                self.s.settimeout(self.timeout)

                self.s.connect((self.ip, self.port))

                msg = self.s.recv(2)

                if msg != 'OK':
                    logger.warn('Did not get OK-message from GUI, retrying connection.')
                    self.s.close()
                    self.s = None
                    continue

                self.connection_ok = True


            except socket.timeout:
                self.s = None
                logger.debug('Connection timeout when connecting to GUI')

            except socket.error as e:
                if retries % 60 == 0:
                    logger.debug('Connection to GUI failed: {}'.format(e))
                time.sleep(1)
                self.s = None

            except KeyboardInterrupt:
                raise

        if retries == 0 and not self.connection_ok:
            logger.warn('Could not connect to GUI socket, running headless')
        else:
            logger.info('Connected to GUI')

    def handleSocket(self):
        conn_broken = False

        while self.running:

            rs, ws, es = select.select([self.s], [self.s], [self.s], 30)

            for r in rs:
                data = r.recv(2048)
                if len(data) != 0:
                    logger.debug('Received data from GUI: {}'.format(data))
                    self.config_callback(data)
                else:
                    conn_broken = True

            self.msg_lock.acquire()
            for m in self.msgs:
                for w in ws:
                    try:
                        self.send_tcp_msg(w, m)
                    except socket.error:
                        conn_broken = True
                self.msgs.pop(0)
            self.msg_lock.release()

            for e in es:
                e.close()
                self.init_connection(retries=-1)
                conn_broken = False

            if conn_broken:
                self.s.close()
                self.init_connection(retries=-1)
                conn_broken = False

            time.sleep(0.05)

    def run_gui(self, retries=3):
        self.init_connection(retries=retries)
        if self.connection_ok:
            self.sock_thread.start()

    def send_msg(self, msg):
        """ Function for sending messages to GUI.
            Each message is appended with ; to separate messages serverside
        """
        self.msg_lock.acquire()
        self.msgs.append(msg)
        self.msg_lock.release()

    def send_tcp_msg(self, sock, msg):
        try:
            sock.send(msg + ';')

        except socket.error, e:

            if e[0] == errno.EPIPE or e[0] == errno.ECONNRESET:
                logger.warn("Connection broken, trying to reconnect")

            else:
                logger.warn(e)

            raise

    def set_info(self, x, y, p, actioncode):
        """ GUI gets information about previous touch
            This function sends touch start, end and cancel events to GUI
        """

        if actioncode != 0 and actioncode != 1 and actioncode != 3:
            return

        msg = "touch:{}".format(actioncode)

        self.send_msg(msg)

    def set_config(self, **kwargs):
        """ Function for showing current sequencer Ip and port in GUI
        """
        conf = {}
        for key in kwargs:
            conf[key] = kwargs[key]
        msg = 'config:' + util.json_from_dict(conf)
        # msg = 'config:{{"ip":"{}", "port": "{}"}}'.format(ip, port)
        self.send_msg(msg)

    def set_connection_status(self, status):
        if status != self.seq_connection_status:
            self.seq_connection_status = status
            msg = "conn:{}".format(status)
            try:
                self.send_tcp_msg(self.s, msg)
            except socket.error, e:
                # Just warning if can't send, nothing crucial
                logger.warn(e)

    def close_socket(self):
        if self.s is not None:
            self.s.close()

    def stop_gui(self):
        """ Close socket
        """
        self.connection_ok = False
        self.running = False
        if self.sock_thread.isAlive():
            self.sock_thread.join()
        self.close_socket()