from django.db import models
from django.conf import settings # Import settings

# Create your models here.

class NutritionLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='nutrition_logs')
    meal_items_json = models.JSONField() # Stores the meal_items array as JSON
    total_calories = models.FloatField()
    total_carbohydrates_g = models.FloatField()
    total_protein_g = models.FloatField()
    total_fat_g = models.FloatField()
    health_index = models.FloatField(null=True, blank=True)
    logged_at = models.DateTimeField(auto_now_add=True) # Timestamp of acceptance

    def __str__(self):
        return f"Nutrition Log for {self.user.email} at {self.logged_at.strftime('%Y-%m-%d %H:%M')}"
