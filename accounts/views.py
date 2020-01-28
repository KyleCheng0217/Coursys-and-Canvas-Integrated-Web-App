from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.urls import reverse

from django.utils.dateparse import parse_datetime
from django.utils import timezone
from datetime import timedelta

import requests

# Create your views here.
from django.contrib.auth.decorators import login_required
from .models import Student, ActivityDescription
from django.core.cache import cache

from authentication.views import get_coursys_session

from pprint import pprint
import time

from collections import defaultdict

CANVAS_SFU_CA = "https://canvas.sfu.ca"
COURSYS_SFU_CA = "https://coursys.sfu.ca"

GRAPHQL_ENDPOINT = CANVAS_SFU_CA + '/api/graphql'

GRAPHQL_PRIMARY_QUERY = \
"""
{
    allCourses {
        id
        _id
        name
        courseCode
        term {
            id
            name
        }
    }
}
"""

GRAPHQL_COURSE_QUERY = \
"""
%s: course(id: "%s") {
    assignmentsConnection {
        nodes {
            id
            name
            htmlUrl
            description
            dueAt
            pointsPossible
            submissionsConnection {
                nodes {
                    grade
                }
            }
        }
    }
}
"""

class CanvasError(Exception):
    pass

class CoursysError(Exception):
    pass

def determine_current_semester():
    current_datetime = timezone.now()
    current_month = current_datetime.month  # Values from 1 to 12
    current_year = str(current_datetime.year)
    if current_month <= 4:
        return "Spring " + current_year
    elif current_month <= 8:
        return "Summer " + current_year
    else:
        return "Fall " + current_year

# Get all Canvas data, including assignments and grades
def canvas_primary_query(user):

    def request():
        print("new canvas request")
        response = requests.post(
            GRAPHQL_ENDPOINT,
            headers={"Authorization": "Bearer " + user.canvas_token},
            data={"query": GRAPHQL_PRIMARY_QUERY}
        ).json()
        if 'errors' in response:
            raise CanvasError(str(response['errors']))
        response = response['data']['allCourses']
        current_semester = determine_current_semester()
        current_courses = [course for course in response if course['term']['name'] == current_semester]
        refresh_canvas_info(user, courses=current_courses)
        return current_courses

    return cache.get_or_set("canvas_" + user.student_id, request, timeout=None)

# Add or update the 'assignmentsConnection' key in the Canvas courses
def refresh_canvas_info(user, courses=None):
    print("refresh canvas")
    update_cache = False
    if courses is None:
        update_cache = True
        courses = cache.get("canvas_" + user.student_id)
    GRAPHQL_COURSE_QUERIES = [GRAPHQL_COURSE_QUERY % (course['id'], course['id']) for course in courses]
    GRAPHQL_EXTENDED_QUERY = '\n'.join(GRAPHQL_COURSE_QUERIES)
    GRAPHQL_EXTENDED_QUERY = '{\n%s\n}' % GRAPHQL_EXTENDED_QUERY
    response = requests.post(
        GRAPHQL_ENDPOINT,
        headers={"Authorization": "Bearer " + user.canvas_token},
        data={"query": GRAPHQL_EXTENDED_QUERY}
    ).json()
    if 'errors' in response:
        raise CanvasError(str(response['errors']))
    response = response['data']
    for course in courses:
        course['assignmentsConnection'] = response[course['id']]['assignmentsConnection']
    if update_cache:
        cache.set("canvas_" + user.student_id, courses, timeout=None)


# List of courses hardly ever changes, so we can cache ir for an hour
# This function should only be called from views with @login_required decorator
# @cache_page(60 * 60)
def get_canvas_courses(user):
    """
    This function is depreceated, use GraphQL query instead
    """
    COURSES_URL = CANVAS_SFU_CA + "/api/v1/courses"

    # Create a callable, but do not execute it unless the cache hasn't been set
    def request(): return requests.get(url=COURSES_URL, headers={
        "Authorization": "Bearer " + user.canvas_token}, params={"include[]": "term"}).json()

    return cache.get_or_set('canvas_courses_' + user.student_id, request, timeout=None)

