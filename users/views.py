from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate, login
# from rest_framework_simplejwt.tokens import RefreshToken # Removed for direct use of MyTokenObtainPairSerializer
from .serializers import UserRegisterSerializer, UserLoginSerializer, MyTokenObtainPairSerializer # Modified
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView # New, for direct use in LoginView

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserRegisterSerializer

class LoginView(APIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        user = authenticate(request, username=email, password=password)

        if user is not None:
            # Use the custom serializer to get tokens with email in payload
            custom_token_serializer = MyTokenObtainPairSerializer(data={
                'email': email,
                'password': password
            })
            custom_token_serializer.is_valid(raise_exception=True)
            return Response(custom_token_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
