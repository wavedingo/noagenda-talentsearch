from django.db import models


class Settings(models.Model):
    key = models.CharField(max_length=100, primary_key=True)
    value_json = models.JSONField()

    def __str__(self):
        return self.key
