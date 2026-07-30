from django.db import models
from django.db.models.functions import Lower

class Choice(models.Model):
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    class Meta:
        ordering = [Lower("name")]