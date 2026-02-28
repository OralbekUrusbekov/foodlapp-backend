import uuid
from botocore.exceptions import BotoCoreError, NoCredentialsError
from fastapi import HTTPException
from app.setting.s3_setting import s3_client, AWS_S3_BUCKET_NAME

def upload_file_to_s3(file, content_type: str) -> str:
    try:
        ext = file.filename.split(".")[-1]
        unique_name = f"foods/{uuid.uuid4()}.{ext}"

        s3_client.upload_fileobj(
            file.file,
            AWS_S3_BUCKET_NAME,
            unique_name,
            ExtraArgs={"ContentType": content_type}
        )

        return f"https://{AWS_S3_BUCKET_NAME}.s3.amazonaws.com/{unique_name}"

    except (BotoCoreError, NoCredentialsError):
        raise HTTPException(status_code=500, detail="S3 upload error")