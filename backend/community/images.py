from io import BytesIO
from uuid import UUID

from django.core.files.base import ContentFile
from django.http import FileResponse, Http404
from PIL import Image, UnidentifiedImageError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CommunityPostImage


MAX_IMAGE_BYTES = 20 * 1024 * 1024
FORMATS = {"JPEG": ("JPEG", "image/jpeg", ".jpg"), "PNG": ("PNG", "image/png", ".png"), "WEBP": ("WEBP", "image/webp", ".webp")}


class CommunityImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()


class CommunityImageResultSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    url = serializers.CharField()
    width = serializers.IntegerField()
    height = serializers.IntegerField()
    byteSize = serializers.IntegerField()


class CommunityImageUploadView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(request=CommunityImageUploadSerializer, responses={201: CommunityImageResultSerializer, 400: OpenApiTypes.OBJECT})
    def post(self, request):
        upload = request.FILES.get("image")
        if not upload:
            return Response({"image": "이미지를 선택해 주세요."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_IMAGE_BYTES:
            return Response({"image": "이미지는 한 장에 20MB 이하로 올려 주세요."}, status=status.HTTP_400_BAD_REQUEST)
        if CommunityPostImage.objects.filter(owner=request.user, post__isnull=True, course__isnull=True).count() >= 30:
            return Response({"image": "미사용 이미지가 많아요. 작성 중인 글을 등록해 주세요."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with Image.open(upload) as probe:
                image_format = probe.format
                width, height = probe.size
                if image_format not in FORMATS or width > 6000 or height > 6000 or width * height > 25_000_000:
                    raise ValueError("이미지 종류 또는 크기가 올바르지 않아요.")
                probe.load()
                image = probe.copy()
            target_format, mime, suffix = FORMATS[image_format]
            if target_format == "JPEG":
                image = image.convert("RGB")
            elif target_format == "PNG":
                image = image.convert("RGBA") if "A" in image.getbands() else image.convert("RGB")
            elif target_format == "WEBP":
                image = image.convert("RGBA") if "A" in image.getbands() else image.convert("RGB")
            buffer = BytesIO()
            image.save(buffer, format=target_format, **({"quality": 85} if target_format in {"JPEG", "WEBP"} else {}))
            output = buffer.getvalue()
            if len(output) > MAX_IMAGE_BYTES:
                raise ValueError("변환한 이미지가 20MB를 초과했어요.")
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
            return Response({"image": str(exc) if isinstance(exc, ValueError) else "JPG, PNG, WEBP 이미지 파일만 올릴 수 있어요."}, status=status.HTTP_400_BAD_REQUEST)
        record = CommunityPostImage(owner=request.user, mime_type=mime, byte_size=len(output), width=width, height=height)
        record.file.save(f"{record.id}{suffix}", ContentFile(output), save=False)
        record.save()
        return Response({"id": str(record.id), "url": f"/api/community/images/{record.id}/", "width": width, "height": height, "byteSize": len(output)}, status=status.HTTP_201_CREATED)


class CommunityImageDetailView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses={200: OpenApiTypes.BINARY, 404: OpenApiTypes.OBJECT})
    def get(self, request, image_id):
        try:
            record = CommunityPostImage.objects.get(pk=UUID(image_id))
        except (ValueError, CommunityPostImage.DoesNotExist) as exc:
            raise Http404 from exc
        response = FileResponse(record.file.open("rb"), content_type=record.mime_type)
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'"
        return response