# Get all Coursys courses, icluding their assignments and grades
def coursys_primary_request(user):
    # COURSES_URL = COURSYS_SFU_CA + "/api/1/offerings"
    COURSES_URL = 'https://coursys.sfu.ca/api/1/offerings/'

    # Create but do not execute the callable that retreives Coursys session and requests the list of courses
    def request():
        print("new coursys request")
        # Get the list of courses
        session = get_coursys_session(user.coursys_access_token, user.coursys_access_token_secret)
        courses = session.get(COURSES_URL).json()
        if isinstance(courses, dict) and 'detail' in courses:
            raise CoursysError(courses['detail'])
        # Filter the courses in current semester
        current_semester = max([course['semester'] for course in courses])
        courses = [course for course in courses if course['semester'] == current_semester]
        # Add information about the assignments and grades
        for course in courses:
            course_details = session.get(course['link']).json()
            course['assignments'] = session.get(course_details['links']['activities']).json()
            course['grades'] = session.get(course_details['links']['grades']).json()
        return courses
        
    return cache.get_or_set('coursys_courses_' + user.student_id, request, timeout=None)

# Update grades and assignments of Coursys courses
def refresh_coursys_info(user):
    print("refresh coursys")
    courses = cache.get('coursys_courses_' + user.student_id)
    assert(courses is not None)
    session = get_coursys_session(user.coursys_access_token, user.coursys_access_token_secret)
    for course in courses:
        course_details = session.get(course['link']).json()
        course['assignments'] = session.get(course_details['links']['activities']).json()
        course['grades'] = session.get(course_details['links']['grades']).json()
    cache.set('coursys_courses_' + user.student_id, courses, timeout=None)

def get_current_courses_and_assignments(user):
    # Create a list of tuples (course name, assignments list) where each element in assignments list is also a tuple (name, due date)
    coursys_courses = coursys_primary_request(user)
    courses = [
        (course['title'],
        [(assignment['name'], assignment['due_date']) for assignment in course['assignments']]) for course in coursys_courses
    ]

    canvas_courses = canvas_primary_query(user)
    courses.extend([
        (course['name'],
        [(assignment['name'], assignment['dueAt']) for assignment in course['assignmentsConnection']['nodes']]) for course in canvas_courses
    ])

    return courses

def coursys_api_call(user, URL):
    return get_coursys_session(user.coursys_access_token, user.coursys_access_token_secret).get(URL).json()

def get_current_courses(user):
    canvas_courses = canvas_primary_query(user)
    current_semester = determine_current_semester()
    
    if 'errors' in canvas_courses:
        return [str(canvas_courses['errors'])]
    canvas_courses = canvas_courses['data']['allCourses']
    current_courses = [course['name'] for course in canvas_courses if course['term']['name'] == current_semester]

    coursys_courses = coursys_primary_request(user)
    current_semester = max([course['semester'] for course in coursys_courses])
    current_courses.extend([course['title'] for course in coursys_courses if course['semester'] == current_semester])

    return current_courses

def get_current_canvas_assignments_old(user):
    canvas_courses = canvas_primary_query(user)
    if 'errors' in canvas_courses:
        return [str(canvas_courses['errors'])]

    # create a dictionary with name as key, and assignmentConnections["nodes"] as value
    # value is a list of assignments, where a node is an assignment
    course_assignment_dict = {}
    course_id = []
    for course in canvas_courses:
        course_assignment_dict[course["name"]] = course['assignmentsConnection']['nodes']
        course_id.append(course['_id'])

    GRAPHQL_ENDPOINT = CANVAS_SFU_CA + '/api/graphql'

    GRAPHQL_GRADE_QUERY_TEMPLATE = \
    """
    {
        course(id: "%s") {
            name
            assignmentsConnection {
                nodes {
                    name
                    submissionsConnection {
                        nodes {
                            grade
                        }
                    }
                }
            }
        }
    }
    """


    current_assignments = []
    # request grades based on individual course ID
    for i in range(len(course_id)):
        GRAPHQL_GRADE_QUERY = GRAPHQL_GRADE_QUERY_TEMPLATE % course_id[i]
        
        # Cache grades for 5 minutes, can be removed later in production
        def request():
            return requests.post(
                GRAPHQL_ENDPOINT,
                headers={"Authorization": "Bearer " + user.canvas_token},
                data={"query": GRAPHQL_GRADE_QUERY}
            ).json()
        response = cache.get_or_set(user.student_id + course_id[i], request, timeout=300)
        if 'errors' in response:
            raise CanvasError(str(response['errors']))
        response = response['data']['course']['assignmentsConnection']['nodes']       

        assignment_grade_dict = {}
        for asn in response:         
            assignment_grade_dict[asn['name']] = asn['submissionsConnection']['nodes']

        #extract individual assignments and put append to a single list to return
        for course_name, assignments in course_assignment_dict.items():
            for assign in assignments:
                for assignment_name, grades in assignment_grade_dict.items():
                    if assign["name"] == assignment_name:
                        course_assignments = [(course_name,assign["name"],assign["dueAt"],\
                        	grade["grade"],assign["pointsPossible"]) for grade in grades]             
                        current_assignments += course_assignments

    return current_assignments

