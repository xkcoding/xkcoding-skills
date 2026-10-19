"""Identity codec: the starting point. encode and decode must be inverse functions on bytes."""


def encode(data: bytes) -> bytes:
    return data


def decode(blob: bytes) -> bytes:
    return blob
