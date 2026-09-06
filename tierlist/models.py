from django.db import models
from django.db.models.functions import Lower

class Choice(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

class Category(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    weight = models.FloatField(default=0)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weight__gte=0),
                name="weight_gte_zero"
            ),
            models.CheckConstraint(
                condition=models.Q(weight__lte=1),
                name="weight_lte_one"
            ),
        ]

class CategoryChoice(models.Model):
    id = models.AutoField(primary_key=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'choice'],
                name='unique_category_choice'
            ),
        ]