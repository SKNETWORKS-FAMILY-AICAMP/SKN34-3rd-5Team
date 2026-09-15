from rest_framework import serializers

from .models import CommunityPost


class CommunityPostSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="source_id")
    sourceId = serializers.CharField(source="source_id")
    postNumber = serializers.CharField(source="post_number")
    teamCode = serializers.CharField(source="team_code")
    createdAt = serializers.DateTimeField(source="created_at", allow_null=True)
    commentCount = serializers.IntegerField(source="comment_count")
    isSample = serializers.BooleanField(source="is_sample")

    class Meta:
        model = CommunityPost
        fields = (
            "id", "sourceId", "postNumber", "board", "teamCode", "author", "title", "content",
            "category", "createdAt", "views", "recommendations", "commentCount", "isSample",
        )
