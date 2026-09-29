"""A minimal in-memory stand-in for the boto3 S3 client, used only where a real MinIO/R2 endpoint
isn't reachable (this sandbox has no Docker Hub access to pull minio/minio). It implements exactly
the boto3 surface app/services/storage_r2.py calls, so everything above that call — validation,
the files/pending_file_deletions rows, the API layer — is exercised for real; only the actual
network PUT/DELETE/presign is faked.
"""

from __future__ import annotations

from botocore.exceptions import ClientError


class _FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakePaginator:
    def __init__(self, client: "FakeS3Client") -> None:
        self._client = client

    def paginate(self, Bucket, Prefix=""):  # noqa: N803
        keys = sorted(k for (b, k) in self._client.objects if b == Bucket and k.startswith(Prefix))
        contents = [{"Key": k, "Size": len(self._client.objects[(Bucket, k)])} for k in keys]
        yield {"Contents": contents}


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.buckets: set[str] = set()

    def put_object(self, Bucket, Key, Body, ContentType=None):  # noqa: N803 (matches boto3's signature)
        self.buckets.add(Bucket)
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):  # noqa: N803
        try:
            return {"Body": _FakeBody(self.objects[(Bucket, Key)])}
        except KeyError:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject")

    def delete_object(self, Bucket, Key):  # noqa: N803
        self.objects.pop((Bucket, Key), None)

    def head_bucket(self, Bucket):  # noqa: N803
        if Bucket not in self.buckets:
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket")

    def create_bucket(self, Bucket):  # noqa: N803
        self.buckets.add(Bucket)

    def get_paginator(self, operation_name):
        return _FakePaginator(self)

    def generate_presigned_url(self, operation, Params, ExpiresIn=300):  # noqa: N803
        bucket, key = Params["Bucket"], Params["Key"]
        return f"https://fake-r2.test/{bucket}/{key}?expires={ExpiresIn}"
