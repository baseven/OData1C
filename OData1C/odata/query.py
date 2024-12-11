from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Type


type_repr: Dict[Type[Any], Callable[[Any], str]] = {
    bool: lambda v: str(v).lower(),
    str: lambda v: f"'{v}'",
    datetime: lambda v: f"datetime'{v.isoformat()}'",
}


class Q:
    """
    Q is a node of a tree graph. A node is a connection whose child
    nodes are either leaf nodes or other instances of the node.
    This code is partially based on Django code.
    """
    AND = 'and'
    OR = 'or'
    NOT = 'not'

    _operators = ('eq', 'ne', 'gt', 'ge', 'lt', 'le', 'in')
    _default_operator = 'eq'
    _annotations = ('guid', 'datetime')
    _arg_error_msg = 'The positional argument must be a Q object. Received {}.'

    def __new__(cls, *args: 'Q', **kwargs: Any):
        """
        Creates a Q object with kwargs leaf. Combines the created
        Q object with the objects passed via positional arguments
        using &. Returns the resulting Q object.
        :param args: Q objects.
        :param kwargs: Lookups.
        """
        obj = super().__new__(cls)
        children = []
        for key, value in kwargs.items():
            _, lookup, *_ = *key.split('__'), None
            if lookup == 'in':
                children.append(
                    cls.create(children=[(key, value)], connector=Q.OR))
            else:
                children.append((key, value))
        obj.children = children
        obj.connector = Q.AND
        obj.negated = False

        for arg in args:
            if not isinstance(arg, Q):
                raise TypeError(cls._arg_error_msg.format(type(arg)))
            obj &= arg

        return obj

    def __init__(self, *args: 'Q', **kwargs: Any):
        if not args and not kwargs:
            raise AttributeError('No arguments given')

    @classmethod
    def create(cls, children=None, connector=None, negated=False):
        obj = cls.__new__(cls)
        obj.children = children.copy() if children else []
        obj.connector = connector if connector is not None else connector
        obj.negated = negated
        return obj

    def __str__(self) -> str:
        return self.build_expression()

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self}>'

    def __copy__(self):
        return self.create(children=self.children,
                           connector=self.connector,
                           negated=self.negated)

    copy = __copy__

    def __or__(self, other):
        return self.combine(other=other, connector=self.OR)

    def __and__(self, other):
        return self.combine(other=other, connector=self.AND)

    def __invert__(self):
        obj = self.copy()
        obj.negated = not self.negated
        return obj

    def add(self, other) -> None:
        if self.connector != other.connector or other.negated:
            self.children.append(other)
        else:
            self.children.extend(other.children)

    def combine(self, other, connector):
        obj = self.create(connector=connector)
        obj.add(self)
        obj.add(other)
        return obj

    def build_expression(self,
                         field_mapping: dict[str, str] | None = None) -> str:
        """
        Recursively iterates over child elements. Builds an expression
        taking into account the priorities of the operations.
        The field_mapping argument is used to map the field name
        to the OData field name.
        :param field_mapping: {field_name: alias}
        :return: Full filter expression.
        """
        child_expressions: list[str] = []
        for child in self.children:
            if isinstance(child, Q):
                child_expression: str = child.build_expression(field_mapping)
                if self.connector == Q.AND and child.connector == Q.OR:
                    child_expression: str = f'({child_expression})'
            else:
                child_expression: str = self._build_lookup(child,
                                                           field_mapping)
            child_expressions.append(child_expression)
        expression = f' {self.connector} '.join(child_expressions)
        if self.negated:
            expression = f'{self.NOT} ({expression})'
        return expression

    def _build_lookup(self,
                      lookup: tuple[str, Any],
                      field_mapping: dict[str, str] | None = None) -> str:
        """
        Builds a lookup to a filter expression.
        :param lookup: (key, value)
        :param field_mapping: {field_name: alias}
        :return: Expression. For example: "Name eq 'Ivanov'"
        """
        field, operator, annotation, *_ = (
            *lookup[0].split('__', maxsplit=3),
            None,
            None
        )
        if field_mapping is not None:
            if field not in field_mapping:
                raise KeyError(
                    f"Field '{field}' not found. "
                    f"Use one of {list(field_mapping.keys())}"
                )
            field = field_mapping[field]
        operator = operator or self._default_operator
        if operator not in self._operators:
            raise KeyError(
                f"Unsupported operator {operator} ({lookup[0]}). "
                f"Use one of {self._operators}."
            )
        return self._get_lookup_builder(operator)(field, lookup[1], annotation)

    def _get_lookup_builder(self, lookup: str) -> Callable:
        if lookup == 'in':
            return self._in_builder
        return lambda field, value, annotation: \
            f'{field} {lookup} {self._annotate_value(value, annotation)}'

    def _in_builder(self,
                    field: str,
                    value: Any,
                    annotation: str | None) -> str:
        """
        :param field: Field name.
        :param value: Value.
        :param annotation: Annotation.
        Converts lookup 'in' to an Odata filter parameter.
        For example: 'foo eq value or foo eq value2 ...'
        """
        items = [f'{field} eq {self._annotate_value(v, annotation)}'
                 for v in value]
        return ' or '.join(items)

    def _annotate_value(self,
                        value: Any,
                        annotation: str | None) -> str:
        """
        :param value: Value to annotate.
        :param annotation: Annotation ('guid', 'date', etc ).
        :return: Annotated value. For example: guid'123'.
        """
        if annotation is not None:
            if annotation not in self._annotations:
                raise KeyError(
                    f"Unknown annotation {annotation}. "
                    f"Use one of {self._annotations}"
                )
            return f"{annotation}'{value}'"

        if type(value) in type_repr:
            return type_repr[type(value)](value)
        return str(value)
