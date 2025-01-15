# OData1C - Python-клиент для работы с OData в системах 1C

OData1C — это Python-клиент для взаимодействия с системами 1C через их REST-интерфейс OData версии 3.  
Цель клиента — упростить и ускорить выполнение задач, связанных с запросами к сущностям, применением фильтров и расширений, созданием и обновлением данных, а также работой с вложенными сущностями. В качестве базовых технологий использутся **Pydantic** для валидации данных и **Requests** для HTTP-коммуникации.

Первоначально основанный на [PyOData1C](https://github.com/kr-aleksey/PyOData1C) (который предоставлял лишь основные возможности OData для 1C), OData1C был переработан для обеспечения более чёткой структуры, подробных докстрингов на английском языке, улучшенной поддерживаемости и расширяемости.

## Ключевые возможности

- **Интеграция с OData**: Поддержка взаимодействия с OData-эндпоинтами 1C (в основном проверено на OData v3).
- **Валидация данных**: Использование Pydantic для сериализации, десериализации и валидации данных сущностей.
- **Интерфейс, похожий на ORM**: Определяйте модели сущностей как классы, наследующие от `ODataModel` (Pydantic), а затем используйте классы `OData` и `ODataManager` для удобной работы с сервером.
- **Гибкое построение запросов**:  
  - **Фильтрация**: Применяйте фильтры, используя lookups в стиле Django или объекты `Q`.
  - **Расширение**: Получайте связанные вложенные сущности через `$expand`.
  - **Пагинация**: Ограничивайте и пропускайте результаты с помощью `$top` и `$skip`.
- **Цепочки вызовов**: Методы `filter()`, `expand()`, `top()` и `skip()` возвращают менеджер, что позволяет строить цепочки вызовов и писать более понятные и компактные запросы.
- **Обработка ошибок**: Предоставляются доменно-специфичные исключения, аккумулирование ошибок валидации и гибкие стратегии обработки ошибок.
- **Контекстный менеджер**: Используйте `Connection` в контекстном менеджере (`with ... as ...`), чтобы автоматически управлять ресурсами и сессией.

## Установка

```bash
pip install odata1c-client
```

## Зависимости
- Python = 3.12
- Pydantic = 2.7.0
- Requests = 2.32.0

## Пример использования

Ниже приведён пример, показывающий определение моделей и выполнение запроса:

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

Больше примеров Вы найдете в OData1C/example.

## Класс Connection
Класс `Connection` предоставляет интерфейс для отправки HTTP-запросов к OData-серверу 1C.
Его можно создавать напрямую или использовать в контекстном менеджере (`with ... as ...`).
Конструктор принимает параметры, такие как `host` (домен или IP-адрес сервера 1C), `protocol` (например, http или https)
и `authentication` (например, HTTPBasicAuth). Вы также можете указать `connection_timeout` и `read_timeout`. Внутри используется библиотека `Requests`.

Примеры использования:
```python
with Connection(
        host='my1c.domain.ru',
        protocol='http',
        authentication=HTTPBasicAuth('user', 'pass')) as conn:
    # Perform OData operations here
```
Или без контекстного менеджера:
```python
conn = Connection(
  host='my1c.domain.ru',
  protocol='http',
  authentication=HTTPBasicAuth('user', 'pass'))
# Perform OData operations here
```

## Определение моделей

Модели должны наследоваться от `ODataModel` (класса, расширяющего возможности Pydantic).
Используйте `nested_models` для указания вложенных моделей, которые можно получить через `$expand`:

```python
class MyNestedModel(ODataModel):
    # Define fields and aliases as needed

class MyModel(ODataModel):
    # Define fields and aliases
    nested_models = {
        'some_related_field': MyNestedModel
    }
```

## Работа с OData-сущностями

Создайте подкласс OData и определите:
- **database**: Наименование сервиса или БД.
- **entity_model**: Класс Pydantic-модели для валидации данных.
- **entity_name**: Имя OData-набора сущностей.

```python
class FooOdata(OData):
    database = 'my1cdb'
    entity_model = MyModel
    entity_name = 'bar'
```

## ODataManager

Создайте экземпляр менеджера и выполняйте операции:

```python
manager = FooOdata.manager(conn)
items = manager.all()
```

### Основные методы ODataManager:
- **all(ignore_invalid=False)**: Выполняет GET-запрос, возвращает валидированные сущности. Если `ignore_invalid=True`, невалидные объекты пропускаются, а ошибки сохраняются в `validation_errors`.
- **create(data)**: Отправляет POST-запрос для создания новой сущности. `data` может быть словарём или экземпляром `entity_model` (например, `MyModel`), описывающим новую сущность.
- **get(guid):** Получает одну сущность по ее `GUID`.
- **update(guid, data)**: Обновляет сущность по `GUID` с помощью PATCH-запроса. `data` может быть словарём или экземпляром `entity_model` (например, `MyModel`)с обновляемыми полями.
- **post_document(guid, operational_mode=False)**: Проводит (постит) документ по `GUID`.
- **unpost_document(guid)**: Отменяет проведение документа по `GUID`.
- **expand(*fields)**: Указывает, какие вложенные сущности нужно `$expand`. Принимает позиционные строковые аргументы - имена полей для которых необходимо получить связанные сущности. Переданные имена полей должны быть объявлены в словаре `entity_model.nested_models` (например, `MyModel.nested_models`).
- **filter(...)**: Применяет условия `$filter`. Принимает именованные аргументы в стиле lookups Django или позиционные аргументы `Q`-объектов.
Формат lookup: `field__operator__annotation` где:
  - **field** — имя поля модели;
  - **operator** — один из `eq`, `ne`, `gt`, `ge`, `lt`, `le`, `in` (если не указан, используется `eq`);
  - **annotation (опционально)** — может быть `GUID` или `datetime`.

  ```python
  manager.filter(foo='abc')
  manager.filter(bar__gt=100)
  manager.filter(uid_1c__in__guid=[...])
  ```

- **skip(n), top(n)**: Применяют `$skip` and `$top` для пагинации.

## Фильтрация с помощью Q

Для сложных фильтров используйте объекты `Q`:

```python
from OData1C.odata.query import Q

manager.filter(Q(name='Ivanov') & Q(age__gt=30))
```

## Работа с метаданными

В OData1C также есть удобный механизм для запроса и разбора `$metadata` в 1С OData с кэшированием, что ускоряет 
повторные обращения. Это полезно, если вам нужно изучать доступные Каталоги, Документы или любые другие сущности 
(Entity Types) и их поля без многократных дорогих HTTP-запросов.

```python
from OData1C.connection import Connection
from OData1C.odata.metadata_manager import MetadataManager
from requests.auth import HTTPBasicAuth

with Connection(
        host='1c.dev.evola.ru',
        protocol='https',
        authentication=HTTPBasicAuth('username', 'password')
) as conn:
    mdm = MetadataManager(connection=conn, database='zup-demo')

    # Retrieve all entity types
    entity_types = mdm.list_entity_types()
    print(entity_types)

    # Retrieve all entity sets
    entity_sets = mdm.list_entity_sets()
    print(entity_sets)

    # Inspect specific entity fields
    fields = mdm.get_properties_for_entity_type("Catalog_ФизическиеЛица")
    print(fields)

    # Force reloading metadata if necessary
    mdm.reload_metadata()
```

Данный подход кэширует метаданные в памяти после первой загрузки, и все последующие вызовы (например, 
`list_entity_sets()` или `get_properties_for_entity_type(...)`) получают нужную информацию из уже разобранной структуры, 
а не заново парсят XML. Это существенно снижает издержки, если в вашем приложении часто нужно смотреть метаданные.


## Отладка

Экземпляр `ODataManager` после выполнения запроса имеет атрибуты request и response.
request — объект `ODataRequest`, response — объект `requests.Response`.
Это можно использовать для отладки, просматривая, какие запросы отправлены и какой ответ получен от сервера.

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

## Вклад (Contributing)

Приветствуются вклады в проект! Пожалуйста, открывайте issues или присылайте pull request для улучшений и исправлений.