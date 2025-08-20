from rest_framework import serializers
from .models import NutritionLog

class ImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()

class NutritionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutritionLog
        fields = [
            'meal_items_json',
            'total_calories',
            'total_carbohydrates_g',
            'total_protein_g',
            'total_fat_g',
            'health_index',
            # 'logged_at' and 'user' will be handled by the view
        ]

class MealItemSerializer(serializers.Serializer):
    name = serializers.CharField()
    estimated_weight_g = serializers.FloatField()
    calories = serializers.FloatField()
    macronutrients = serializers.JSONField()

class DailySummarySerializer(serializers.Serializer):
    date = serializers.DateField()
    total_calories = serializers.FloatField()
    total_carbohydrates_g = serializers.FloatField()
    total_protein_g = serializers.FloatField()
    total_fat_g = serializers.FloatField()
    total_estimated_weight_g = serializers.FloatField()
    average_health_index = serializers.FloatField()
    meals_count = serializers.IntegerField()
    meals = NutritionLogSerializer(many=True, read_only=True)
