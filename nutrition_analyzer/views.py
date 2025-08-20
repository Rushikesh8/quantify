import base64
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, status, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from django.conf import settings
from openai import OpenAI
from .serializers import ImageUploadSerializer, NutritionLogSerializer, DailySummarySerializer # New import
from .models import NutritionLog # Added import for NutritionLog
from django.db.models import Sum, Avg # New import
from datetime import datetime, timedelta

class NutritionAnalysisView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        serializer = ImageUploadSerializer(data=request.data)
        if serializer.is_valid():
            image_file = serializer.validated_data['image']

            # Read image data and encode to base64
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')

            # OpenAI API call
            try:
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                
                prompt_text = (
                    "You are a nutrition analysis assistant. I will provide you with a photo of a meal. "
                    "Your task is to:\n\n" +
                    "1. Identify the food items in the photo.\n" +
                    "2. Estimate the total calories for the meal.\n" +
                    "3. Provide a detailed macronutrient breakdown:\n" +
                    "   - Carbohydrates (g)\n" +
                    "   - Protein (g)\n" +
                    "   - Fat (g)\n" +
                    "4. Estimate the approximate weight (in grams) of the meal or each major food item.\n" +
                    "5. Calculate a simple \"health index\" for the meal on a scale of 1 to 10, "
                    "where 1 = unhealthy (very high sugar/fat, low nutrition) and 10 = very healthy (balanced macros, nutrient dense). \n" +
                    "6. Return the output strictly in **structured JSON format** as follows:\n\n" +
                    "```json\n" +
                    "{\n  \"meal_items\": [\n    {\n      \"name\": \"string\",\n      \"estimated_weight_g\": number,\n      \"calories\": number,\n      \"macronutrients\": {\n        \"carbohydrates_g\": number,\n        \"protein_g\": number,\n        \"fat_g\": number\n      }\n    }\n  ],\n  \"total\": {\n    \"estimated_weight_g\": number,\n    \"calories\": number,\n    \"carbohydrates_g\": number,\n    \"protein_g\": number,\n    \"fat_g\": number\n  },\n  \"health_index\": number\n}\n" +
                    "```"
                )

                response = client.chat.completions.create(
                    model="gpt-4o", # or "gpt-4-turbo" for vision capabilities
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}",
                                        "detail": "low" # or "high"
                                    },
                                },
                            ],
                        }
                    ],
                    max_tokens=1000,
                )

                # Extract and parse the JSON response from OpenAI
                openai_response_content = response.choices[0].message.content
                
                # The response content might be wrapped in ```json ... ```
                if openai_response_content.startswith("```json") and openai_response_content.endswith("```"):
                    json_string = openai_response_content[len("```json\n"): -len("```")].strip()
                else:
                    json_string = openai_response_content.strip()

                try:
                    nutrition_data = json.loads(json_string)
                    return Response(nutrition_data, status=status.HTTP_200_OK)
                except json.JSONDecodeError:
                    return Response({"error": "Failed to parse JSON from OpenAI response", "raw_response": openai_response_content}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class NutritionLogCreateView(generics.CreateAPIView):
    queryset = NutritionLog.objects.all()
    serializer_class = NutritionLogSerializer
    permission_classes = [permissions.IsAuthenticated] # Only authenticated users can log nutrition

    def perform_create(self, serializer):
        # The request.user is available because of JWTAuthentication
        serializer.save(user=self.request.user, meal_items_json=self.request.data.get('meal_items'))

    def post(self, request, *args, **kwargs):
        # We expect the full JSON response from OpenAI to be sent here by the frontend
        data = request.data
        
        # Manually extract fields for the serializer
        serializer_data = {
            'total_calories': data.get('total', {}).get('calories'),
            'total_carbohydrates_g': data.get('total', {}).get('carbohydrates_g'),
            'total_protein_g': data.get('total', {}).get('protein_g'),
            'total_fat_g': data.get('total', {}).get('fat_g'),
            'health_index': data.get('health_index'),
            'meal_items_json': data.get('meal_items'), # Pass the list directly, JSONField will handle it
        }

        serializer = self.get_serializer(data=serializer_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class NutritionSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not start_date_str or not end_date_str:
            return Response({"error": "Please provide both start_date and end_date query parameters (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Ensure end_date includes the entire day
        end_datetime = datetime.combine(end_date, datetime.max.time())

        logs = NutritionLog.objects.filter(
            user=user,
            logged_at__range=(start_date, end_datetime)
        ).order_by('logged_at')

        # Group logs by day
        daily_summaries = {}
        for log in logs:
            log_date = log.logged_at.date()
            if log_date not in daily_summaries:
                daily_summaries[log_date] = {
                    'date': log_date,
                    'total_calories': 0,
                    'total_carbohydrates_g': 0,
                    'total_protein_g': 0,
                    'total_fat_g': 0,
                    'total_estimated_weight_g': 0,
                    'health_index_sum': 0,
                    'meals_count': 0,
                    'meals': []
                }
            
            summary = daily_summaries[log_date]
            summary['total_calories'] += log.total_calories
            summary['total_carbohydrates_g'] += log.total_carbohydrates_g
            summary['total_protein_g'] += log.total_protein_g
            summary['total_fat_g'] += log.total_fat_g
            # Note: total_estimated_weight_g is not directly logged per meal item in NutritionLog
            # If you need this, you would need to adjust NutritionLog model or calculate from meal_items_json
            # For now, we'll sum up total_estimated_weight_g from the 'total' field of the logged data
            if 'total' in log.meal_items_json and 'estimated_weight_g' in log.meal_items_json['total']:
                summary['total_estimated_weight_g'] += log.meal_items_json['total']['estimated_weight_g']
            
            if log.health_index is not None:
                summary['health_index_sum'] += log.health_index
            summary['meals_count'] += 1
            summary['meals'].append(log) # Append the full log object for nested serialization

        # Calculate averages and prepare final response
        results = []
        for date, summary in sorted(daily_summaries.items()):
            if summary['meals_count'] > 0:
                summary['average_health_index'] = summary['health_index_sum'] / summary['meals_count']
            else:
                summary['average_health_index'] = None
            
            # Remove temporary sum field
            del summary['health_index_sum']
            
            # Serialize individual meals using NutritionLogSerializer
            summary['meals'] = NutritionLogSerializer(summary['meals'], many=True).data

            results.append(DailySummarySerializer(summary).data)
            
        return Response(results, status=status.HTTP_200_OK)
