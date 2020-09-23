# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE_chromiumos file.
import math
from collections import namedtuple
from .event import MtEvent, EV_ABS, ABS_MT_TRACKING_ID


MtFinger = namedtuple('MtFinger', ['tid', 'syn_time', 'x', 'y', 'pressure'])
MtSnapshot = namedtuple('MtSnapshot', ['syn_time', 'button_pressed',
                                       'fingers', 'raw_events'])

# Touch actions
ACTION_DOWN         = 0
ACTION_UP           = 1
ACTION_MOVE         = 2
ACTION_CANCEL       = 3
ACTION_HOVER_DOWN   = 9
ACTION_HOVER_MOVE   = 7
ACTION_HOVER_UP     = 10

class MtStateMachine(object):
    """ This is an abstract base class that defines the interface of a multitouch
    state machine.  This class should never be instantiated directly, but rather
    any actual state machines should derive from this class to guarantee that it
    conforms to the same interfaces.
    """
    PRESSURE_FROM_MT_PRESSURE = 'from_mt_pressure'
    PRESSURE_FROM_MT_TOUCH_MAJOR = 'from_mt_touch_major'
    PRESSURE_FROM_NOWHERE = 'from_nowhere'
    PRESSURE_SOURCES = [PRESSURE_FROM_MT_PRESSURE, PRESSURE_FROM_MT_TOUCH_MAJOR,
                        PRESSURE_FROM_NOWHERE]


    def __init__(self, pressure_src):
        """ Setup the parts of the state machine that are uniform across all MT
        protocol state machines.

        Currently this is only one option: pressure source.  This tells the state
        machine where to get the "pressure" readings from.  While, the default
        way is to use MT_PRESSURE messages, some touchpads/screens use the
        MT_TOUCH_MAJOR message instead or do not report it at all.  This parameter
        allows you to specify which you want the state machine to use.
        """
        if pressure_src not in MtStateMachine.PRESSURE_SOURCES:
            raise ValueError('The pressure source "%s" is not valid.')
        self.pressure_src = pressure_src

def add_event(self, event):
    raise NotImplementedError('Error: add_event() not implemented.')

def get_current_snapshot(self, request_data_ready=True):
    raise NotImplementedError('Error: get_current_snapshot() not implemented.')


class MtaStateMachine(MtStateMachine):
    """ The state machine for MTA events

    This class accepts MtEvents via the add_event() member function and maintains
    the state that an MTA system would.  MTA is slightly different than MTB, but
    uses similar events.  Without delta compression, MTA can get rid of the
    concept of slots, since all the finger data is reported before each SYN_REPORT
    and the fingers themselves are separated byt SYN_MT_REPORTS instead of a
    new SLOT.

    Note that because our system expects new fingers to have new TIDs and in MTA
    this is not the case (they reuse TIDs all the time) the MtaStateMachine
    keeps track of which TIDs have already been used and remaps them when
    it detects a repeated TID to an unused value to maintain transparency
    between MTB and MTA.
    """
    def __init__(self, pressure_src=MtStateMachine.PRESSURE_FROM_MT_PRESSURE):
        # This dictionary maps the raw (non-unique) tids reported in the events to
        # new (unique) tids so we can easily differentiate any two fingers even if
        # there is a gap of time inbetween them.
        self.tid_mappings = {}
        self.next_unique_tid = 0

        self.button_pressed = False
        self.last_snapshot = None

        self._clear()

        MtStateMachine.__init__(self, pressure_src)

    def _clear(self):
        # Clear out the state for the current fingers
        self.fingers_data = []
        self.raw_events_since_last_syn = []
        self.tid = self.x = self.y = self.pressure = self.touch_major = None

    def add_event(self, event):
        self.raw_events_since_last_syn.append(event)

        # If this is the end of the information for all the fingers for this report
        if event.is_SYN_REPORT():
            # First build up the snapshot
            fingers = []
            for tid, x, y, touch_major in self.fingers_data:
                mapped_tid = self.tid_mappings[tid]
                fingers.append(MtFinger(mapped_tid, event.timestamp, x, y, touch_major))
            self.last_snapshot = MtSnapshot(event.timestamp, self.button_pressed,
                                            fingers, self.raw_events_since_last_syn)

            # Delete the tid mappings for any leaving fingers
            # Find all the raw tids that have currently been reported
            raw_tids_used = set([raw_tid for raw_tid, _, _, _ in self.fingers_data])
            # Detect any mappings that are for fingers no longer on the pad
            leaving_raw_tids = [raw_tid for raw_tid in self.tid_mappings
                                if raw_tid not in raw_tids_used]
            # Remove those out-dated mappings from the mapping dictionary
            for raw_tid in leaving_raw_tids:
                del self.tid_mappings[raw_tid]

            # Then clear out the fingers_data since this starts a new snapshot
            self._clear()

        # If this is the end of a finger's information stash all the data about it
        # until the end of the data for all the fingers
        elif event.is_SYN_MT_REPORT():
            if self.pressure_src == MtStateMachine.PRESSURE_FROM_MT_TOUCH_MAJOR:
                pressure = self.touch_major
            elif self.pressure_src == MtStateMachine.PRESSURE_FROM_NOWHERE:
                pressure = 1
            else:
                pressure = self.pressure

            if all([v is not None for v in (self.tid, self.x, self.y, pressure)]):
                self.fingers_data.append((self.tid, self.x, self.y, pressure))

        # Otherwise, check what information it's giving us and store it
        elif event.is_ABS_MT_TRACKING_ID():
            self.tid = event.value
            if self.tid not in self.tid_mappings:
                self.tid_mappings[self.tid] = self.next_unique_tid
                self.next_unique_tid += 1
        elif event.is_ABS_MT_POSITION_X():
            self.x = event.value
        elif event.is_ABS_MT_POSITION_Y():
            self.y = event.value
        elif event.is_ABS_MT_PRESSURE():
            self.pressure = event.value
        elif event.is_ABS_MT_TOUCH_MAJOR():
            self.touch_major = event.value
        elif event.is_BTN_LEFT():
            self.button_pressed = (event.value == 1)

    def get_current_snapshot(self, request_data_ready=True):
        return self.last_snapshot


