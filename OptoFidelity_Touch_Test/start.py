#!/usr/bin/env python

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

import sys, os
import subprocess, signal
import logging
from optparse import OptionParser

from chromeos_tester.eventsenders import SnapshotSender
from chromeos_tester.util import config_utils as util

def is_only_instance():
    curr_pid = os.getpid()
    count = 0
    pids = []
    p = subprocess.Popen(["pgrep", '-af', 'python {}'.format(__file__)], stdout=subprocess.PIPE)
    for process in p.stdout:
        pid = int(process.strip().split(' ')[0])
        count += 1
        if pid != curr_pid:
            pids.append(pid)
    if count > 1:
        print("Closing other instances of this script before continuing.")
        print("PIDs to be killed: {}".format(pids))

        # If running remotely with bat-script and putty plink, cannot give user input
        # kill_now = raw_input('Kill other instances now? (y/n)>> ')
        kill_now = 'y'
        if kill_now.lower() == 'y':
            for pid in pids:
                os.kill(pid, signal.SIGTERM)
        else:
            return False
    return True


if __name__ == '__main__':

    if not is_only_instance():
        print("Other instances running, exiting this process")
        sys.exit()

    curr_path = os.path.dirname(os.path.realpath(__file__))

    parser = OptionParser()

    parser.add_option("-c", "--config", dest="config", action='store',
                        default=curr_path + os.sep + 'config/default.cfg',
                        help="Path to configuration file")
    parser.add_option("-l", "--log_config", dest="log_conf", action="store",
                        default=curr_path + os.sep + 'config/logging.json',
                        help="Path to logging configuration file")

    (options, args) = parser.parse_args()

    try:

        util.setup_logging(options.log_conf)

        logging.info('Logging started')

        init = False

        Sender = SnapshotSender(options.config)

        init = True

        Sender.run()

        Sender.shutdown()

    except KeyboardInterrupt:
        logging.info('User interrupt, shutting down')
        if init: Sender.shutdown()

    except ValueError as e:
        logging.error(e)

    except BaseException as e:
        logging.warn(e)
        logging.error('Unknown error, shutting down')

        if init: Sender.shutdown()

        raise
