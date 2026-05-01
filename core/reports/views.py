import requests as http_requests
from django.db.models import Q
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from children.models import ChildProfile, DoctorChildAccess
from users.permissions import IsDoctorOrParent
from .models import ASDReport, ADHDReport
from .serializers import (
    ASDVideosDoctorSerializer, ASDVideosParentSerializer,
    ASDPhysiologyDoctorSerializer, ASDPhysiologyParentSerializer,
    ADHDReportDoctorSerializer, ADHDReportParentSerializer,
)
from errors.models import SystemErrorLog
from celery.result import AsyncResult
from rest_framework.permissions import IsAuthenticated
from .tasks import (
    process_asd_videos_task,
    process_asd_physiology_task,
    process_adhd_task,
)

ALLOWED_VIDEO_TYPES = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo', 'video/webm', 'video/x-matroska']
ALLOWED_EEG_TYPES   = ['text/csv', 'application/octet-stream', 'application/vnd.ms-excel',
                        'text/plain', 'application/x-edf', 'application/edf']

# EEG/physiology files are commonly .edf, .csv, .bdf, .txt — adjust to your AI server's expectation
def validate_file_type(file, allowed_types, label):
    """Returns an error string if the file content-type is not in allowed_types, else None."""
    if file.content_type not in allowed_types:
        return f"'{label}' must be one of: {', '.join(allowed_types)}. Got: {file.content_type}"
    return None

# Shared helper — used by all views in this file
def get_child_or_403(request, child_id):
    """Returns the ChildProfile if the user is authorized, otherwise returns a 403 Response."""
    if request.user.role == 'parent':
        try:
            return ChildProfile.objects.get(child_id=child_id, created_by=request.user)
        except ChildProfile.DoesNotExist:
            return Response({'error': 'Access denied.'}, status=403)

    elif request.user.role == 'doctor':
        # Doctor either created the child themselves OR was granted access by the parent
        child = ChildProfile.objects.filter(
            Q(child_id=child_id, created_by=request.user) |
            Q(child_id=child_id, authorized_doctors__doctor=request.user)
        ).first()
        
        if child:
            return child
        return Response({'error': 'Access denied.'}, status=403)


# ASD: Videos + Questionnaire
class ASDVideosView(APIView):
    permission_classes = [IsDoctorOrParent]

    # MultiPartParser is needed for file uploads, FormParser is needed for parsing the questionnaire field from form data.
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, child_id):
        # First, check if the child exists and the user has access. If not, return 403 immediately.
        child = get_child_or_403(request, child_id)

        # get_child_or_403 returns either a ChildProfile or a Response. If it's a Response, we should return it immediately.
        if isinstance(child, Response):
            return child

        # Extract files and questionnaire from the request
        motion_video = request.FILES.get('behavioral_video')
        emotion_video = request.FILES.get('emotion_video')
        questionnaire = request.data.get('questionnaire_data')

        # All three are required for the AI server to process. If any is missing, return an error.
        if not all([motion_video, emotion_video, questionnaire]):
            return Response({'error': 'behavioral_video, emotion_video, and questionnaire_data are all required.'}, status=400)
        
        # Validate file types before sending to AI server
        err = validate_file_type(motion_video, ALLOWED_VIDEO_TYPES, 'motion_video')
        if err: return Response({'error': err}, status=400)
        err = validate_file_type(emotion_video, ALLOWED_VIDEO_TYPES, 'emotion_video')
        if err: return Response({'error': err}, status=400)

        # Save videos to disk.
        # update_or_create means: if an ASDReport for this child already exists (e.g. physiology was uploaded first), update it. Otherwise create a new one.
        report, _ = ASDReport.objects.update_or_create(
            child=child,
            defaults={
                "motion_video": motion_video,
                "emotion_video": emotion_video,
                "questionnaire_answers": questionnaire,
            },
        )

        task = process_asd_videos_task.delay(str(report.id))

        return Response({
            "message": "ASD videos processing started.",
            "task_id": task.id,
            "status": "PENDING",
        }, status=202)


    def get(self, request, child_id):
        child = get_child_or_403(request, child_id)
        if isinstance(child, Response):
            return child

        # For GET requests, we return the existing report data. If no report exists, return 404.
        try:
            report = child.asd_report
        except ASDReport.DoesNotExist:
            return Response({'error': 'No ASD report found.'}, status=404)

        # Doctors get more detailed data (including AI response and raw questionnaire).
        if request.user.role == 'doctor':
            return Response(ASDVideosDoctorSerializer(report).data)
        
        # while parents get a simplified view with just risk level and recommendation.
        return Response(ASDVideosParentSerializer(report).data)

