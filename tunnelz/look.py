from .beam import Beam

class Look (Beam):
    """A look is a beam that is actually a composite of several beams."""

    def __init__(self, layers):
        """Construct a new look from the contents of a mixer.

        This constructor copies everything handed to it.

        layers, levels, and masks are all lists of the mixer channel values.
        """
        super(Look, self).__init__()
        self.layers = [layer.copy() for layer in layers]

    def copy(self):
        """Return a copy of this look."""
        return Look(self.layers)

    def display(self, level_scale, as_mask):
        """Draw all the Beams in this Look.

        level: int in [0, 255]
        as_mask: boolean
        """

        for layer in self.layers:
            # only draw a layer if it isn't off
            level = layer.level
            if level != 0:
                scaled_level = level_scale * level / 255
                layer.beam.display(scaled_level, as_mask or level.mask)