class MtbStateMachine(MtStateMachine):
    """ The state machine for MTB events.

    It traces the slots, tracking IDs, x coordinates, y coordinates, etc. If
    these values are not changed explicitly, the values are kept across events.

    Note that the kernel driver only reports what is changed. Due to its
    internal state machine, it is possible that either x or y in
    self.point[tid] is None initially even though the instance has been created.
    """
    DUMMY_TRACKING_ID = 999999

    def __init__(self, pressure_src=MtStateMachine.PRESSURE_FROM_MT_PRESSURE):
        # Set the default slot to 0 as it may not be displayed in the MT events
        #
        # Some abnormal event files may not display the tracking ID in the
        # beginning. To handle this situation, we need to initialize
        # the following variables:  slot_to_tid, point
        #
        # As an example, refer to the following event file which is one of
        # the golden samples with this problem.
        #   tests/data/stationary_finger_shift_with_2nd_finger_tap.dat
        self.reset()
        MtStateMachine.__init__(self, pressure_src)

    def add_event(self, event):
        """ Update the internal states with the input MtEvent  """
        if self.is_first_event and not event.is_ABS_MT_TRACKING_ID():
            self.add_event(MtEvent(event.timestamp,
                                   EV_ABS, ABS_MT_TRACKING_ID,
                                   MtbStateMachine.DUMMY_TRACKING_ID))
        self.is_first_event = False

        self.raw_events_since_last_syn.append(event)

        # Note: The physical click button is not associated with any finger/slot
        if event.is_BTN_LEFT():
            self.button_pressed = (event.value == 1)

        # Handle all the finger-related updates below here
        # Switch the slot.
        elif event.is_ABS_MT_SLOT():
            self.slot = event.value

        # Update tracking ID, noting if the slot is no longer used
        elif event.is_ABS_MT_TRACKING_ID():
            self.slots_modified.add(self.slot)
            if event.value == MtEvent.LEAVING_TRACKING_ID:
                # Create unique negative ID for leaving tracking id
                self.tid[self.slot] = event.value - self.slot
                self.slots_in_use.discard(self.slot)
            else:
                self.tid[self.slot] = event.value
                self.slots_in_use.add(self.slot)

        # Update the x, y, pressure, etc values for a given slot
        elif event.is_ABS_MT_POSITION_X():
            self.x[self.slot] = event.value
        elif event.is_ABS_MT_POSITION_Y():
            self.y[self.slot] = event.value
        elif event.is_ABS_MT_PRESSURE():
            self.pressure[self.slot] = event.value
        elif event.is_ABS_MT_TOUCH_MAJOR():
            self.touch_major[self.slot] = event.value
        elif event.is_ABS_MT_DISTANCE():
            self.distance[self.slot] = event.value

        # Use the SYN_REPORT time as the snapshot time
        elif event.is_SYN_REPORT():
            self.syn_time = event.timestamp
            self.last_snapshot = self._build_current_snapshot()
            self.raw_events_since_last_syn = []

    def _update_current_actions(self):
        # By default set all slots used to ACTON_MOVE
        self.actions = {}
        for slot in self.slots_in_use:
            self.actions[slot] = ACTION_MOVE
        # If slot was added or discarded, set according action status
        for slot in self.slots_modified:
            if self.tid[slot] <= MtEvent.LEAVING_TRACKING_ID:
                self.actions[slot] = ACTION_UP
            else:
                self.actions[slot] = ACTION_DOWN

    def _build_current_snapshot(self):
        """Build current packet's data including x, y, pressure, and
        the syn_time for all tids.
        """
        self._update_current_actions()
        current_fingers = []
        for slot in self.slots_in_use.union(self.slots_modified):
            tid = self.tid.get(slot, None)
            x = self.x.get(slot, None)
            y = self.y.get(slot, None)
            distance = self.distance.get(slot, None)

            # Skip any fingers that are hovering (they have a distance)
            if distance:
                continue

            if self.pressure_src == MtStateMachine.PRESSURE_FROM_MT_TOUCH_MAJOR:
                pressure = self.touch_major.get(slot, 0)
            elif self.pressure_src == MtStateMachine.PRESSURE_FROM_NOWHERE:
                pressure = 0
            else:
                pressure = self.pressure.get(slot, 0)

            data_ready = all([v is not None for v in
                              (x, y, pressure, tid, self.syn_time)])
            if data_ready:
                finger = MtFinger(tid, self.syn_time, x, y, pressure)
                current_fingers.append(finger)

        current_snapshot = MtSnapshot(self.syn_time, self.button_pressed,
                                      current_fingers,
                                      self.raw_events_since_last_syn)

        # Empty container for modified slots
        self.slots_modified = set()
        return current_snapshot

    def get_current_snapshot(self):
        return self.last_snapshot

    def get_current_action_state(self):
        return self.actions

    def get_slot_of_tid(self, tid):
        return list(self.tid.keys())[list(self.tid.values()).index(tid)]

    def is_active(self):
        return self.button_pressed

    def reset(self):
        self.slot = 0
        self.slots_in_use = set()
        self.slots_modified = set()  # Slots that are new or discarded
        self.tid = {}
        self.x = {}
        self.y = {}
        self.distance = {}
        self.pressure = {}
        self.touch_major = {}
        self.syn_time = None
        self.leaving_slots = []
        self.button_pressed = False
        self.raw_events_since_last_syn = []
        self.last_snapshot = None
        self.is_first_event = True
        self.actions = {}
        self.buffer_overrun = False


