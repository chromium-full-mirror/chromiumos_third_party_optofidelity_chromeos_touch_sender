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
import socket
import time
import logging
import errno

import threading
from threading import Lock

logger = logging.getLogger(__name__)

# Maximum message length, 9999 - 10 characters
MAX_LEN = 9989

def emptyFunc(*args):
    pass

class SocketHandler(object):
    """ Class for handling communication between DUT and server.
        Used to communicate periodically to server. """
    def __init__(self, ip, port=50007, max_send_frequency=10, timeout=2.5, cmd_callback=emptyFunc):

        self.max_freq = max_send_frequency
        self.limit_sending = True
        # If maximum sending frequency is 0 or lower, don't limit sending frequency
        if self.max_freq <= 0:
            self.limit_sending = False

        elif self.max_freq < 0.5:
            logger.warn('Maximum sending frequency is low, one message per {:.2f} seconds'.format(self.max_freq))

        # Sequencer commands calls this callback function
        self.sequencerCmdCb = cmd_callback

        self.s = None
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.retries = -1
        self.config_msg = ''
        self.messages = []
        self.run_thread = True
        self.connection_ok = False
        self.config_lock = Lock()
        self.msg_lock = Lock()
        self.socket_lock = Lock()
        self.send_thread = threading.Thread(target=self.sender_thread)
        self.recv_thread = threading.Thread(target=self.receiver_thread)

    def add_length_to_msg(self, msg):
        """ Calculate length of the message and add four char length in front of it
        """
        length = '{:04d}'.format(len(msg))
        full_msg = length + msg
        return full_msg

    def close(self):
        """ Close sending thread and close socket
        """
        self.run_thread = False

        # Join threads
        logger.debug('Joining threads...')
        if self.send_thread.isAlive(): self.send_thread.join()
        if self.recv_thread.isAlive(): self.recv_thread.join()

        # Make new threads in case of they are restarted
        logger.debug('Creating new threads in case of new start...')
        self.send_thread = threading.Thread(target=self.sender_thread)
        self.recv_thread = threading.Thread(target=self.receiver_thread)

        logger.debug('Closing socket connection...')
        if self.s is not None:
            self.s.close()

        logger.debug('Emptying messages...')
        self.messages[:] = []

        logger.debug('Socket closing ready')

        self.connection_ok = False

    def create_message(self):
        msg = ''
        ev_count = 0

        self.msg_lock.acquire()

        # Add as many messages from queue as possible to send at once
        for m in self.messages:
            if len(msg) + len(m) <= MAX_LEN:
                ev_count += 1
                msg += m
            else:
                break

        # Remove added messages from queue
        for i in range(ev_count):
            self.messages.pop(0)

        self.msg_lock.release()
        if ev_count > 0:
            msg = '[' + msg + '"OK",""]'
        return msg


    def init_connection(self, retries=-1):
        """ Initialize socket TCP-connection to defined ip and port
            Use self.socket_lock when calling this function!
        """
        logger.info('Connecting to: {}:{}'.format(self.ip, self.port))
        self.s = None
        self.connection_ok = False

        while not self.s and retries != 0 and self.run_thread:
            retries -= 1
            try:
                # Create a socket and try to connect
                self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                self.s.settimeout(self.timeout)

                self.s.connect((self.ip, self.port))

                self.s.setblocking(0)

                self.connection_ok = True
                self.run_thread = True

                logger.info('Connected')

            except socket.timeout:
                self.s = None
                logger.warn('Connection timeout')

            except socket.error as e:
                if retries % 10 == 0:
                    logger.warn('Connection failed: {}'.format(e))
                time.sleep(1)
                self.s = None

            except KeyboardInterrupt:
                self.run_thread = False
                raise

        if retries == 0 and not self.connection_ok:
            logger.warn('Could not connect to the server {}:{}'.format(self.ip, self.port))
            return False
        else:
            return True

    def run(self, retries=-1):
        self.retries = retries
        self.run_thread = True
        self.socket_lock.acquire()
        self.init_connection(retries)
        self.socket_lock.release()

        if self.connection_ok:
            self.send_thread.start()
            self.recv_thread.start()

    def receiver_thread(self):

        while self.run_thread:
            self.socket_lock.acquire()
            if self.s:
                try:
                    # Try to receive message
                    msg = self.s.recv(128)
                    self.socket_lock.release()
                    self.sequencerCmdCb(msg)

                except socket.timeout:
                    # Connection timeout
                    self.socket_lock.release()

                except socket.error as e:
                    # Other socket errors
                    self.socket_lock.release()
                    # Broken pipe error or connection reset by peer
                    if e.errno == errno.EPIPE or e.errno == errno.ECONNRESET:
                        self.connection_ok = False
                    elif e.errno == errno.EAGAIN:
                        pass
                    else:
                        logger.warn(e)
            else:
                self.socket_lock.release()
            time.sleep(0.5)


    def send(self, msg):
        """ Add message to older ones.
            Check if message is too long, and discard it if there is too much data
            to send in one message.
            Maximum length = 9999, and it consists of [<data>,'OK','']
            = data + 10 characters
        """
        if len(''.join(self.messages)) >= MAX_LEN - len(msg):
            logger.warn('Too much data to send, adding message to queue')

        if not self.connection_ok:
            logger.warn('Sending without socket connection, adding message to queue')

        self.msg_lock.acquire()

        self.messages.append(msg)

        self.msg_lock.release()

    def send_config(self, msg):
        with self.config_lock:
            self.config_msg = 'CONFIG ' + msg

    def sender_thread(self):
        """ This function runs a thread which sends data with TCPSocket protocol:
            https://wiki.optofidelity.com/display/OTA/Communication+Protocol+Specification
        """

        while self.run_thread:
            if self.config_msg is not '':
                with self.config_lock:
                    msg = self.config_msg
                    self.config_msg = ''
            else:
                msg = self.create_message()
            # Check if messages available
            if msg is not '':
                # Add length to beginning of the message
                full_msg = self.add_length_to_msg(msg)

                # Check that socket is available
                if self.s:
                    try:
                        self.socket_lock.acquire()
                        # Try to send message and empty data container
                        self.s.send(full_msg.encode('utf-8'))
                        self.socket_lock.release()

                    except socket.timeout:
                        # Connection timeout
                        self.socket_lock.release()
                        logger.warn("Connection timeout when sending data")

                    except socket.error as e:
                        self.socket_lock.release()
                        # Other socket errors
                        self.connection_ok = False

                        # Broken pipe error or connection reset by peer
                        if e.errno == errno.EPIPE or e.errno == errno.ECONNRESET or errno.EWOULDBLOCK:
                            logger.warn("Connection broken, trying to reconnect")
                            self.socket_lock.acquire()
                            self.init_connection(retries=-1)
                            self.socket_lock.release()

                        else:
                            logger.warn(e)

                # If socket not available, use dummy connection
                else:
                    logger.warn('Using dummy connection')
                    logger.debug(msg)

                # If sending is limited, sleep until allowed to send next packet
                if self.limit_sending:
                    time.sleep(1/self.max_freq)
            else:
                time.sleep(0.05)
