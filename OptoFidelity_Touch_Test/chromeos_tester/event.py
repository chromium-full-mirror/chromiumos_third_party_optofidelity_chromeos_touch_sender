# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE_chromiumos file.

from evdev import ecodes

class MtEvent(object):
  """ Class that holds the a single MT event """

  LEAVING_TRACKING_ID = -1

  def __init__(self, timestamp, event_type=ecodes.EV_SYN,
               event_code=None, value=None):
    self.timestamp = timestamp
    self.event_type = event_type
    self.event_code = event_code
    self.value = value

  def is_ABS_MT_TRACKING_ID(self):
    """ Is this event ABS_MT_TRACKING_ID? """
    return (self.event_type == ecodes.EV_ABS and
            self.event_code == ecodes.ABS_MT_TRACKING_ID)

  def is_ABS_MT_SLOT(self):
    """ Is this event ABS_MT_SLOT? """
    return (self.event_type == ecodes.EV_ABS and
            self.event_code == ecodes.ABS_MT_SLOT)

  def is_ABS_MT_POSITION_X(self):
    """ Is this event ABS_MT_POSITION_X? """
    return (self.event_type == ecodes.EV_ABS and
            self.event_code == ecodes.ABS_MT_POSITION_X)

  def is_ABS_X(self):
    """ Is this event ABS_X? """
    return self.event_type == ecodes.EV_ABS and self.event_code == ecodes.ABS_X

  def is_ABS_MT_POSITION_Y(self):
    """ Is this event ABS_MT_POSITION_Y? """
    return (self.event_type == ecodes.EV_ABS and
            self.event_code == ecodes.ABS_MT_POSITION_Y)

  def is_ABS_Y(self):
    """ Is this event ABS_Y? """
    return self.event_type == ecodes.EV_ABS and self.event_code == ecodes.ABS_Y

  def is_ABS_MT_PRESSURE(self):
    """ Is this event ABS_MT_PRESSURE? """
    return (self.event_type == ecodes.EV_ABS and
            self.event_code == ecodes.ABS_MT_PRESSURE)

  def is_ABS_PRESSURE(self):
    """ Is this event ABS_PRESSURE? """
    return (self.event_type == ecodes.EV_ABS and
            self.event_code == ecodes.ABS_PRESSURE)

  def is_ABS_MT_TOUCH_MAJOR(self):
    """ Is this event ABS_MT_TOUCH_MAJOR? """
    return (self.event_type == ecodes.EV_ABS and
            self.event_code == ecodes.ABS_MT_TOUCH_MAJOR)

  def is_ABS_MT_DISTANCE(self):
    """ Is this event ABS_MT_DISTANCE? """
    return (self.event_type == ecodes.EV_ABS and
            self.event_code == ecodes.ABS_MT_DISTANCE)

  def is_ABS_TILT_X(self):
    """ Is this event ABS_TILT_X? """
    return (self.event_type == ecodes.EV_ABS and
            self.event_code == ecodes.ABS_TILT_X)

  def is_ABS_TILT_Y(self):
    """ Is this event ABS_TILT_Y? """
    return (self.event_type == ecodes.EV_ABS and
            self.event_code == ecodes.ABS_TILT_Y)

  def is_MSC_SCAN(self):
    return self._is_EV_MSC and self.event_code == ecodes.MSC_SCAN

  def _is_EV_KEY(self):
    """ Is this an EV_KEY event? """
    return self.event_type == ecodes.EV_KEY

  def _is_EV_MSC(self):
    """ Is this an EV_MSC event? """
    return self.event_type == ecodes.EV_MSC

  def is_BTN_LEFT(self):
    """ Is this event BTN_LEFT? """
    return self._is_EV_KEY() and self.event_code == ecodes.BTN_LEFT

  def is_BTN_TOOL_PEN(self):
    """ Is this event BTN_TOOL_PEN? """
    return self._is_EV_KEY() and (self.event_code == ecodes.BTN_TOOL_PEN or
                                  self.event_code == ecodes.BTN_TOOL_RUBBER or
                                  self.event_code == ecodes.BTN_STYLUS or
                                  self.event_code == ecodes.BTN_STYLUS2)

  def is_BTN_TOUCH(self):
    """ Is this event BTN_TOUCH? """
    return self._is_EV_KEY() and self.event_code == ecodes.BTN_TOUCH

  def is_SYN_MT_REPORT(self):
    """ is this event is SYN_REPORT? """
    return (self.event_type == ecodes.EV_SYN and
            self.event_code == ecodes.SYN_MT_REPORT)

  def is_SYN_REPORT(self):
    """ is this event is SYN_REPORT? """
    return (self.event_type == ecodes.EV_SYN and
            self.event_code == ecodes.SYN_REPORT)

  def is_SYN_DROPPED(self):
    """ is this event SYN_DROPPED = device buffer overrun """
    return (self.event_type == ecodes.EV_SYN and
            self.event_code == ecodes.SYN_DROPPED)

  def __str__(self):
    """ Return a human-readable string version of the event.  If the event codes
    are not found in the translation list, simply use the even code numbers.
    """
    if self.is_SYN_REPORT():
      return '%0.5f\t-- SYN --' % self.timestamp
    ev_type = ecodes.EV.get(self.event_type, str(self.event_type))
    ev_string = str(self.event_code)
    if self.event_type in ecodes.EV:
      ev_string = ecodes.bytype[self.event_type].get(self.event_code, ev_string)
      # When multiple names are defined to the same code, ev_string will be a
      # list of valid names.  Choose the first.
      if isinstance(ev_string, list):
          ev_string = ev_string[0]
    return '%0.5f\t%s\t%s\t%d' % (self.timestamp, ev_type, ev_string,
                                  self.value)
