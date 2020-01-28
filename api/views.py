from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import Http404

from accounts.views import canvas_primary_query, coursys_primary_request

from pprint import pprint

class AllCoursesView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        response = []
        canvas_courses = canvas_primary_query(request.user)
        for course in canvas_courses:
            response.append({
                'id': course['id'],
                'courseCode': course['courseCode'].split(' ')[0],
                'name': course['name'],
            })
        coursys_courses = coursys_primary_request(request.user)
        for course in coursys_courses:
            courseCode = course['subject'] + course['number']
            response.append({
                'id': course['slug'],
                'courseCode': courseCode,
                'name': courseCode + ' ' + course['title'],
            })
        # pprint(response)
        return Response(response)

class AssignmentsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, course_id):
        response = []
        canvas_courses = canvas_primary_query(request.user)
        course = [course for course in canvas_courses if course['id'] == course_id]
        if len(course) == 0:
            coursys_courses = coursys_primary_request(request.user)
            try:
                course = [course for course in coursys_courses if course['slug'] == course_id][0]
            except IndexError:
                raise Http404('Course not found')
            for assignment in course['assignments']:
                response.append({
                    'name': assignment['name'],
                    'url': assignment['url'],
                    'due_date': assignment['due_date'],
                    'grade': [grade_info['grade'] for grade_info in course['grades'] if grade_info['slug'] == assignment['slug']][0],
                    'max_grade': assignment['max_grade'],
                })
        
        else:
            course = course[0]
            for assignment in course['assignmentsConnection']['nodes']:
                try:
                    assignment_grade = assignment['submissionsConnection']['nodes'][0]['grade']
                except:
                    assignment_grade = None
                response.append({
                    'name': assignment['name'],
                    'url': assignment['htmlUrl'],
                    'due_date': assignment['dueAt'],
                    'grade': assignment_grade,
                    'max_grade': assignment['pointsPossible'],
                })
        
        # pprint(response)
        return Response(response)