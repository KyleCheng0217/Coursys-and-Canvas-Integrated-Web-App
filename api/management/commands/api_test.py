from accounts.models import Student
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
import requests

from pprint import pprint

class Command(BaseCommand):
    help = "Full test of the project's API"

    def handle(self, *args, **options):
        # Check that the user has registered
        student_id = input('Enter student ID: ')
        password = input('Enter password: ')
        s = Student.objects.filter(student_id=student_id)
        if len(s) != 1:
            raise CommandError('No users have been logged out')
        
        token = requests.post('http://app:8000/api/obtain-token/', data={'username': student_id, 'password': password})
        token = token.json()['token']
        print(token)
        response = requests.get('http://app:8000/api/all-courses/', headers={'Authorization': 'Token %s' % token})
        if response.status_code != 200:
            raise CommandError('Could not get all courses')

        for course in response.json():
            assignments = requests.get('http://app:8000/api/assignments/%s/' % course['id'], headers={'Authorization': 'Token %s' % token})
            if assignments.status_code != 200:
                raise CommandError('Could not get %s assignments' % course['courseCode'])
            assignments = assignments.json()
            print(len(assignments))
            pprint(assignments[0] if len(assignments) > 0 else 'No assignments')
        
        self.stdout.write(self.style.SUCCESS('Test succeeded'))
        
