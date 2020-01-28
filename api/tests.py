from django.test import TestCase, Client
import json

from accounts.models import Student

# Create your tests here.
class APITest(TestCase):
    def setUp(self):
        self.student_id = 'a'
        self.password = 'a'
        s = Student.objects.filter(student_id=self.student_id)
        self.assertEqual(len(s), 1, msg="The test assumes that there is a user with student id 'a' and password 'a'")

    def test_all(self):
        # s = Student(student_id=self.student_id, password=self.password, email='%s@gmail.com' % self.student_id)
        # s.set_password(self.password)
        # s.save()

        c = Client()
        token = c.post('api/obtain-token/', {'username': self.student_id, 'password': self.password})
        token = token.json()['token']
        print(token)
        response = c.get('api/all-courses/', authorization='Token %s' % token)
        self.assertTrue(response.status_code == 200)
        response = response.json()
        self.assertNotEqual(len(response), 0)
        print(response[0])
