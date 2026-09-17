from django.urls import include, path


urlpatterns = [path("baseball/", include("baseball.urls"))]
