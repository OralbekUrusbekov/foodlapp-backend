from app.models.file import FileUpload
from app.repositories.default_repositories import SQLAlchemyRepository


class FileRepository(SQLAlchemyRepository):
    model = FileUpload