# ASD: Physiology File (Page 2 — fully independent)
class ASDPhysiologyView(APIView):
    permission_classes = [IsDoctorOrParent]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, child_id):
        child = get_child_or_403(request, child_id)
        if isinstance(child, Response):
            return child

        eeg_vhdr = request.FILES.get('eeg_vhdr')
        eeg_vmrk = request.FILES.get('eeg_vmrk')
        eeg_data = request.FILES.get('eeg_data')
        if not all([eeg_vhdr, eeg_vmrk, eeg_data]):
            return Response({'error': 'eeg_vhdr, eeg_vmrk, and eeg_data are all required.'}, status=400)
        
        # Validate file type before sending to AI server
        err = validate_file_type(eeg_vhdr, ALLOWED_EEG_TYPES, 'eeg_vhdr')
        if err: return Response({'error': err}, status=400)
        err = validate_file_type(eeg_vmrk, ALLOWED_EEG_TYPES, 'eeg_vmrk')
        if err: return Response({'error': err}, status=400)
        err = validate_file_type(eeg_data, ALLOWED_EEG_TYPES, 'eeg_data')
        if err: return Response({'error': err}, status=400)

        try:
            report = child.asd_report
        except ASDReport.DoesNotExist:
            return Response({'error': 'ASD videos must be processed before physiology files.'}, status=400)

        videos_ai_response = report.videos_ai_response or {}
        observational_probability = videos_ai_response.get('fused_probability')
        if observational_probability is None:
            return Response({
                'error': 'fused_probability is missing. Complete ASD videos processing first.'
            }, status=400)

        report.eeg_vhdr = eeg_vhdr
        report.eeg_vmrk = eeg_vmrk
        report.eeg_data = eeg_data
        report.physiology_ai_response = None
        report.save(update_fields=[
            'eeg_vhdr',
            'eeg_vmrk',
            'eeg_data',
            'physiology_ai_response',
            'updated_at',
        ])

        task = process_asd_physiology_task.delay(str(report.id))

        return Response({
            "message": "ASD physiology processing started.",
            "task_id": task.id,
            "status": "PENDING",
        }, status=202)


    def get(self, request, child_id):
        child = get_child_or_403(request, child_id)
        if isinstance(child, Response):
            return child

        try:
            report = child.asd_report
        except ASDReport.DoesNotExist:
            return Response({'error': 'No ASD report found.'}, status=404)

        if request.user.role == 'doctor':
            return Response(ASDPhysiologyDoctorSerializer(report).data)
        return Response(ASDPhysiologyParentSerializer(report).data)


# ADHD
class ADHDDiagnosisView(APIView):
    permission_classes = [IsDoctorOrParent]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, child_id):
        child = get_child_or_403(request, child_id)
        if isinstance(child, Response):
            return child

        eeg_file = request.FILES.get('eeg_csv')
        if not eeg_file:
            return Response({'error': 'EEG file is required.'}, status=400)
        
        # Validate file type before sending to AI server
        err = validate_file_type(eeg_file, ALLOWED_EEG_TYPES, 'eeg_file')
        if err: return Response({'error': err}, status=400)

        report, _ = ADHDReport.objects.update_or_create(
            child=child,
            defaults={
                "eeg_file": eeg_file,
            },
        )

        task = process_adhd_task.delay(str(report.id))

        return Response({
            "message": "ADHD report processing started.",
            "task_id": task.id,
            "status": "PENDING",
        }, status=202)


    def get(self, request, child_id):
        child = get_child_or_403(request, child_id)
        if isinstance(child, Response):
            return child

        try:
            report = child.adhd_report
        except ADHDReport.DoesNotExist:
            return Response({'error': 'No ADHD report found.'}, status=404)

        if request.user.role == 'doctor':
            return Response(ADHDReportDoctorSerializer(report).data)
        return Response(ADHDReportParentSerializer(report).data)


class TaskStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        task = AsyncResult(task_id)

        response = {
            "task_id": task_id,
            "status": task.status,
        }

        if task.successful():
            response["result"] = task.result

        elif task.failed():
            response["error"] = str(task.result)

        return Response(response)