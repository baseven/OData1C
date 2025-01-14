import xml.etree.ElementTree as ET
from typing import List, Optional

from requests import Request
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout

from OData1C.connection import Connection
from OData1C.exceptions import ODataConnectionError


# В 1С OData практически всегда используется "http://schemas.microsoft.com/ado/2009/11/edm"
# как пространство имён для <EntityType>, <EntitySet> и т.д.
# Будем искать теги именно в этом namespace.
NAMESPACE = "{http://schemas.microsoft.com/ado/2009/11/edm}"


class MetadataManager:
    """
    Класс для получения/парсинга метаданных (/$metadata) в 1С OData,
    принимая в конструкторе:
      - connection: существующий Connection
      - database: например, 'zup-demo'
    Путь 'odata/standard.odata' считаем постоянным и не меняем.
    """

    ODATA_PATH = "odata/standard.odata"

    def __init__(self, connection: Connection, database: str) -> None:
        """
        :param connection: Активный Connection (через with Connection(...) as conn).
        :param database: Название «базы» (например 'zup-demo'),
                         которая идёт после хоста и перед 'odata/standard.odata'.
        """
        self.connection = connection
        self.database = database

    def get_raw_metadata(self) -> str:
        """
        Запрашивает полный URL вида:
          {protocol}://{host}/{database}/{ODATA_PATH}/$metadata
        и возвращает сырую XML-строку с описанием метаданных.

        Мы не используем Connection.get_url(...), а формируем URL вручную.
        """
        # TODO: В теории можно использовать Connection.get_url(...)?
        # Построим полный URL:
        #   base_url = "https://1c.dev.evola.ru/"
        #   + database = "zup-demo" + "/"
        #   + "odata/standard.odata" + "/$metadata"
        url = f"{self.connection.base_url}{self.database}/{self.ODATA_PATH}/$metadata"

        # Берём сессию (если нет активной, создаём временную)
        session = self.connection._session or self.connection._create_session()

        # Формируем запрос вручную
        raw_request = Request(
            method='GET',
            url=url,
            headers={"Accept": "application/xml"},  # важно для метаданных
        )
        prepared_request = session.prepare_request(raw_request)

        try:
            response = session.send(
                prepared_request,
                timeout=(self.connection.connection_timeout, self.connection.read_timeout)
            )
            response.raise_for_status()
            return response.text
        except (RequestsConnectionError, Timeout) as e:
            raise ODataConnectionError(f"Error while fetching metadata: {e}") from e
        finally:
            # Если Connection используется в виде conn._session = None (т.е. не через with),
            # мы закрываем временную сессию сами
            if self.connection._session is None:
                session.close()

    def list_entity_types(self) -> List[str]:
        """
        Возвращает список имён (Name) всех <EntityType ...> из метаданных.
        """
        xml_text = self.get_raw_metadata()
        root = ET.fromstring(xml_text)

        entity_types = []
        for et in root.findall(f".//{NAMESPACE}EntityType"):
            name = et.get("Name")
            if name:
                entity_types.append(name)
        return entity_types

    def list_entity_sets(self) -> List[str]:
        """
        Возвращает список имён (Name) всех <EntitySet ...> из метаданных.
        """
        xml_text = self.get_raw_metadata()
        root = ET.fromstring(xml_text)

        entity_sets = []
        for es in root.findall(f".//{NAMESPACE}EntitySet"):
            name = es.get("Name")
            if name:
                entity_sets.append(name)
        return entity_sets
