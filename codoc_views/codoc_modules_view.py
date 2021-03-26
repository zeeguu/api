from codoc.service import filters
from codoc.service.export import view

@view(
    label="Module View",
)
def view_modules(graph):
    """
    This view contains all the modules that our project contain.
    """
    return filters.exclude_functions(filters.exclude_classes(graph))