class StylusStateMachine(MtStateMachine):
    """ State machine for parsing simplified stylus protocol.
    This only supports a single stylus, and ignores any hovering reports, just
    reporting snapshots when the stylus is touching the surface.
    """
    def __init__(self, pressure_src=MtStateMachine.PRESSURE_FROM_NOWHERE):
        self.reset()
        MtStateMachine.__init__(self, pressure_src)

    def __update_hover_state(self):
        self.is_hovering = not self.btn_touch and self.btn_tool_pen

    def __update_action_state(self):
        # By default, touch moved or touch_hovering action
        if self.is_hovering: self.action = ACTION_HOVER_MOVE
        else: self.action = ACTION_MOVE

        if self.touch_updated and self.btn_touch:
            # Touch started action
            self.action = ACTION_DOWN
        elif self.touch_updated and self.is_hovering:
            # Tool hovering, touch ended action
            self.action = ACTION_UP
        elif self.is_hovering and self.tool_updated:
            # Tool started hovering
            self.action = ACTION_HOVER_DOWN
        elif self.is_hovering:
            # Tool hovering
            self.action = ACTION_HOVER_MOVE
        elif self.tool_updated and not self.is_hovering:
            # Tool hovering ended
            self.action = ACTION_HOVER_UP

        if self.touch_updated and self.tool_updated and \
                not self.btn_touch and not self.btn_tool_pen:
            # Tool and touch disappeared in same event, touch cancelled
            self.action = ACTION_CANCEL

    def add_event(self, event):
        self.raw_events_since_last_syn.append(event)
        if event.is_ABS_X():
            self.x = event.value
        elif event.is_ABS_Y():
            self.y = event.value
        elif event.is_ABS_PRESSURE():
            self.p = event.value
        elif event.is_BTN_TOUCH():
            self.btn_touch = (event.value == 1)
            self.touch_updated = True
            self.__update_hover_state()
        elif event.is_BTN_TOOL_PEN():
            self.btn_tool_pen = (event.value == 1)
            self.tool_updated = True
            self.__update_hover_state()
            # if event.value == 0:
            #   self.x = self.y = self.p = None
        elif event.is_ABS_TILT_X():
            self.tilt_x = event.value
        elif event.is_ABS_TILT_Y():
            self.tilt_y = event.value
        elif event.is_MSC_SCAN():
            self.scan = event.value
        elif event.is_SYN_DROPPED():
            self.buffer_overrun = True

        elif event.is_SYN_REPORT():
            self.__update_action_state()
            current_fingers = None

            if self.buffer_overrun:
                self.last_snapshot = None
                self.touch_updated = self.tool_updated = False
                self.__update_hover_state()
                return
            # self.last_snapshot = MtSnapshot(event.timestamp, False, [], self.raw_events_since_last_syn)
            # self.raw_events_since_last_syn = []
            if self.btn_touch:
                # Stylus touching screen
                current_fingers = [MtFinger(0, event.timestamp, self.x, self.y, self.p)]
                self.last_report_was_empty = False
            elif self.btn_tool_pen or self.tool_updated:
                # Stylus not touching screen but visible => hovering
                current_fingers = [MtFinger(0, event.timestamp, self.x, self.y, 0.0)]
                self.last_report_was_empty = False
            elif not self.last_report_was_empty:
                current_fingers = []
                self.last_report_was_empty = True

            if current_fingers is not None:
                self.last_snapshot = MtSnapshot(event.timestamp, False, current_fingers,
                                                self.raw_events_since_last_syn)
                self.raw_events_since_last_syn = []
            else:
                self.last_snapshot = None

            self.touch_updated = self.tool_updated = False

    def get_current_snapshot(self, request_data_ready=True):
        return self.last_snapshot

    def get_current_action_state(self):
        """ Returns current action in list to be compatible with multitouch devices
        """
        return [self.action]




    def get_tilt_and_yaw(self):
        tilt, yaw = 0, 0
        if self.tilt_x:
            tilt_x = math.radians(self.tilt_x)
        else:
            tilt_x = 0

        if self.tilt_y:
            tilt_y = math.radians(self.tilt_y)
        else:
            tilt_y = 0

        if tilt_x != 0 and tilt_y != 0:
            x = [math.sin(tilt_x), 0, math.cos(tilt_x)]
            y = [0, math.sin(tilt_y), math.cos(tilt_y)]
            scaler = x[2] / y[2]
            y = [p/scaler for p in y]

            comb = [x[0], y[1], x[2]]

            s = 0
            for i in comb:
                s += i**2
            hyp = math.sqrt(s)

            d = math.sqrt(comb[0]**2 + comb[1]**2)

            tilt = math.degrees(math.radians(90) - math.acos(d / hyp))

            yaw = math.degrees(math.atan2(-comb[1], comb[0]))

        elif tilt_x != 0:
            tilt = math.degrees(abs(tilt_x))
            yaw = 0 if tilt_x >= 0 else 180
        elif tilt_y != 0:
            tilt = math.degrees(abs(tilt_y))
            yaw = 90 if tilt_y <= 0 else -90

        return (tilt, yaw)

    def is_active(self):
        return self.btn_tool_pen

    def reset(self):
        self.x = self.y = self.p = self.tilt_x = self.tilt_y = self.last_snapshot = None
        self.touch_updated = self.tool_updated = self.buffer_overrun = False
        self.action = 0
        self.scan = None
        self.btn_touch = self.btn_tool_pen = self.is_hovering = False
        self.raw_events_since_last_syn = []
        self.last_report_was_empty = True

    def set_tilts_with_tilt_and_yaw(self, tilt, yaw):
        if tilt == 0:
            yaw = 0
        tilt = math.radians(tilt)
        yaw = math.radians(yaw)

        tilt_x = tilt * math.cos(yaw)
        tilt_y = tilt * math.sin(yaw)

        self.tilt_x = math.degrees(tilt_x)
        self.tilt_y = math.degrees(tilt_y)



if __name__ == '__main__':
    import random
    sm = StylusStateMachine()

    for i in range(361):
        t = random.randrange(0, 45)
        if t == 0:
            y = 0
        else:
            y = random.randrange(-180, 180)
            y = i - 180

        sm.set_tilts_with_tilt_and_yaw(t, y)
        print("#"*5)
        print("Set : ({}, {})".format(90 - t,y))
        print("Calc: {}".format(sm.get_tilt_and_yaw()))
