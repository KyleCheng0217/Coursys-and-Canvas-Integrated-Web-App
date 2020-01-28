from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
# Create your models here.
class StudentManager(BaseUserManager):
    def create_user(self, student_id):
        user = self.model(student_id=student_id)
        user.save(using=self._db)
        return user

class Student(AbstractBaseUser):
    first_name = models.CharField(max_length=32)
    last_name = models.CharField(max_length=32)
    student_id = models.CharField(max_length=32, unique=True)
    email = models.EmailField()
    coursys_access_token = models.CharField(max_length=256)             # Permanent token that we need to obtain only once for each user
    coursys_access_token_secret = models.CharField(max_length=256)      # It's corresponding secret
    canvas_token = models.CharField(max_length=256)                     # Also permanent

    USERNAME_FIELD = 'student_id'
    EMAIL_FIELD = 'email'
    # REQUIRED_FIELDS = ['first_name', 'last_name', 'student_id', 'email']
    # REQUIRED_FIELDS = ['canvas_token', 'coursys_token']

    objects = StudentManager()

    def get_full_name(self):
        return self.last_name + ' ' + self.first_name

    def get_short_name(self):
        return self.student_id

    def __str__(self):
        return self.student_id

    def has_coursys_access(self):
        return self.coursys_access_token and self.coursys_access_token_secret

# Temporary tokens used in the process of authentication
class CoursysRequestToken(models.Model):
    owner = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='coursys',
    )
    request_token = models.CharField(max_length=256)
    request_token_secret = models.CharField(max_length=256)
    authorize_url = models.CharField(max_length=256)

# Store descriptions of activities (used in weekly schedule)
class ActivityDescription(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    slug = models.CharField(max_length=128)
    description = models.TextField()