# Collect data for assignments page from Canvas
def get_current_canvas_assignments(user):
    canvas_courses = canvas_primary_query(user)
    current_assignments = list()

    for course in canvas_courses:
        for assignment in course['assignmentsConnection']['nodes']:
            for grade in assignment['submissionsConnection']['nodes']:
                current_assignments.append((
                    course['name'],
                    assignment['name'],
                    assignment['dueAt'],
                    grade['grade'],
                    assignment['pointsPossible'],
                    assignment['htmlUrl']
                ))
    return current_assignments

# Collect data for assignments page from Coursys
def get_current_coursys_assignments(user):
    coursys_courses = coursys_primary_request(user)

    all_course_assignments = []
    for course in coursys_courses:
        course_title = course["title"]
        assign_data = []
        grades_data = []
        for assign in course["assignments"]:
            assign_data.append((assign["name"],assign["due_date"], assign["url"]))
        for grades in course["grades"]:
            grades_data.append((grades["grade"], grades["max_grade"]))
        assert(len(assign_data) == len(grades_data))
        for i in range(len(assign_data)):
            all_course_assignments.append((course_title,
                                            assign_data[i][0],
                                            assign_data[i][1],
                                            grades_data[i][0],
                                            grades_data[i][1],
                                            assign_data[i][2]))

    return(all_course_assignments)
    
    
#returns all current assignments in the given semester
#in tuple form : (course_name,assigment_name,due_date)
def get_current_assignments(user):
    canvas_assignments = get_current_canvas_assignments(user)
    coursys_assignments = get_current_coursys_assignments(user)
    current_assignments = canvas_assignments + coursys_assignments
    return current_assignments

# For debugging
events = [
    # Monday
    [
        {
            'name': 'Quiz',
            'offset': '10:30',
            'due': '11:20',
            'slug': 'quiz-1',
            'colour': 1,
        },
        {
            'name': 'Homework 1',
            'offset': '16:00',
            'due': '18:00',
            'slug': 'homework-1',
            'colour': 2,
        },
    ],
    # Tuesday
    [],
    # Wednesday
    [
        {
            'name': 'Exam',
            'offset': '13:30',
            'due': '15:30',
            'slug': 'exam',
            'colour': 3,
        },
    ],
    # Thursday
    [],
    # Friday
    [
        {
            'name': 'Homework 2',
            'offset': '14:00',
            'due': '16:00',
            'slug': 'homework-2',
            'colour': 2,
        },
    ],
]

days_of_the_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

