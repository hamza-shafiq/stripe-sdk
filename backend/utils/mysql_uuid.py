import uuid
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID


class GUID(TypeDecorator):
    """
    A class to handle platform-independent GUID type.
    """

    impl = CHAR

    def load_dialect_impl(self, dialect):
        """
        Loads the implementation of a given dialect.

        Args:
          dialect (Dialect): The dialect to load the implementation for.

        Returns:
          Returns the type descriptor for the given dialect. If the dialect is
          'postgresql', it returns a UUID type descriptor, otherwise it returns
          a CHAR(32) type descriptor.
        """
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        """
        Process the bind parameter based on the value and dialect provided.

        Args:
          value: The value to be processed.
          dialect: The dialect based on which the value is processed.

        Returns:
          Returns the processed value based on the conditions met. If value is
          None, it returns None. If dialect is 'postgresql', it returns the
          string representation of the value. If value is not an instance of
          uuid.UUID, it returns a 32-character hexadecimal number. Otherwise,
          it returns the hexadecimal representation of the value.
        """

        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value)
            else:
                # hexstring
                return value.hex

    def process_result_value(self, value, dialect):
        """
        Process the given value and return a UUID object if the value is not
        None.

        Args:
          value (Any): The value to be processed.
          dialect (Any): The dialect to be used. This parameter is not used in
            the function.

        Returns:
          Returns a UUID object if the value is not None, otherwise returns
          None.
        """
        if value is None:
            return value
        else:
            return uuid.UUID(value)
