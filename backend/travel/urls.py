from django.urls import path

from .views import CourseDetailView, CourseListCreateView

urlpatterns = [
    path("courses/", CourseListCreateView.as_view(), name="course-list"),
    path("courses/<uuid:pk>/", CourseDetailView.as_view(), name="course-detail"),
]
