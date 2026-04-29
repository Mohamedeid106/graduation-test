from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.contrib.auth.hashers import check_password
from .models import ChildProfile, DoctorChildAccess
from .serializers import ChildProfileSerializer, ChildAccessSerializer, ClinicNoteSerializer
from users.permissions import IsDoctorOrParent, IsDoctor

class ChildProfileListCreateView(APIView):
    permission_classes = [IsDoctorOrParent]

    def get(self, request):
        """Return all children created by this user"""
        children = ChildProfile.objects.filter(
            Q(created_by=request.user) |
            Q(authorized_doctors__doctor=request.user)
        ).distinct()
        
        serializer = ChildProfileSerializer(children, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create a new child profile"""
        serializer = ChildProfileSerializer(data=request.data)
        if serializer.is_valid():
            child = serializer.save(created_by=request.user)

            if request.user.role == 'doctor':
                DoctorChildAccess.objects.get_or_create(doctor=request.user, child=child)

            return Response({
                'message': 'Child profile created.',
                'child_id': child.child_id,
                'password': child.raw_password,  # shown ONCE — parent shares this with doctor
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ChildProfileDetailView(APIView):
    permission_classes = [IsDoctorOrParent]

    def get_child(self, request, child_id):
        return ChildProfile.objects.filter(
            Q(child_id=child_id, created_by=request.user) |
            Q(child_id=child_id, authorized_doctors__doctor=request.user)
        ).first()

    def patch(self, request, child_id):
        child = self.get_child(request, child_id)
        if not child:
            return Response({'error': 'Access denied.'}, status=403)
        
        serializer = ChildProfileSerializer(child, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Child profile updated.'})
        return Response(serializer.errors, status=400)
    
    def delete(self, request, child_id):
        """Only the creator can delete a child profile"""
        child = ChildProfile.objects.filter(
            child_id=child_id, created_by=request.user
        ).first()

        if not child:
            return Response(
                {'error': 'Access denied. Only the creator can delete this profile.'},
                status=403
            )
        
        child_name = child.basic_info.get('full_name', child_id) if child.basic_info else child_id
        child.delete()
        return Response({'message': f'Child profile "{child_name}" deleted.'}, status=200)

class DoctorAccessView(APIView):
    permission_classes = [IsDoctor]

    def post(self, request):
        """Doctor enters child_id + password to gain access"""
        serializer = ChildAccessSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            child = ChildProfile.objects.get(child_id=serializer.validated_data['child_id'])
        except ChildProfile.DoesNotExist:
            return Response({'error': 'Child not found'}, status=404)

        if not check_password(serializer.validated_data['password'], child.hashed_password):
            return Response({'error': 'Incorrect password'}, status=403)

        # Grant access (ignore if already granted)
        if DoctorChildAccess.objects.filter(doctor=request.user, child=child).exists():
            return Response({'error': 'You already have access to this child profile.'}, status=400)
        DoctorChildAccess.objects.create(doctor=request.user, child=child)
        
        # Extract child name from basic_info JSONB field
        child_name = "Child"
        if child.basic_info and 'full_name' in child.basic_info:
            child_name = child.basic_info['full_name']
        
        return Response({'message': f'Access granted to {child_name}.'})

class ClinicNoteView(APIView):
    permission_classes = [IsDoctor]

    def patch(self, request, child_id):
        """Doctor adds/updates the clinic note on a child profile"""
        try:
            access = DoctorChildAccess.objects.get(doctor=request.user, child__child_id=child_id)
        except DoctorChildAccess.DoesNotExist:
            return Response({'error': 'Access denied'}, status=403)

        serializer = ClinicNoteSerializer(access.child, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Clinic note updated.'})
        return Response(serializer.errors, status=400)