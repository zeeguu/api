
from codoc.service.export import view
from codoc.service.parsing.node import get_description, get_identifier_of_object


import zeeguu_core

from codoc.service.filters import exclude_functions, exclude_classes, get_children_of

@view(
    label="Core Module View",
)
def view_modules(graph):
    """
    This view contains all the modules that our project contain.
    """
    model = get_identifier_of_object(zeeguu_core)
    filter_function = get_children_of(model)

    return exclude_functions(exclude_classes(filter_function(graph)))
