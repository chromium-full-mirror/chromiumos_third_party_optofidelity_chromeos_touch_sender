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
import configparser
import logging.config
import os
import json

logger = logging.getLogger(__name__)


def check_port(port):
    if type(port) is not int:
        raise ValueError('Port is not integer, but {}'.format(type(port)))
    if not 0 < port < 65536:
        raise ValueError('Invalid port number: {}'.format(port))


def get_file_config(config_file_name):

    ip = port = device_type = max_freq = None
    conf = {}

    config = configparser.ConfigParser()
    logger.debug("Reading configuration from file: {}".format(config_file_name))

    try:
        config.read(config_file_name)
    except configparser.ParsingError as e:
        logger.warn('Error parsing configuration file {}'.format(config_file_name))
        raise ValueError(e.message.strip())

    if not config.sections():
        raise RuntimeError(
            'Configuration file does not exist or exists with invalid content')

    # Loop through all sections in config file
    # If configuration file could not be read, config.sections() will be empty.
    for section in config.sections():
        # Loop through each sections items
        for item in config.items(section):
            # Add each item to config.
            # If same item appears twice, use later one (overwrite old one)
            conf[item[0]] = config.get(section, item[0])

    msg = ''
    for key in conf:
        msg += '\n{:>15}: {}'.format(key, conf[key])

    logger.debug('Using configuration:' + msg)

    return conf


def write_config_file(filename, section, **kwargs):
    """ Function for writing keyword arguments to configuration file
    """
    config = configparser.ConfigParser()
    config.add_section(section)

    for key in kwargs:
        config.set(section, key, kwargs[key])

    with open(filename, 'wb') as configfile:
        config.write(configfile)


def get_json_config(json_string):
    """ Read json and return dict
    """
    try:
        json_dict = json.loads(json_string)
        return json_dict
    except ValueError as e:
        logger.warn('Error parsing JSON string')
        raise

def json_from_dict(conf):
    conf_str = json.dumps(conf)
    return conf_str

def setup_logging(default_path='config/logging.json', default_level=logging.INFO):
    """Setup logging configuration
    """

    path = default_path
    if os.path.exists(path):
        with open(path, 'rt') as f:
            try:
                config = json.load(f)
            except ValueError as e:
                logger.warn('Error loading JSON from file {}'.format(path))
                raise
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


def str2bool(s):
    """ Transform string to boolean
    """
    return s.lower() in ("true", "1")


if __name__ == '__main__':
    setup_logging()
    conf = get_config('../../config/test.cfg')
