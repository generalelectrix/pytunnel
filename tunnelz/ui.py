from functools import wraps
from weakref import WeakSet


class UiProperty (object):
    """Descriptor for creating observed properties."""
    def __init__(self, initial_value, callback_name, **kwargs):
        self.val = initial_value
        self.callback_name = callback_name
        self.kwargs = kwargs
    def __get__(self, obj, objtype):
        return self.val

    def __set__(self, obj, val):
        self.val = val
        for controller in obj.controllers:
            getattr(controller, self.callback_name)(val, **self.kwargs)

class UiModelProperty (object):
    """Descriptor for creating UI-observed properties of model attributes."""
    def __init__(self, attribute, callback_name=None, **kwargs):
        self.attribute = attribute
        self.callback_name = callback_name if callback_name is not None else attribute
        self.kwargs = kwargs
    def __get__(self, obj, objtype):
        return getattr(obj.model, self.attribute)

    def __set__(self, obj, val):
        print "setting {}.{} to {}".format(obj.model, self.attribute, val)
        setattr(obj.model, self.attribute, val)
        for controller in obj.controllers:
            getattr(controller, self.callback_name)(val, **self.kwargs)


class UserInterfaceMeta (type):
    """Metaclass for user interface creation.

    Ensures that various class-level attributes are initialized separately for
    each UI class.  Provides
    """
    def __new__(cls, clsname, bases, dct):
        dct['model_properties'] = model_properties = set()
        dct['ui_properties'] = ui_properties = set()

        for value in dct.itervalues():
            if isinstance(value, UiProperty):
                ui_properties.add(value)
            elif isinstance(value, UiModelProperty):
                model_properties.add(value)

        inst = super(UserInterfaceMeta, cls).__new__(cls, clsname, bases, dct)

        return inst


class UserInterface (object):
    """Base class for UIs.  Mostly responsible for implementing Observer.

    Maintains observing controllers using a weak reference set.
    """
    __metaclass__ = UserInterfaceMeta
    def __init__(self, model):
        """Initialize a user interface to an underlying model object."""
        self.model = model
        self.controllers = WeakSet()

    def swap_model(self, model):
        """Swap in a new model object and reinitialize controllers."""
        self.model = model
        self.initialize()

    def update_controllers(self, method, *args, **kwargs):
        """Call a named method on the controllers."""
        for controller in self.controllers:
            getattr(controller, method)(*args, **kwargs)

    def initialize(self):
        for prop in self.model_properties:
            val = getattr(self.model, prop.attribute)
            for controller in self.controllers:
                getattr(controller, prop.callback_name)(val, **prop.kwargs)
        for prop in self.ui_properties:
            val = prop.val
            for controller in self.controllers:
                getattr(controller, prop.callback_name)(val, **prop.kwargs)


def ui_method(callback_name, result_filter_func=None, **decoargs):
    """Decorator to make a method act something like a ui property.

    Only use this decorator on methods in classes which subclass UserInterface.

    The wrapped method will be called.  The value it returns will be passed
    through an optional result_filter_func before being passed to the
    observing controllers by calling their callback_name method with the
    filtered result as the first argument, as well as any optional keyword
    arguments passed to this decorator.  The original return value will then be
    returned.
    """
    def ui_method_decorator(method):
        @wraps(method)
        def ui_method_wrapper(self, *args, **kwargs):
            filtered_result = result = method(self, *args, **kwargs)
            if result_filter_func is not None:
                filtered_result = result_filter_func(result)
            for controller in self.controllers:
                getattr(controller, callback_name)(filtered_result, **decoargs)
            return result
        return ui_method_wrapper
    return ui_method_decorator