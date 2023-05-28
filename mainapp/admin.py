from django.contrib import admin
from mainapp.models import UserRating, SaveForLater, Book

# Register your models here.

admin.site.register(UserRating)
admin.site.register(SaveForLater)
admin.site.register(Book)
