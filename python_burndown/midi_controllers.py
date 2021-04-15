from .animation import WaveformType, AnimationTarget
from .beam_matrix_minder import (
    Idle,
    BeamSave,
    LookSave,
    Delete,
    LookEdit,
    ButtonEmpty,
    ButtonBeam,
    ButtonLook,
    BeamMatrixMinder,
)
from bidict import bidict
from collections import namedtuple
import logging
from .midi import NoteOnMapping, NoteOffMapping, ControlChangeMapping

def _build_grid_button_map(page):
    mapping = {}
    col_offset = BeamMatrixMinder.col_per_page * page
    for row in range(BeamMatrixMinder.n_rows):
        for column in range(BeamMatrixMinder.col_per_page):
            mapping[(row, column+col_offset)] = NoteOnMapping(column, row + 0x35)
    return bidict(mapping)


class MidiController (object):
    """Base class for midi controllers."""

    def __init__(self, mi, midi_out):
        self.controls = {}
        self.mi = mi
        mi.controllers.add(self)

        self.midi_out = midi_out

        self.setup_controls()

    def setup_controls(self):
        """Subclasses should override this method to wire up controls."""
        pass

    def add_controls(self, control_map, callback):
        """Attach a control map to a specified callback.

        Returns the bidirectional version of the control map.
        """
        self.set_callback_for_mappings(control_map.values(), callback)
        return bidict(control_map)

    def set_callback(self, mapping, callback):
        """Register a callback for a single mapping."""
        self.controls[mapping] = callback
        return mapping

    def set_callback_for_mappings(self, mappings, callback):
        """Manually register a callback for an iterable of mappings."""
        for mapping in mappings:
            self.controls[mapping] = callback

    def _set_radio_button(self, set_value, control_map):
        """Set only one out of a set of controls on."""
        for value, mapping in control_map.items():
            self.midi_out.send_from_mapping(mapping, int(value == set_value))



class BeamMatrixMidiController (MidiController):

    # maps named controls to midi messages
    control_map = bidict({
        BeamSave: NoteOnMapping(0, 0x52),
        LookSave: NoteOnMapping(0, 0x53),
        Delete: NoteOnMapping(0, 0x54),
        LookEdit: NoteOnMapping(0, 0x56)
    })

    BeamMatrixLEDState = namedtuple(
        "BeamMatrixLEDState", (BeamSave, LookSave, LookEdit, Delete))

    state_to_led_state_map = {
        Idle: BeamMatrixLEDState(0, 0, 0, 0),
        BeamSave: BeamMatrixLEDState(2, 0, 0, 0),
        LookSave: BeamMatrixLEDState(0, 2, 0, 0),
        LookEdit: BeamMatrixLEDState(0, 0, 2, 0),
        Delete: BeamMatrixLEDState(0, 0, 0, 2),
    }

    button_state_value_map = {
        ButtonEmpty: (0, 1), # off, red
        ButtonLook: (1, 1), # on, red
        ButtonBeam: (1, 2) # on, orange
    }

    def __init__(self, mi, midi_out, page=0):
        self.page = page
        super(BeamMatrixMidiController, self).__init__(mi, midi_out)

    def setup_controls(self):
        self.grid_button_map = _build_grid_button_map(self.page)
        # the controls which will be registered with the midi service
        self.set_callback_for_mappings(
            self.grid_button_map.values(), self.handle_grid_button)
        self.set_callback_for_mappings(
            self.control_map.values(), self.handle_state_button)

    def column_in_range(self, col):
        """Return True if this column is on the page assigned to this controller."""
        col_count = BeamMatrixMinder.col_per_page
        first_col = col_count * self.page
        last_col = first_col + col_count - 1
        return col >= first_col and col <= last_col

    def handle_grid_button(self, mapping, payload):
        row, col = self.grid_button_map.inv[mapping]
        self.mi.grid_button_press(row, col)

    def handle_state_button(self, mapping, payload):
        self.mi.state_toggle(self.control_map.inv[mapping])

    def set_beam_matrix_state(self, state):
        """Send UI update commands based on the beam matrix state."""
        led_state = self.state_to_led_state_map[state]
        message_mappings = tuple(
            (mapping, getattr(led_state, control))
            for control, mapping in self.control_map.items())
        self.midi_out.send_from_mappings(message_mappings)

    def set_button_state(self, row, column, state):
        # ignore updates for other pages
        if not self.column_in_range(column):
            return

        control_map = self.grid_button_map[(row, column)]
        status, color = self.button_state_value_map[state]
        if status == 0:
            val = 0
        elif status == 1:
            val = color*2 + 1
        elif state == 2:
            val = (color + 1)*2
        else:
            val = 0

        self.midi_out.send_from_mapping(control_map, val)

