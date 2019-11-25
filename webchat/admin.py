from django.contrib import admin

# Register your models here.
from .models import MyUser


class UserProfileAdmin(admin.ModelAdmin):
    pass


admin.site.register(MyUser, UserProfileAdmin)