# OData1C - A Python OData Client for 1C Systems

OData1C is a Python client designed to interact with 1C systems via their OData v3 REST endpoints.  
This client aims to simplify and streamline common tasks such as querying entities, applying filters and expansions, creating and updating data, and handling related entities. It uses **Pydantic** for data validation and **Requests** for HTTP communication.

While originally inspired by [PyOData1C](https://github.com/kr-aleksey/PyOData1C) (with only essential OData capabilities for 1C), OData1C has been refined with clearer structure, comprehensive English docstrings, improved maintainability, and extensibility.

## Key Features

- **OData Integration**: Communicates with 1C OData endpoints (primarily tested with OData v3).
- **Data Validation**: Leverages Pydantic for serialization, deserialization, and validation of model data.
- **ORM-Like Interface**: Define your entity models as Pydantic classes inheriting from `ODataModel`, and use `OData` and `ODataManager` classes to interact with the server.
- **Complex Query Building**:  
  - **Filtering**: Apply filters using Django-style lookups or `Q` objects.
  - **Expansion**: Fetch related nested entities via `$expand`.
  - **Pagination**: Limit and skip results using `$top` and `$skip`.
- **Chaining API**: Methods like `filter()`, `expand()`, `top()`, and `skip()` return the manager instance, allowing method chaining and cleaner query construction.
- **Error Handling**: Provides domain-specific exceptions, validation error accumulation, and flexible error handling strategies.
- **Context Manager Support**: Use `Connection` as a context manager (`with ... as ...`) to ensure proper resource cleanup.

## Installation

```bash
pip install OData1C
```

## Dependencies
- Python >= 3.12
- Pydantic >= 2.7.0
- Requests >= 2.32.0

## Usage

Below is a sample usage example showing how to define models and query data:

```python
from uuid import UUID

from requests.auth import HTTPBasicAuth
from pydantic import Field

from OData1C.connection import Connection
from OData1C.models import ODataModel
from OData1C.odata.manager import OData


class MeasureUnitModel(ODataModel):
    uid: UUID = Field(alias='Ref_Key', exclude=True)
    name: str = Field(alias='Description', max_length=6)


class NomenclatureModel(ODataModel):
    uid: UUID = Field(alias='Ref_Key', exclude=True)
    code: str = Field(alias='Code', max_length=12)
    name: str = Field(alias='Description', max_length=200)
    measure_unit: MeasureUnitModel = Field(alias='Measure_Unit')

    nested_models = {
        'measure_unit': MeasureUnitModel
    }


class NomenclatureOdata(OData):
    database = 'database_name'
    entity_model = NomenclatureModel
    entity_name = 'Catalog_Nomenclature'


with Connection('ODATA_HOST',
                'ODATA_PROTOCOL',
                HTTPBasicAuth('ODATA_USERNAME', 'ODATA_PASSWORD')) as conn:
    nomenclatures = (
        NomenclatureOdata.manager(conn)
        .expand('measure_unit')
        .filter(code__in=['00-123', '00-456'])
        .all(ignore_invalid=True)
    )

    for item in nomenclatures:
        print(item.name, item.measure_unit.name)
```

You can find more examples in OData1C/example.

## Connection Class
The `Connection` class provides an interface for sending HTTP requests to the 1C OData server.
It can be instantiated directly or used as a context manager (`with ... as ...`) to handle session lifecycle automatically.
Its constructor requires parameters such as `host` (the domain or IP of the 1C server), `protocol` (e.g. http or https), and `authentication` (e.g. HTTPBasicAuth).
You can also specify `connection_timeout` and `read_timeout` to control network timings. Internally, `Connection` uses the `Requests` library.

Example usage:
```python
with Connection(
        host='my1c.domain.ru',
        protocol='http',
        authentication=HTTPBasicAuth('user', 'pass')) as conn:
    # Perform OData operations here
```
Or without a context manager:
```python
conn = Connection(
  host='my1c.domain.ru',
  protocol='http',
  authentication=HTTPBasicAuth('user', 'pass'))
# Perform OData operations here
```

## Defining Models

Models must inherit from `ODataModel` (a Pydantic BaseModel subclass).
Use `nested_models` to specify related models for `$expand` queries:

```python
class MyNestedModel(ODataModel):
    # Define fields and aliases as needed

class MyModel(ODataModel):
    # Define fields and aliases
    nested_models = {
        'some_related_field': MyNestedModel
    }
```

## Working with OData Entities

Create a subclass of OData and define:
- **database**: The service root or database name.
- **entity_model**: The Pydantic model class for data validation.
- **entity_name**: The OData entity set name.

```python
class FooOdata(OData):
    database = 'my1cdb'
    entity_model = MyModel
    entity_name = 'bar'
```

## ODataManager

Obtain a manager instance and perform operations:

```python
manager = FooOdata.manager(conn)
items = manager.all()
```

### Common Methods in ODataManager:
- **all(ignore_invalid=False)**: Executes a GET request and returns validated entities. If `ignore_invalid=True`, skips invalid objects and accumulates errors in `validation_errors`.
- **create(data)**: Sends a POST request to create a new entity. `data` can be either a dictionary or an instance of the `entity_model` (for example, `MyModel`) representing the new entity.
- **get(guid):** Fetches a single entity by `GUID`.
- **update(guid, data)**: Updates an entity identified by `GUID` using PATCH. `data` can be either a dictionary or an instance of the `entity_model` (for example, `MyModel`) containing the fields to update.
- **post_document(guid, operational_mode=False)**: Posts (commits) a document by `GUID`.
- **unpost_document(guid)**: Unposts (reverts) a previously posted document by `GUID`.
- **expand(*fields)**: Specifies which related entities to `$expand`. Accepts positional string arguments - field names for which related entities should be retrieved. The passed field names must be declared in the `entity_model.nested_models` (for example, `MyModel.nested_models`) dictionary.
- **filter(...)**: Applies `$filter` conditions. It accepts keyword arguments as conditions (lookups in Django style) or positional `Q` objects.
Lookup format: `field__operator__annotation` where:
  - **field** is the model field name;
  - **operator** is one of `eq`, `ne`, `gt`, `ge`, `lt`, `le`, `in` (defaults to `eq` if omitted);
  - **annotation (optional)** can be `GUID` or `datetime`.

  ```python
  manager.filter(foo='abc')
  manager.filter(bar__gt=100)
  manager.filter(uid_1c__in__guid=[...])
  ```

- **skip(n), top(n)**: Applies `$skip` and `$top` for pagination.

## Filtering with Q

For complex filters, use `Q` objects and combine them with logical operators:

```python
from OData1C.odata.query import Q

manager.filter(Q(name='Ivanov') & Q(age__gt=30))
```

## Debugging

The `ODataManager` object has request and response attributes after executing a request. These hold instances of `ODataRequest` and `requests.Response`, respectively. You can inspect them for debugging:

```python
with Connection(
        host='my1c.domain.ru',
        protocol='http',
        authentication=HTTPBasicAuth('user', 'pass')) as conn:
    manager = FooOdata.manager(conn)
    bars = manager.top(3).all()
    pprint(manager.request)
    pprint(manager.response.json())
 ```

## Contributing

Contributions are welcome! Please open issues or submit pull requests for improvements or bug fixes.