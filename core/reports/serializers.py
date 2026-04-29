from rest_framework import serializers
from .models import ASDReport, ADHDReport

# ASD: Videos + Questionnaire
class ASDVideosParentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ASDReport
        fields = ['risk_level', 'recommendation', 'updated_at']

class ASDVideosDoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ASDReport
        # Doctor can see the video files and the AI response from the videos
        fields = ['motion_video', 'emotion_video', 'questionnaire_answers',
                  'videos_ai_response', 'risk_level', 'recommendation', 'updated_at']

# ASD: Physiology page
class ASDPhysiologyParentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ASDReport
        fields = ['risk_level', 'recommendation', 'updated_at']

class ASDPhysiologyDoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ASDReport
        fields = ['physiology_file', 'physiology_ai_response',
                  'risk_level', 'recommendation', 'updated_at']

# ADHD
class ADHDReportParentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ADHDReport
        fields = ['risk_level', 'recommendation', 'updated_at']

class ADHDReportDoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ADHDReport
        fields = ['eeg_file', 'ai_full_response', 'risk_level', 'recommendation', 'updated_at']