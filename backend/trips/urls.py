from django.urls import path

from . import views

urlpatterns = [
    path("trip-plan", views.TripPlanView.as_view(), name="trip-plan"),
]