@login_required
def weekly_schedule(request):
    # Basic version
    # try:
    #     courses = get_current_courses_and_assignments(request.user)
    # except CanvasError:
    #     return HttpResponse('Invalid Canvas token')
    # except CoursysError:
    #     return HttpResponse('Invalid Coursys request. Detail: ' + str(CoursysError))
    # return render(request, 'accounts/courses.html', context={'user': request.user, "courses": courses})
    
    # Find the current week number plus the requested offset, also create a list of dates for this week
    timezone_now = timezone.now()
    _, current_week_number, current_weekday = timezone_now.isocalendar()
    most_recent_monday = timezone_now - timedelta(days=current_weekday-1)
    dates = [date.strftime('%b %d') for date in (most_recent_monday + timedelta(days=i) for i in range(7))]

    week_offset = request.GET.get('week_offset', '0')
    if week_offset == 'exams':
        probable_exam_weeks = [15, 32, 50]
        probable_exam_week = probable_exam_weeks[(timezone_now.month - 1) // 4]
        week_offset = probable_exam_week - current_week_number
        current_week_number = probable_exam_week
    else:
        try:
            week_offset = int(week_offset)
        except ValueError:
            raise Http404('Invalid URL parameter: week_offset. Should be convertible to int.')
        current_week_number += week_offset

    request.user.activitydescription_set.all().delete()
    events = [[] for i in range(7)]
    occupied_slots = [set() for i in range(7)]
    
    coursys_courses = coursys_primary_request(request.user)
    # Filter current week's assignments and retrieve needed information
    # Also, save more detailed descriptions
    for i, course in enumerate(coursys_courses):
        for assignment in course['assignments']:
            if assignment['due_date'] is not None:
                due_date = parse_datetime(assignment['due_date'])
                _, week_number, weekday = due_date.isocalendar()
                weekday = weekday - 1   # in 0-6 range
                if week_number == current_week_number:
                    assignment_grade = [grading_info['grade'] for grading_info in course['grades'] if grading_info['slug'] == assignment['slug']][0]
                    ActivityDescription(
                        student=request.user,
                        slug=course['slug'] + assignment['slug'],
                        description='<div class="text-md"><h2 data-colour={colour}>{course}</h2><br><p>Grade: {grade}/{max_grade}</p><br><p>Final score percent: <b>{percent}%</b></p><br><p>Link to asssignment page: <a href="{url}" target="_blank">{url}</a></p></div>'.format(colour=i, course=course['subject'] + course['number'], grade=assignment_grade if assignment_grade else '?', max_grade=assignment['max_grade'], percent=assignment['percent'], url=assignment['url'])
                    ).save()
                    offset = (due_date.hour >> 1) << 1  # Make it even
                    if due_date.minute == 0:
                        offset -= 2
                    while offset in occupied_slots[weekday]:
                        offset -= 2
                    occupied_slots[weekday].add(offset)
                    events[weekday].append({
                        'name': assignment['name'],
                        'offset': '{}:00'.format(offset),
                        'due': due_date.time().strftime('%H:%M'),
                        'slug': course['slug'] + assignment['slug'],
                        'colour': i,
                    })
    
    canvas_courses = canvas_primary_query(request.user)
    for i, course in enumerate(canvas_courses):
        for assignment in course['assignmentsConnection']['nodes']:
            if assignment['dueAt'] is not None:
                due_date = parse_datetime(assignment['dueAt'])
                _, week_number, weekday = due_date.isocalendar()
                weekday = weekday - 1   # in 0-6 range
                if week_number == current_week_number:
                    try:
                        assignment_grade = assignment['submissionsConnection']['nodes'][0]['grade']
                    except:
                        assignment_grade = None
                    ActivityDescription(
                        student=request.user,
                        slug=assignment['id'],
                        description= '<div class="text-md"><h2 data-colour={colour}>{course}</h2><br><p>Grade: {grade}/{max_grade}</p><br><p>Link to assignment page: <a href="{url}" target="_blank">{url}</a></p><br>{description}</div>'.format(colour=i+len(coursys_courses), course=course['courseCode'].partition(' ')[0], grade = assignment_grade if assignment_grade else '?', max_grade=assignment['pointsPossible'], description=assignment['description'], url=assignment['htmlUrl']),
                    ).save()
                    offset = (due_date.hour >> 1) << 1
                    if due_date.minute == 0:
                        offset -= 2
                    while offset in occupied_slots[weekday]:
                        offset -= 2
                    occupied_slots[weekday].add(offset)
                    events[weekday].append({
                        'name': assignment['name'],
                        'offset': '{}:00'.format(offset),
                        'due': due_date.time().strftime('%H:%M'),
                        'slug': assignment['id'],
                        'colour': i + len(coursys_courses),
                    })

    # If there are no due dates on weekends, remove them
    if len(events[5]) == 0 and len(events[6]) == 0:
        events = events[:-2]

    week_numbers = [(week_offset + i, current_week_number + i) for i in range(-2, 2)]
    return render(request, 'accounts/weekly_schedule.html', context={'eventful_days': zip(days_of_the_week, dates, events), 'week_numbers': week_numbers, 'week_offset': week_offset})

@login_required
def ajax(request, slug, week_offset='whatever'):
    description = request.user.activitydescription_set.get(slug=slug).description
    return HttpResponse('<div class="cd-schedule-modal__event-info">{}</div>'.format(description))

@login_required
def refresh(request):
    # Refresh assignments and grades
    refresh_coursys_info(request.user)
    refresh_canvas_info(request.user)
    return HttpResponseRedirect(reverse('accounts:weekly_schedule') + '?week_offset=' + request.GET.get('week_offset', '0'))

# get information for a single course.
# https://canvas.instructure.com/doc/api/all_resources.html#method.courses.show
@login_required
def course_info_view(request, course_id):
    return HttpResponse("You entered the follow course: " + str(course_id))


# https://canvas.instructure.com/doc/api/all_resources.html#method.announcements_api.index
@login_required
def announcements_view(request):
    ANNOUNCEMENTS_URL = CANVAS_SFU_CA + "/api/v1/announcements"

    response = get_canvas_courses(request.user)
    # https://community.canvaslms.com/thread/15698-contextcodes
    # context code is just "course_" + course id. course id obtained from previous api call to courses list
    context_codes = {"course_" + str(course['id'])
                     for course in response if 'name' in course}
    payload = {'context_codes[]': context_codes}
    # making announcements list api call with context codes params
    response = requests.get(url=ANNOUNCEMENTS_URL,
                            headers={"Authorization": "Bearer " +
                                     request.user.canvas_token},
                            params=payload)

    announcements = {announcement["title"]
                     for announcement in response.json() if 'title' in announcement}

    return render(request, 'accounts/announcements.html', context={"announcements": announcements})


@login_required
# https://canvas.instructure.com/doc/api/assignments.html#method.assignments_api.index
def assignments_view(request):
    data_select = request.GET.get('data_select')
    import dateutil.parser
    all_assignments = get_current_assignments(request.user)
    
    date_key_assign = defaultdict(list)
    course_key_assign = defaultdict(list)
    for course,assignment,due_date,grade,max_grade,url in all_assignments:
        if due_date != None:
            d = dateutil.parser.parse(due_date)
            date_key_assign[d.strftime('%Y/%m/%d')].append((course,assignment,grade,max_grade,url))
            course_key_assign[course].append((d.strftime('%Y/%m/%d'),assignment,grade,max_grade,url))
        else:
            date_key_assign["No deadline given"].append((course,assignment,grade,max_grade,url))
            course_key_assign[course].append(("<No deadline given>",assignment,grade,max_grade,url))

        
    #do this because templates can't loop over default dicts
    date_key_assign = dict(date_key_assign)
    ordered_date = sorted(date_key_assign.items())
    course_key_assign = dict(course_key_assign)
    ordered_courses = sorted(course_key_assign.items())
    
    if data_select == "date":
        return render(request, 'accounts/current_assignments.html', 
				      context={"all_assignments": ordered_date})
				      
    elif data_select == "courses":
        return render(request, 'accounts/current_assignments.html', 
				      context={"all_assignments":ordered_courses})
    else:
        return render(request, 'accounts/current_assignments.html', 
				      context={"all_assignments": ordered_date})
@login_required
# https://canvas.instructure.com/doc/api/assignments.html#method.assignments_api.index
def courses_view(request):
    data_select = request.GET.get('data_select')
    import dateutil.parser
    all_assignments = get_current_assignments(request.user)
    
    course_key_assign = defaultdict(list)
    for course,assignment,due_date,grade,max_grade,url in all_assignments:
        if due_date != None:
            d = dateutil.parser.parse(due_date)
            course_key_assign[course].append((d.strftime('%Y/%m/%d'),assignment,grade,max_grade,url))
        else:
            course_key_assign[course].append(("<No deadline given>",assignment,grade,max_grade,url))

        
    #do this because templates can't loop over default dicts

    course_key_assign = dict(course_key_assign)
    ordered_courses = sorted(course_key_assign.items())
    
    return render(request, 'accounts/current_courses.html', 
				      context={"all_assignments":ordered_courses})


# Display some user information
@login_required
def profile(request):
    if request.method == 'POST':
        from rest_framework.authtoken.models import Token
        token, was_created = Token.objects.get_or_create(user=request.user)
        return render(request, 'accounts/profile.html', context={'user': request.user, 'token': token.key})
    return render(request, 'accounts/profile.html', context={'user': request.user})
