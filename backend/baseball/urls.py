from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RESOURCE_VIEWSETS, public_urlpatterns

router = DefaultRouter()
for resource, viewset in RESOURCE_VIEWSETS.items():
    router.register(resource, viewset, basename=f"baseball-{resource}")

urlpatterns = [path("manage/", include(router.urls)), *public_urlpatterns]
