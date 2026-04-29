from django.urls import path
from .views import ChildProfileListCreateView, ChildProfileDetailView, DoctorAccessView, ClinicNoteView

urlpatterns = [
    path('', ChildProfileListCreateView.as_view()),
    path('access/', DoctorAccessView.as_view()),
    path('<str:child_id>/', ChildProfileDetailView.as_view()),
    path('<str:child_id>/clinic-note/', ClinicNoteView.as_view()),
]