from django.db import models
from django.contrib.auth.models import User, AbstractUser
# Create your models here.


class MyUser(AbstractUser):

    class Meta(AbstractUser.Meta):
        verbose_name = u"用户信息"
        verbose_name_plural = verbose_name


class Group(models.Model):
    name = models.CharField(max_length=128, verbose_name='群组名')

    create_time = models.DateTimeField(auto_now_add=True, verbose_name='添加时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='修改时间')
    delete_time = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')

    class Meta:
        verbose_name = u'群组'
        verbose_name_plural = verbose_name


class GroupMembers(models.Model):
    member = models.ForeignKey('MyUser', db_constraint=False, on_delete=models.CASCADE, related_name='member', verbose_name='群成员')
    group = models.ForeignKey('Group', db_constraint=False, on_delete=models.CASCADE, verbose_name='群')

    create_time = models.DateTimeField(auto_now_add=True, verbose_name='添加时间')

    class Meta:
        verbose_name = '群成员'
        verbose_name_plural = verbose_name
