#
"""
Utility functions
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

#import importlib
import inspect
from pydoc import locate
import copy
import numpy as np

# pylint: disable=invalid-name, no-member, no-name-in-module

import tensorflow as tf
from tensorflow.python.framework import ops
from tensorflow.python.util import nest
from tensorflow.python.ops import rnn

from texar import context


MAX_SEQ_LENGTH = np.iinfo(np.int32).max  #TODO (zhiting): move to constants

## Some modules can be imported directly, e.g., `import tensorflow.train` fails.
## Such modules are treated in a special way in utils like `get_class` as below.
#_unimportable_modules = {
#    'tensorflow.train', 'tensorflow.keras.regularizers'
#}

def get_class(class_name, module_paths=None):
    """Returns the class based on class name.

    Args:
        class_name: Name or full path of the class to instantiate.
        module_paths: A list of paths to candidate modules to search for the
            class. This is used if the class cannot be located solely based on
            `class_name`. The first module in the list that contains the class
            is used.

    Returns:
        A class.

    Raises:
        ValueError: If class is not found based on :attr:`class_name` and
            :attr:`module_paths`.
    """
    class_ = locate(class_name)
    if (class_ is None) and (module_paths is not None):
        for module_path in module_paths:
            #if module_path in _unimportable_modules:
            # Special treatment for unimportable modules by directly
            # accessing the class
            class_ = locate('.'.join([module_path, class_name]))
            if class_ is not None:
                break
            #else:
            #    module = importlib.import_module(module_path)
            #    if class_name in dir(module):
            #        class_ = getattr(module, class_name)
            #        break

    if class_ is None:
        raise ValueError(
            "Class not found in {}: {}".format(module_paths, class_name))

    return class_


def get_instance(class_name, kwargs, module_paths=None):
    """Creates a class instance.

    Args:
        class_name: Name or full path of the class to instantiate.
        kwargs: A dictionary of arguments for the class constructor.
        module_paths: A list of paths to candidate modules to search for the
            class. This is used if the class cannot be located solely based on
            `class_name`. The first module in the list that contains the class
            is used.

    Returns:
        A class instance.

    Raises:
        ValueError: If class is not found based on :attr:`class_name` and
            :attr:`module_paths`.
        ValueError: If :attr:`kwargs` contains arguments that are invalid
            for the class construction.
    """
    # Locate the class
    class_ = get_class(class_name, module_paths)

    # Check validity of arguments
    class_args = set(inspect.getargspec(class_.__init__).args)
    for key in kwargs.keys():
        if key not in class_args:
            raise ValueError(
                "Invalid argument for class %s.%s: %s" %
                (class_.__module__, class_.__name__, key))

    return class_(**kwargs)


def get_instance_with_redundant_kwargs(
        class_name, kwargs, module_paths=None):
    """Creates a class instance.

    Only those keyword arguments in :attr:`kwargs` that are included in the
    class construction method are used.

    Args:
        class_name (str): Name or full path of the class to instantiate.
        kwargs (dict): A dictionary of arguments for the class constructor. It
            may include invalid arguments which will be ignored.
        module_paths (list of str): A list of paths to candidate modules to
            search for the class. This is used if the class cannot be located
            solely based on :attr:`class_name`. The first module in the list
            that contains the class is used.

    Returns:
        A class instance.

    Raises:
        ValueError: If class is not found based on :attr:`class_name` and
            :attr:`module_paths`.
    """
    # Locate the class
    class_ = get_class(class_name, module_paths)

    # Select valid arguments
    selected_kwargs = {}
    class_args = set(inspect.getargspec(class_.__init__).args)
    for key, value in kwargs.items():
        if key in class_args:
            selected_kwargs[key] = value

    return class_(**selected_kwargs)


def get_function(fn_name, module_paths=None):
    """Returns the function of specified name and module.

    Args:
        fn_name (str): Name of the function.
        module_paths (list of str): A list of paths to candidate modules to
            search for the function. This is used when the function cannot be
            located solely based on `fn_name`. The first module in the list
            that contains the function is used.

    Returns:
        A function.
    """
    fn = locate(fn_name)
    if (fn is None) and (module_paths is not None):
        for module_path in module_paths:
            #if module_path in _unimportable_modules:
            fn = locate('.'.join([module_path, fn_name]))
            if fn is not None:
                break
            #module = importlib.import_module(module_path)
            #if fn_name in dir(module):
            #    fn = getattr(module, fn_name)
            #    break

    if fn is None:
        raise ValueError(
            "Method not found in {}: {}".format(module_paths, fn_name))

    return fn


def call_function_with_redundant_kwargs(fn, kwargs):
    """Calls a function and returns the results.

    Only those keyword arguments in :attr:`kwargs` that are included in the
    function's argument list are used to call the function.

    Args:
        fn (function): The function to call.
        kwargs (dict): A dictionary of arguments for the class constructor. It
            may include invalid arguments which will be ignored.

    Returns:
        The returned results by calling :attr:`fn`.
    """
    # Select valid arguments
    selected_kwargs = {}
    fn_args = set(inspect.getargspec(fn).args)
    for key, value in kwargs.items():
        if key in fn_args:
            selected_kwargs[key] = value

    return fn(**selected_kwargs)


def get_default_arg_values(fn):
    """Gets the arguments and respective default values of a function.

    Only arguments with default values are included in the output dictionary.

    Args:
        fn (function): The function to inspect.

    Returns:
        dict: A dictionary that maps argument names (str) to their default
        values. The dictionary is empty if no arguments have default values.
    """
    argspec = inspect.getargspec(fn)
    if argspec.defaults is None:
        return {}
    num_defaults = len(argspec.defaults)
    return dict(zip(argspec.args[-num_defaults:], argspec.defaults))


#TODO(zhiting): support more modes.
# checkout: http://tflearn.org/layers/merge_ops/
def merge(values, mode, axis=0, name='merge'):
    """Merges tensors in a manner specified in :attr:`mode`.

    Args:
        values (list): A list of `Tensor` to merge.
        mode (str): Mode of the merge op. This can be:

            - :attr:`'concat'`: Concatenates tensors along one axis. \
              Tensors must have the same shape except for the dimension \
              specified in axis, which can have different sizes.
            - :attr:`'elemwise_sum'`: Outputs element-wise sum. \
              Tensors must have the same shape.
            - TODO ...
        axis (int): The axis to use in merging. Ignored in modes
            :attr:`"elemwise_sum"` ...

    Returns:
        The merged tensor.

    Raises:
        ValueError: If :attr:`values` is not a list of tensor or contains less
            than one tensor.
        ValueError: If :attr:`mode` is not one in the above list.
    """
    if not isinstance(values, list) or len(values) < 1:
        raise ValueError("`values` must be a list of Tensors.")

    with tf.name_scope(name):
        if mode == 'concat':
            output = tf.concat(values=values, axis=axis)
        elif mode == 'elemwise_sum':
            output = values[0]
            for v in values[1:]:
                output = tf.add(output, v)
        else:
            raise ValueError("Unkown merge mode: %s." % str(mode))

    return output


def switch_dropout(dropout_keep_prob, is_train=None):
    """Turns off dropout when not in training mode.

    Args:
        dropout_keep_prob: Dropout keep probability in training mode
        is_train: Boolean Tensor indicator of the training mode. Dropout is
            activated if `is_train=True`. If `is_train` is not given, the mode
            is inferred from the global mode.

    Returns:
        A unit Tensor that equals the dropout keep probability in training mode,
        and 1 in eval mode.
    """
    if is_train is None:
        return 1. - (1. - dropout_keep_prob) * tf.to_float(context.is_train())
    else:
        return 1. - (1. - dropout_keep_prob) * tf.to_float(is_train)


def transpose_batch_time(inputs):
    """Transposes inputs between time-major and batch-major.

    Args:
        inputs: A Tensor of shape `[batch_size, max_time, ...]` (batch-major)
            or `[max_time, batch_size, ...]` (time-major), or a (possibly
            nested) tuple of such elements.

    Returns:
        A Tensor with transposed batch and time dimensions of inputs.
    """
    flat_input = nest.flatten(inputs)
    flat_input = [ops.convert_to_tensor(input_) for input_ in flat_input]
    # pylint: disable=protected-access
    flat_input = [rnn._transpose_batch_time(input_) for input_ in flat_input]
    return nest.pack_sequence_as(structure=inputs, flat_sequence=flat_input)


def default_string(str_, default_str):
    """Returns :attr:`str_` if it is not `None` or empty, otherwise returns
    :attr:`default_str`.

    Args:
        str_: A string.
        default_str: A string.

    Returns:
        Either :attr:`str_` or :attr:`default_str`.
    """
    if str_ is not None and str_ != "":
        return str_
    else:
        return default_str

def patch_dict(tgt_dict, src_dict):
    """Recursively patch :attr:`tgt_dict` by adding items from :attr:`src_dict`
    that do not exist in :attr:`tgt_dict`.

    If respective items in :attr:`src_dict` and :attr:`tgt_dict` are both
    `dict`, the :attr:`tgt_dict` item is patched recursively.

    Args:
        tgt_dict (dict): Target dictionary to patch.
        src_dict (dict): Source dictionary.

    Return:
        dict: A patched dictionary.
    """
    patched_dict = copy.deepcopy(tgt_dict)
    for key, value in src_dict.items():
        if key not in patched_dict:
            patched_dict[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(patched_dict[key], dict):
            patched_dict[key] = patch_dict(patched_dict[key], value)
    return patched_dict

def is_str_or_unicode(x):
    """Returns `True` if :attr:`x` is either a str or unicode. Returns `False`
    otherwise.
    """
    return isinstance(x, str) or isinstance(x, unicode)

def uniquify_str(str_, str_set):
    """Uniquifies :attr:`str_` if :attr:`str_` is included in :attr:`str_set`.

    This is done by appending '_[digits]' to :attr:`str_`. Returns
    :attr:`str_set` directly if :attr:`str_` is not included in :attr:`str_set`.

    Args:
        str_ (string): A string to uniquify.
        str_set (set, dict, or list): A collection of strings. The returned
            string is guaranteed to be different from the elements in the
            collection.

    Returns:
        string: The uniquified string. Returns :attr:`str_` directly if it is
            already unique.
    """
    if str_ not in str_set:
        return str_
    else:
        for i in range(1, len(str_set)+1):
            unique_str = str_ + "_%d" % i
            if unique_str not in str_set:
                return unique_str
    raise ValueError("Fails to uniquify string: " + str_)