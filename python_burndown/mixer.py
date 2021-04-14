from .tunnel import Tunnel
from .look import Look
from .model_interface import ModelInterface
import logging

class MixerMI (ModelInterface):
    """Handle model interactions for the mixer."""
    def __init__(self, mixer):
        super(MixerMI, self).__init__(mixer)
        self.mixer = mixer

    def put_beam_in_layer(self, layer, beam):
        """Replace the beam in numbered layer with this beam."""
        self.mixer.put_beam_in_layer(layer, beam)
        self.update_controllers('set_look_indicator', layer, isinstance(beam, Look))

    def set_look(self, look):
        """Set the current look, clobbering mixer state."""
        self.mixer.set_look(look)
        self.initialize()

    def set_level(self, layer, level):
        self.mixer.set_level(layer, level)
        self.update_controllers('set_level', layer, level)

    def set_bump_button(self, layer, state):
        if state:
            self.mixer.bump_on(layer)
        else:
            self.mixer.bump_off(layer)
        self.update_controllers('set_bump_button', layer, state)

    def toggle_mask_state(self, layer):
        state = self.mixer.toggle_mask_state(layer)
        self.update_controllers('set_mask_button', layer, state)

    def toggle_video_channel(self, layer, channel):
        state = self.mixer.toggle_video_channel(layer, channel)
        self.update_controllers('set_video_channel', layer, channel, state)


class Mixer (object):


    @property
    def layer_count(self):
        return len(self.layers)

    def get_beam_from_layer(self, layer):
        return self.layers[layer].beam

    def get_copy_of_current_look(self):
        """Return a frozen copy of the entire current look."""
        return Look(self.layers)

    def set_look(self, look):
        """Unload a look into the mixer state, clobbering current state."""
        # It appears this method was ill-formed in the Java version, as a
        # incoming look's mask and level state does not clobber the mixer.
        # Seems like mask at least should clobber, or your ugly mask layer
        # becomes a positive.  Hell, here, I'll fix it right now.

        self.layers = look.copy().layers
