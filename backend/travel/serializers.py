import math

from django.db import transaction
from rest_framework import serializers

from .models import Course, CourseStop


class FiniteFloatField(serializers.FloatField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not math.isfinite(value):
            raise serializers.ValidationError("유한한 숫자를 입력해 주세요.")
        return value


class CourseStopSerializer(serializers.ModelSerializer):
    placeId = serializers.CharField(source="place_id", required=False, allow_blank=True, allow_null=True)
    visitId = serializers.CharField(source="visit_id", required=False, allow_blank=True, allow_null=True)
    tourContentId = serializers.CharField(source="tour_content_id", required=False, allow_blank=True, allow_null=True)
    isMapPoint = serializers.BooleanField(source="is_map_point", required=False, allow_null=True)
    isDrawnPoint = serializers.BooleanField(source="is_drawn_point", required=False, allow_null=True)
    lat = FiniteFloatField(min_value=-90, max_value=90)
    lng = FiniteFloatField(min_value=-180, max_value=180)

    class Meta:
        model = CourseStop
        fields = ("position", "name", "lat", "lng", "category", "placeId", "visitId", "address", "tourContentId", "isMapPoint", "isDrawnPoint")

    def to_representation(self, instance):
        return {key: value for key, value in super().to_representation(instance).items() if value is not None}


class CourseSerializer(serializers.ModelSerializer):
    sampleId = serializers.CharField(source="source_id", read_only=True)
    isSample = serializers.BooleanField(source="is_sample", read_only=True)
    content = serializers.CharField(required=False, allow_blank=True, max_length=12000)
    contentFormat = serializers.ChoiceField(source="content_format", choices=("", "html"), required=False, allow_blank=True)
    startLat = FiniteFloatField(source="start_lat", min_value=-90, max_value=90, required=False, allow_null=True)
    startLng = FiniteFloatField(source="start_lng", min_value=-180, max_value=180, required=False, allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    stops = CourseStopSerializer(many=True, required=False)

    class Meta:
        model = Course
        fields = ("id", "sampleId", "title", "stadium", "description", "content", "contentFormat", "duration", "cover", "tags", "startLat", "startLng", "author", "likes", "views", "isSample", "createdAt", "updatedAt", "stops")
        read_only_fields = ("id", "sampleId", "description", "cover", "author", "likes", "views", "isSample", "createdAt", "updatedAt")

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("코스 이름을 입력해 주세요.")
        return value

    def validate_tags(self, value):
        if not isinstance(value, list) or not all(isinstance(tag, str) for tag in value):
            raise serializers.ValidationError("태그는 문자열 목록이어야 합니다.")
        return value

    def validate_stops(self, value):
        if self.partial:
            serializer = CourseStopSerializer(data=self.initial_data["stops"], many=True)
            serializer.is_valid(raise_exception=True)
            return serializer.validated_data
        return value

    def validate(self, attrs):
        lat = attrs.get("start_lat", getattr(self.instance, "start_lat", None))
        lng = attrs.get("start_lng", getattr(self.instance, "start_lng", None))
        if (lat is None) != (lng is None):
            raise serializers.ValidationError("출발 좌표는 위도와 경도를 함께 입력해 주세요.")
        if "stops" in attrs:
            stops = attrs["stops"]
            if not 1 <= len(stops) <= 12:
                raise serializers.ValidationError({"stops": "방문 장소는 1개 이상 12개 이하이어야 합니다."})
            positions = [stop["position"] for stop in stops]
            if sorted(positions) != list(range(len(stops))):
                raise serializers.ValidationError({"stops": "position은 0부터 중복 없이 이어져야 합니다."})
        elif self.instance is None:
            raise serializers.ValidationError({"stops": "방문 장소를 입력해 주세요."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        stops = validated_data.pop("stops")
        course = Course.objects.create(**validated_data)
        CourseStop.objects.bulk_create(CourseStop(course=course, **stop) for stop in stops)
        return course

    @transaction.atomic
    def update(self, instance, validated_data):
        stops = validated_data.pop("stops", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if stops is not None:
            instance.stops.all().delete()
            CourseStop.objects.bulk_create(CourseStop(course=instance, **stop) for stop in stops)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data["sampleId"] is None:
            data.pop("sampleId")
        if not data["contentFormat"]:
            data.pop("contentFormat")
        if data["startLat"] is None:
            data.pop("startLat")
            data.pop("startLng")
        return data
