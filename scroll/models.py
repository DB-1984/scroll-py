from django.db import models 
from django.contrib.auth.models import User 

class Label(models.Model):
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#e4e4e7") # Zinc-200 hex

    def __str__(self):
        return self.name

class Entry(models.Model): 
    user = models.ForeignKey(User, on_delete=models.CASCADE) 
    label = models.ForeignKey(Label, on_delete=models.SET_NULL, null=True, blank=True, related_name="entries")
    body = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Entries" 

    def __str__(self):
        return f"{self.user.username}: {self.body[:20]}"