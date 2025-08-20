from django.urls import path
from .views import NutritionAnalysisView, NutritionLogCreateView, NutritionSummaryView

urlpatterns = [
    path('analyze/', NutritionAnalysisView.as_view(), name='analyze_nutrition'),
    path('log/', NutritionLogCreateView.as_view(), name='log_nutrition'),
    path('summary/', NutritionSummaryView.as_view(), name='nutrition_summary'),
]
