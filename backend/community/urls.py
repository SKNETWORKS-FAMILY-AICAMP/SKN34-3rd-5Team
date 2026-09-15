from django.urls import path

from .views import CommunityPostListView

urlpatterns = [
    path("posts/", CommunityPostListView.as_view(), name="community-post-list"),
]
