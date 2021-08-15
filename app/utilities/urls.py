from django.urls import path

from . import scripts

urlpatterns = [
    # scripts
    path("firebase/access/", scripts.FirebaseAccess.as_view()),
]
