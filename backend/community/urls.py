from django.urls import path

from .interactions import CommentDetailView, CommentListCreateView, ReportCreateView, VoteView
from .images import CommunityImageDetailView, CommunityImageUploadView
from .predictions import prediction_game_detail, prediction_game_list, prediction_game_vote
from .views import CommunityPostDetailView, CommunityPostListCreateView

urlpatterns = [
    path("images/", CommunityImageUploadView.as_view(), name="community-image-upload"),
    path("images/<str:image_id>/", CommunityImageDetailView.as_view(), name="community-image-detail"),
    path("posts/", CommunityPostListCreateView.as_view(), name="community-post-list"),
    path("posts/<str:source_id>/", CommunityPostDetailView.as_view(), name="community-post-detail"),
    path("posts/<str:source_id>/comments/", CommentListCreateView.as_view()),
    path("comments/<int:comment_id>/", CommentDetailView.as_view()),
    path("posts/<str:source_id>/vote/", VoteView.as_view()),
    path("posts/<str:source_id>/reports/", ReportCreateView.as_view()),
    path("predictions/games/", prediction_game_list),
    path("predictions/games/<str:game_id>/", prediction_game_detail),
    path("predictions/games/<str:game_id>/vote/", prediction_game_vote),
]
