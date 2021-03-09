class ArtsBase:
    """A simple Base class for the ARTS classes, which holds implementations of builtin functions like e.g. __eq__
    """

    def __eq__(self, other):
        return self.a == other.a \
               and self.d == other.d \
               and self.b == other.b \
               and self.r == other.r \
               and self.w == other.w