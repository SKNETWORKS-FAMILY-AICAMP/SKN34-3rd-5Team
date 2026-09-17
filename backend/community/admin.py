from django.contrib import admin

from .models import CommunityComment, CommunityPost, CommunityReport, CommunityVote, GamePrediction, PredictionGame


@admin.register(CommunityPost)
class CommunityPostAdmin(admin.ModelAdmin):
    list_display = ("post_number", "board", "team_code", "author", "created_at")
    search_fields = ("=post_number", "source_id", "title", "author")
    list_filter = ("board", "team_code", "is_sample")


admin.site.register((CommunityComment, CommunityVote, CommunityReport, PredictionGame, GamePrediction))
