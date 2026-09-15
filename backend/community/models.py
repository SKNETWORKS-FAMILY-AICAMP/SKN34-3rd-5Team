from django.db import models
from django.db.models import Q


TEAM_CODES = ("LG", "HH", "SK", "SS", "NC", "KT", "LT", "HT", "OB", "WO")


class CommunityPost(models.Model):
    source_id = models.CharField(max_length=40, primary_key=True)
    post_number = models.CharField(max_length=6, unique=True)
    board = models.CharField(max_length=8, choices=(("free", "free"), ("teams", "teams")))
    team_code = models.CharField(max_length=2, blank=True)
    author = models.CharField(max_length=80)
    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=20)
    created_at = models.DateTimeField(null=True, blank=True)
    views = models.PositiveIntegerField(default=0)
    recommendations = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    is_sample = models.BooleanField(default=False)

    class Meta:
        ordering = ("post_number",)
        constraints = (
            models.CheckConstraint(
                condition=Q(board="free", team_code="") | Q(board="teams", team_code__in=TEAM_CODES),
                name="community_post_board_team_valid",
            ),
        )
