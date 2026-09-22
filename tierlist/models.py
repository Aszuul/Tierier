from django.db import models
from django.conf import settings


class TierList(models.Model):
    id = models.AutoField(primary_key=True)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tier_list',
    )
    name = models.CharField(max_length=100, default='My tier list')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Choice(models.Model):
    id = models.AutoField(primary_key=True)
    tier_list = models.ForeignKey(TierList, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

class Category(models.Model):
    id = models.AutoField(primary_key=True)
    tier_list = models.ForeignKey(TierList, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    weight = models.FloatField(default=0.1)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weight__gte=0.1),
                name="weight_gte_point_one"
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