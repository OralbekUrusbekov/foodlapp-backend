

import datetime
from sqlalchemy import Column, DateTime, Integer, String
from app.db.database import Base


class FileUpload(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    s3_url = Column(String, nullable=False)
    local_path = Column(String, default=datetime.datetime.utcnow)
    content_type = Column(String, nullable=False)