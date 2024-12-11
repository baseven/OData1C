"""
This example demonstrates posting and unposting a document using OData:
- Using post_document(guid, operational_mode=False) to commit a document.
- Using unpost_document(guid) to revert the posting.
"""

import os
from datetime import datetime
from uuid import UUID
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from pydantic import Field
from OData1C.connection import Connection
from OData1C.models import ODataModel
from OData1C.odata.manager import OData

load_dotenv()

host = os.getenv('ODATA_HOST')
protocol = os.getenv('ODATA_PROTOCOL')
username = os.getenv('ODATA_USERNAME')
password = os.getenv('ODATA_PASSWORD')

class DocumentModel(ODataModel):
    uid_1c: UUID = Field(alias='Ref_Key', exclude=True)
    number: str = Field(alias='Number')
    date: datetime = Field(alias='Date')

class DocumentOdata(OData):
    database = 'some_database'
    entity_model = DocumentModel
    entity_name = 'Document_SomeDocument'  # замените на реальное имя сущности

if __name__ == "__main__":
    with Connection(
        host=host,
        protocol=protocol,
        authentication=HTTPBasicAuth(username, password),
    ) as conn:
        manager = DocumentOdata.manager(conn)

        # Предположим у нас есть документ с известным GUID
        doc_guid = '123e4567-e89b-12d3-a456-426614174000'

        # Постим документ
        manager.post_document(doc_guid, operational_mode=True)
        print("Document posted.")

        # Распостим документ (отмена проведения)
        manager.unpost_document(doc_guid)
        print("Document unposted.")