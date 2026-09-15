import secrets

from django.contrib.auth.hashers import check_password, make_password
from rest_framework import generics, status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import Course
from .serializers import CourseSerializer


class CoursePayloadTooLarge(APIException):
    status_code = 413
    default_detail = "코스 내용이 너무 깁니다."


class CourseWriteProtectionMixin:
    parser_classes = (JSONParser,)

    def initial(self, request, *args, **kwargs):
        if request.method in {"POST", "PATCH", "DELETE"}:
            origin = request.headers.get("Origin")
            if request.headers.get("Sec-Fetch-Site", "").lower() == "cross-site" or (
                origin is not None and origin != f"{request.scheme}://{request.get_host()}"
            ):
                raise PermissionDenied("같은 사이트에서 요청해 주세요.")
            content_length = request.META.get("CONTENT_LENGTH", "")
            if (content_length and not content_length.isdecimal()) or int(content_length or 0) > 64000 or len(request.body) > 64000:
                raise CoursePayloadTooLarge()
        return super().initial(request, *args, **kwargs)


class CourseWriteThrottle(SimpleRateThrottle):
    scope = "course_write"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class CourseListCreateView(CourseWriteProtectionMixin, generics.ListCreateAPIView):
    queryset = Course.objects.prefetch_related("stops")
    serializer_class = CourseSerializer
    permission_classes = (AllowAny,)

    def get_throttles(self):
        return [CourseWriteThrottle()] if self.request.method == "POST" else []

    def create(self, request, *args, **kwargs):
        token = secrets.token_urlsafe(32)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(edit_token_hash=make_password(token))
        data = dict(serializer.data)
        data["editToken"] = token
        return Response(data, status=status.HTTP_201_CREATED)


class CourseDetailView(CourseWriteProtectionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Course.objects.prefetch_related("stops")
    serializer_class = CourseSerializer
    permission_classes = (AllowAny,)
    http_method_names = ("get", "patch", "delete", "options")

    def get_throttles(self):
        return [CourseWriteThrottle()] if self.request.method in {"PATCH", "DELETE"} else []

    def check_edit_token(self, course):
        token = self.request.headers.get("X-Course-Edit-Token", "")
        if not token or not check_password(token, course.edit_token_hash):
            raise PermissionDenied("올바른 코스 편집 토큰이 필요합니다.")

    def update(self, request, *args, **kwargs):
        self.check_edit_token(self.get_object())
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.check_edit_token(self.get_object())
        return super().destroy(request, *args, **kwargs)
