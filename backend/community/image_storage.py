from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings


class StorageUnavailable(Exception):
    pass


class ObjectNotFound(Exception):
    pass


@lru_cache(maxsize=1)
def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.COMMUNITY_IMAGE_S3_ENDPOINT,
        aws_access_key_id=settings.COMMUNITY_IMAGE_S3_ACCESS_KEY,
        aws_secret_access_key=settings.COMMUNITY_IMAGE_S3_SECRET_KEY,
        region_name=settings.COMMUNITY_IMAGE_S3_REGION,
        config=Config(
            signature_version="s3v4",
            connect_timeout=3,
            read_timeout=10,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


@lru_cache(maxsize=1)
def _ensure_bucket():
    client = _client()
    try:
        client.head_bucket(Bucket=settings.COMMUNITY_IMAGE_S3_BUCKET)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in {"404", "NoSuchBucket", "NotFound"}:
            raise StorageUnavailable from error
        try:
            client.create_bucket(Bucket=settings.COMMUNITY_IMAGE_S3_BUCKET)
        except ClientError as create_error:
            if create_error.response.get("Error", {}).get("Code") not in {
                "BucketAlreadyExists",
                "BucketAlreadyOwnedByYou",
            }:
                raise StorageUnavailable from create_error
    except BotoCoreError as error:
        raise StorageUnavailable from error


def put_object(key, body, content_type):
    _ensure_bucket()
    try:
        _client().put_object(
            Bucket=settings.COMMUNITY_IMAGE_S3_BUCKET,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as error:
        raise StorageUnavailable from error


def get_object(key):
    _ensure_bucket()
    try:
        return _client().get_object(Bucket=settings.COMMUNITY_IMAGE_S3_BUCKET, Key=key)["Body"]
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            raise ObjectNotFound from error
        raise StorageUnavailable from error
    except BotoCoreError as error:
        raise StorageUnavailable from error


def delete_object(key):
    _ensure_bucket()
    try:
        _client().delete_object(Bucket=settings.COMMUNITY_IMAGE_S3_BUCKET, Key=key)
    except (BotoCoreError, ClientError) as error:
        raise StorageUnavailable from error
