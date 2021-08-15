from rest_framework import status
from rest_framework.response import Response


def block_response():
    return Response(
        {"detail": "Permission denied, block exists"},
        status=status.HTTP_403_FORBIDDEN
    )


def created_response(serializer):
    return Response(serializer.data, status=status.HTTP_201_CREATED)


def validation_fail_response(serializer):
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def update_response(serializer):
    return Response(serializer.data)


def validation_error(error):
    return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
