from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Type


type_repr: Dict[Type[Any], Callable[[Any], str]] = {
    bool: lambda v: str(v).lower(),
    str: lambda v: f"'{v}'",
    datetime: lambda v: f"datetime'{v.isoformat()}'",
}


class Q:
    """
    A class for building OData filter expressions in a style similar to Django's Q objects.

    The `Q` class encapsulates conditions and logical combinations of conditions for OData queries.
    It allows the developer to construct complex `$filter` expressions by chaining and combining
    multiple conditions through logical connectors (AND, OR) and applying negations (NOT).

    Key features:
    - Support for a variety of comparison operators: eq, ne, gt, ge, lt, le, in.
    - Easy logical composition using Python's bitwise operators:
        - `&` corresponds to the `and` connector.
        - `|` corresponds to the `or` connector.
        - `~` applies a `not` negation.
    - Recursive combination of conditions, enabling complex and nested filter queries.
    - Field mapping and annotation capabilities for handling OData-specific types (e.g., guid, datetime).

    The `Q` objects are effectively immutable; operations like `&`, `|`, and `~` produce new `Q` objects
    without modifying the originals.

    Example:
        from src.odata.query import Q

        # Simple equality condition: Name eq 'Ivanov'
        q = Q(name='Ivanov')

        # Combined condition: Name eq 'Ivanov' and Age gt 30
        q = Q(name='Ivanov') & Q(age__gt=30)

        # Negation: not(Name eq 'Ivanov')
        q = ~Q(name='Ivanov')

        # Using the 'in' operator: (Code eq 'ABC' or Code eq 'XYZ')
        q = Q(code__in=['ABC', 'XYZ'])

    Calling `str(q)` returns the OData filter expression string, which can be attached
    to an OData query, enabling flexible and maintainable query construction.
    """

    AND = "and"
    OR = "or"
    NOT = "not"

    _OPERATORS = {"eq", "ne", "gt", "ge", "lt", "le", "in"}
    _DEFAULT_OPERATOR = "eq"
    _ANNOTATIONS = {"guid", "datetime"}
    _ARG_ERROR_MSG = "The positional argument must be a Q object. Received {}."

    def __init__(self, *args: "Q", **kwargs: Any):
        """
        Initializes a Q object with conditions and/or nested Q objects.

        Positional arguments must be Q objects and are combined with the default connector (AND).
        Keyword arguments represent conditions in the form of `field__operator=value`.
        If no operator is provided, `eq` is used by default.
        If `in` operator is used, it expands into multiple `eq` conditions joined by `OR`.

        Raises:
            ValueError: If no arguments or keyword conditions are provided.
            TypeError: If any positional argument is not a Q object.
        """
        if not args and not kwargs:
            raise ValueError("No arguments provided to Q object.")

        self.children: List[Any] = []
        self.connector = self.AND
        self.negated = False

        for key, value in kwargs.items():
            parts = key.split("__")
            operator = parts[1] if len(parts) > 1 else self._DEFAULT_OPERATOR
            if operator == "in":
                self.children.append(
                    self.create(children=[(key, value)], connector=self.OR)
                )
            else:
                self.children.append((key, value))

        for arg in args:
            if not isinstance(arg, Q):
                raise TypeError(self._ARG_ERROR_MSG.format(type(arg)))
            self.children.append(arg)

    @classmethod
    def create(
        cls,
        children: Optional[List[Any]] = None,
        connector: Optional[str] = None,
        negated: bool = False,
    ) -> "Q":
        """
        Creates a new Q instance with the given children, connector, and negation flag.

        This factory method is useful for internal operations like copying or combining Q objects
        without invoking the main constructor logic that expects Q objects or conditions as arguments.

        Args:
            children (Optional[List[Any]]): A list of conditions or Q objects.
            connector (Optional[str]): The logical connector (AND/OR) for combining children.
            negated (bool): Whether the resulting Q object should be negated (NOT).

        Returns:
            Q: A new Q object configured with the provided parameters.
        """
        obj = cls()
        obj.children = children or []
        obj.connector = connector or cls.AND
        obj.negated = negated
        return obj

    def __str__(self) -> str:
        """Returns the OData filter expression as a string."""
        return self.build_expression()

    def __repr__(self) -> str:
        """Returns a developer-friendly representation of the Q object."""
        return f"<Q: {self}>"

    def __or__(self, other: "Q") -> "Q":
        """Combines this Q with another Q using OR logic."""
        return self.combine(other, self.OR)

    def __and__(self, other: "Q") -> "Q":
        """Combines this Q with another Q using AND logic."""
        return self.combine(other, self.AND)

    def __invert__(self) -> "Q":
        """
        Applies a NOT operator to this Q object, effectively negating its conditions.

        Returns:
            Q: A new Q object with the negation applied.
        """
        obj = self.copy()
        obj.negated = not self.negated
        return obj

    def copy(self) -> "Q":
        """
        Creates a copy of this Q object, retaining the same children, connector, and negation state.

        Returns:
            Q: A new Q object identical to the current one.
        """
        return self.create(
            children=self.children, connector=self.connector, negated=self.negated
        )

    def combine(self, other: "Q", connector: str) -> "Q":
        """
        Combines this Q object with another Q object using the specified logical connector (AND/OR).

        Args:
            other (Q): Another Q object to combine with.
            connector (str): The logical connector (Q.AND or Q.OR).

        Raises:
            TypeError: If 'other' is not a Q object.

        Returns:
            Q: A new Q object representing (this Q) connector (other Q).
        """
        if not isinstance(other, Q):
            raise TypeError(self._ARG_ERROR_MSG.format(type(other)))
        obj = self.create(connector=connector)
        obj.children = [self, other]
        return obj

    def build_expression(self, field_mapping: Optional[Dict[str, str]] = None) -> str:
        """
        Recursively builds the OData filter expression string from the Q object's conditions and sub-Q objects.

        If the Q object is negated, it wraps the resulting expression with 'not'.
        If children contain nested Q objects, their expressions are built recursively.
        Conditions represented as (key, value) tuples are expanded into OData-compatible filter syntax.

        Args:
            field_mapping (Optional[Dict[str, str]]): A mapping from internal field names to OData field names.

        Returns:
            str: The fully constructed OData filter expression.
        """
        expressions = []
        for child in self.children:
            if isinstance(child, Q):
                expr = child.build_expression(field_mapping)
                if child.negated:
                    expr = f"{self.NOT} ({expr})"
                expressions.append(expr)
            else:
                expr = self._build_lookup(child, field_mapping)
                expressions.append(expr)
        connector = f" {self.connector} "
        expression = connector.join(expressions)
        if self.negated:
            expression = f"{self.NOT} ({expression})"
        return expression

    def _build_lookup(
        self, lookup: Any, field_mapping: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Builds a single lookup (condition) for a field and operator.

        Lookup is a tuple (key, value), where key may include operators and annotations
        in the format `field__operator__annotation`. If no operator is provided, `eq` is used by default.

        Args:
            lookup (Any): A tuple (key, value) representing a condition.
            field_mapping (Optional[Dict[str, str]]): A mapping of internal to OData field names.

        Raises:
            ValueError: If an unsupported operator is used.

        Returns:
            str: The OData condition string, e.g. "Name eq 'Ivanov'".
        """
        key, value = lookup
        parts = key.split("__")
        field = parts[0]
        operator = parts[1] if len(parts) > 1 else self._DEFAULT_OPERATOR
        annotation = parts[2] if len(parts) > 2 else None

        if field_mapping and field in field_mapping:
            field = field_mapping[field]

        if operator not in self._OPERATORS:
            raise ValueError(f"Unsupported operator '{operator}' in lookup '{key}'.")

        if operator == "in":
            return self._in_lookup(field, value, annotation)
        else:
            value_repr = self._format_value(value, annotation)
            return f"{field} {operator} {value_repr}"

    def _in_lookup(self, field: str, values: Iterable[Any], annotation: Optional[str]) -> str:
        """
        Handles the 'in' operator by expanding a list of values into multiple 'eq' comparisons combined with OR.

        For example, code__in=['ABC', 'XYZ'] -> "code eq 'ABC' or code eq 'XYZ'".

        Args:
            field (str): The field name.
            values (Iterable[Any]): The set of values to check.
            annotation (Optional[str]): An optional annotation (e.g., 'guid', 'datetime').

        Returns:
            str: An OData expression that checks if the field equals one of the given values.
        """
        expressions = [
            f"{field} eq {self._format_value(value, annotation)}" for value in values
        ]
        return " or ".join(expressions)

    def _format_value(self, value: Any, annotation: Optional[str]) -> str:
        """
        Formats a value according to OData rules, taking into account annotations and types.

        If an annotation (e.g. 'datetime') is given, the value is wrapped accordingly:
        "datetime'2024-12-07T10:00:00'".

        For known types (bool, str, datetime), it applies predefined formatting rules (type_repr).
        For unknown types, it defaults to str(value).

        Args:
            value (Any): The value to format.
            annotation (Optional[str]): An optional annotation (e.g., 'guid', 'datetime').

        Returns:
            str: The value formatted for inclusion in an OData filter expression.
        """
        if annotation and annotation in self._ANNOTATIONS:
            return f"{annotation}'{value}'"
        value_type = type(value)
        if value_type in type_repr:
            return type_repr[value_type](value)
        return str(value)