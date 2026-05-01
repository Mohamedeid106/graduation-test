from rest_framework import serializers
from .models import ChildProfile, DoctorChildAccess
from datetime import date


class BasicInfoSerializer(serializers.Serializer):
    """Validates basic_info JSONB field structure"""
    full_name = serializers.CharField(max_length=200, required=True)
    date_of_birth = serializers.DateField(required=True)
    age = serializers.IntegerField(min_value=0, required=True)
    gender = serializers.ChoiceField(choices=['male', 'female'], required=True)
    birth_order = serializers.CharField(max_length=100, required=False, allow_blank=True)


class DevMilestonesSerializer(serializers.Serializer):
    """Validates dev_milestones JSONB field structure"""
    age_of_fw = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    age_of_sw = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    lost_skills = serializers.BooleanField(required=False, allow_null=True)
    speech_level = serializers.ChoiceField(
        choices=['non-verbal', 'single words', 'short sentences', 'full sentences'],
        required=False,
        allow_null=True
    )
    gestures_use = serializers.IntegerField(min_value=0, required=False, allow_null=True)


class MedHistorySerializer(serializers.Serializer):
    """Validates med_history JSONB field structure"""
    diagnosed = serializers.ChoiceField(
        choices=['none', 'ASD', 'speech_delay', 'other'],
        required=False,
        allow_null=True
    )
    hear_problem = serializers.BooleanField(required=False, allow_null=True)
    vision_problem = serializers.BooleanField(required=False, allow_null=True)
    fam_history = serializers.ChoiceField(
        choices=['yes', 'no', 'not sure'],
        required=False,
        allow_null=True
    )


class BehaviorSerializer(serializers.Serializer):
    """Validates behavior JSONB field structure"""
    energy_level = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    sensitive_level = serializers.IntegerField(min_value=0, required=False, allow_null=True)


class ChildProfileSerializer(serializers.ModelSerializer):
    """Main serializer for ChildProfile with nested validation"""
    basic_info = BasicInfoSerializer(required=False, allow_null=True)
    dev_milestones = DevMilestonesSerializer(required=False, allow_null=True)
    med_history = MedHistorySerializer(required=False, allow_null=True)
    behavior = BehaviorSerializer(required=False, allow_null=True)

    class Meta:
        model = ChildProfile
        fields = [
            'id', 'child_id', 'basic_info', 'dev_milestones', 'med_history', 'behavior',
            'clinic_note', 'eeg_history', 'created_by', 'created_at',
        ]
        read_only_fields = ['child_id', 'created_by', 'created_at']

    def validate_basic_info(self, value):
        """Validate basic_info structure"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError("basic_info must be a dictionary")
        
        # Ensure date_of_birth is always stored as a plain string inside JSONB
        if value and 'date_of_birth' in value:
            if isinstance(value['date_of_birth'], date):
                value['date_of_birth'] = value['date_of_birth'].isoformat()
        return value

    def validate_dev_milestones(self, value):
        """Validate dev_milestones structure"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError("dev_milestones must be a dictionary")
        return value

    def validate_med_history(self, value):
        """Validate med_history structure"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError("med_history must be a dictionary")
        return value

    def validate_behavior(self, value):
        """Validate behavior structure"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError("behavior must be a dictionary")
        return value

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        json_fields = ['basic_info', 'dev_milestones', 'med_history', 'behavior']

        for field in json_fields:
            if field in validated_data and validated_data[field] is not None:
                current_value = getattr(instance, field) or {}
                new_value = validated_data[field] or {}
                validated_data[field] = {**current_value, **new_value}

        return super().update(instance, validated_data)


class ChildAccessSerializer(serializers.Serializer):
    """Serializer for doctor access credentials"""
    child_id = serializers.CharField(max_length=20)
    password = serializers.CharField(max_length=255)


class ClinicNoteSerializer(serializers.ModelSerializer):
    """Serializer for updating clinic notes only"""
    class Meta:
        model = ChildProfile
        fields = ['clinic_note']
