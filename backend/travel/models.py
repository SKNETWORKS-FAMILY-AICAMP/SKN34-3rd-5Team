import uuid

from django.db import models
from django.db.models import Q


class Course(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_id = models.CharField(max_length=80, null=True, blank=True, unique=True)
    title = models.CharField(max_length=80)
    stadium = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    content = models.TextField(blank=True)
    content_format = models.CharField(max_length=16, blank=True)
    duration = models.CharField(max_length=80)
    cover = models.CharField(max_length=255, blank=True)
    tags = models.JSONField(default=list)
    start_lat = models.FloatField(null=True, blank=True)
    start_lng = models.FloatField(null=True, blank=True)
    author = models.CharField(max_length=80, default="익명")
    likes = models.PositiveIntegerField(default=0)
    views = models.PositiveIntegerField(default=0)
    is_sample = models.BooleanField(default=False)
    edit_token_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = (
            models.CheckConstraint(
                condition=(Q(start_lat__isnull=True) & Q(start_lng__isnull=True)) | (Q(start_lat__isnull=False) & Q(start_lng__isnull=False)),
                name="course_start_coordinates_paired",
            ),
            models.CheckConstraint(condition=Q(start_lat__isnull=True) | Q(start_lat__range=(-90, 90)), name="course_start_lat_bounds"),
            models.CheckConstraint(condition=Q(start_lng__isnull=True) | Q(start_lng__range=(-180, 180)), name="course_start_lng_bounds"),
        )


class CourseStop(models.Model):
    course = models.ForeignKey(Course, related_name="stops", on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=255)
    lat = models.FloatField()
    lng = models.FloatField()
    category = models.CharField(max_length=120)
    place_id = models.CharField(max_length=255, null=True, blank=True)
    visit_id = models.CharField(max_length=255, null=True, blank=True)
    address = models.CharField(max_length=500, null=True, blank=True)
    tour_content_id = models.CharField(max_length=255, null=True, blank=True)
    is_map_point = models.BooleanField(null=True, blank=True)
    is_drawn_point = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ("position",)
        constraints = (
            models.UniqueConstraint(fields=("course", "position"), name="unique_course_stop_position"),
            models.CheckConstraint(condition=Q(lat__range=(-90, 90)), name="course_stop_lat_bounds"),
            models.CheckConstraint(condition=Q(lng__range=(-180, 180)), name="course_stop_lng_bounds"),
        )
