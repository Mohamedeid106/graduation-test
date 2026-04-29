from rest_framework import serializers
from .models import User

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirmation = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password',
                  'password_confirmation', 'phone_number', 'role']

    # Custom validation to ensure passwords match and prevent self-registration as admin
    def validate(self, data):
        if data['password'] != data['password_confirmation']:
            raise serializers.ValidationError("Passwords do not match.")
        if data['role'] == 'admin':
            raise serializers.ValidationError("Cannot self-register as Admin.")
        return data

    # Override create to handle password hashing and remove password_confirmation from the validated data
    def create(self, validated_data):
        validated_data.pop('password_confirmation')
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    # Read-only serializer for user profile details
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number', 'role', 'created_at']


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False)
    new_password = serializers.CharField(write_only=True, min_length=8, required=False)
    new_password_confirmation = serializers.CharField(write_only=True, required=False)
    current_password = serializers.CharField(write_only=True, required=False)

    # Only allow updating certain fields and handle password/email changes with validation
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'email',
                  'current_password', 'new_password', 'new_password_confirmation']

    def validate(self, data):
        # Get the user instance from the serializer context
        user = self.instance

        # If user wants to change email or password, current_password is mandatory
        changing_sensitive = 'email' in data or 'new_password' in data
        if changing_sensitive:
            if not data.get('current_password'):
                raise serializers.ValidationError(
                    {'current_password': 'Current password is required to change email or password.'}
                )
            if not user.check_password(data['current_password']):
                raise serializers.ValidationError(
                    {'current_password': 'Current password is incorrect.'}
                )

        # If changing password, confirmation must match and it must not be the same as current password
        if 'new_password' in data:
            if data.get('new_password') != data.get('new_password_confirmation'):
                raise serializers.ValidationError(
                    {'new_password_confirmation': 'Passwords do not match.'}
                )
            
            if user.check_password(data['new_password']):
                raise serializers.ValidationError(
                    {'new_password': 'This is already your current password.'}
                )

        # If changing email, it must not already exist and it must not be the same as current email
        if 'email' in data:
            if User.objects.exclude(pk=user.pk).filter(email=data['email']).exists():
                raise serializers.ValidationError(
                    {'email': 'This email is already in use.'}
                )
            
            if data['email'] == user.email:
                raise serializers.ValidationError(
                    {'email': 'This is already your current email.'}
                )

        return data

    def update(self, instance, validated_data):
        # Strip fields that are not model fields before saving
        validated_data.pop('current_password', None)
        validated_data.pop('new_password_confirmation', None)
        new_password = validated_data.pop('new_password', None)

        # Update the user instance with the validated data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # If a new password was provided, set it using the set_password method to ensure it's hashed
        if new_password:
            instance.set_password(new_password)

        instance.save()
        return instance