from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse

from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test

from django.utils.safestring import mark_safe

from accounts.models import Student, CoursysRequestToken

import requests

from pprint import pprint

# Create your views here.
class RegistrationForm(forms.ModelForm):
    class Meta:
        model = Student
        exclude = ['coursys_access_token', 'coursys_access_token_secret', 'last_login']
        help_texts = {
            'canvas_token': mark_safe("<p class=\"text-sm margin-top-xxxs\">For details about generating tokens, visit <a target=\"_blank\" href='https://canvas.instructure.com/doc/api/file.oauth.html#manual-token-generation'>Canvas documentation</a></p>")
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control width-100%'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control width-100%'}),
            'student_id': forms.TextInput(attrs={'class': 'form-control width-100%'}),
            'email': forms.TextInput(attrs={'class': 'form-control width-100%'}),
            'password': forms.TextInput(attrs={'class': 'form-control width-100%'}),
            'canvas_token': forms.TextInput(attrs={'class': 'form-control width-100%'}),
        }
    # def clean(self):
    #     cleaned_data = super().clean()

    def clean_canvas_token(self):
        # Test if Canvas token is correct and if GraphQL is supported
        token = self.cleaned_data['canvas_token']
        GRAPHQL_URL = "https://canvas.sfu.ca/api/graphql"
        TEST_QUERY = "{allCourses{_id}}"

        response = requests.post(url=GRAPHQL_URL, headers={\
            "Authorization": "Bearer " + token}, data={"query": TEST_QUERY})
        
        if response.status_code != 200 or 'data' not in response.json():
            raise forms.ValidationError("Please enter a valid Canvas token.")
        return token
        # Apparently it's only for admins for some reason
        # PERMISSIONS_URL = 'https://canvas.sfu.ca/api/v1/accounts/self/permissions'
        # response = requests.get(PERMISSIONS_URL,
        #                     headers={"Authorization": "Bearer " + token},
        #                     params={"permissions[]": "read_course_list", "permissions[]": "read_course_content", "permissions[]": "read_announcements","permissions[]": "view_all_grades"}
        # )
        # pprint(response.text)
        # if response.status_code != 200 or not all(response.json().values()):
        #     raise forms.ValidationError("Please enter a valid Canvas token")
        # return token
            

class LoginForm(forms.Form):
    student_id = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control width-100% margin-bottom-sm'}))
    password = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control width-100% margin-bottom-sm'}))

def registration_view(request):
    if request.method == 'POST':
        registration_form = RegistrationForm(request.POST)
        if registration_form.is_valid():
            student = registration_form.save(commit=False)
            student.set_password(registration_form.cleaned_data['password'])
            student.save()
            return redirect('authentication:login')

    else:
        registration_form = RegistrationForm()
    
    return render(request, 'registration/register.html', context={'user': request.user, 'form': registration_form})

def login_view(request):
    if request.method == 'POST':
        login_form = LoginForm(request.POST)
        next_url = request.POST['next']
        if login_form.is_valid():
            student = authenticate(username=login_form.cleaned_data['student_id'], password=login_form.cleaned_data['password'])
            if student is not None:
                login(request, student)
                if student.has_coursys_access():
                    return HttpResponseRedirect(request.POST['next'])
                else:
                    return HttpResponseRedirect(reverse('authentication:oauth_coursys') + '?next=' + request.POST['next'])  # Is there a better way?

            else:
                login_form.add_error(None, "Authentication failed")

    else:
        login_form = LoginForm()
        try:
            next_url = request.GET['next']
        except KeyError:
            next_url = reverse('accounts:weekly_schedule')
    
    return render(request, 'registration/login.html', context={'user': request.user, 'form': login_form, 'next': next_url})


@login_required
def logout_view(request):
    logout(request)
    return redirect('authentication:logout_success')


def logout_success_view(request):
    return render(request, 'registration/logout_success.html', context={'user': request.user })



from rauth import OAuth1Service
from urllib.parse import parse_qs

coursys = OAuth1Service(
    name='coursys',
    consumer_key='f424620f584248e681c4adc298f1594d',
    consumer_secret='mL6KioJ1l8HSJ1Zi',
    request_token_url='https://coursys.sfu.ca/api/oauth/request_token/',
    access_token_url='https://coursys.sfu.ca/api/oauth/access_token/',
    authorize_url='https://coursys.sfu.ca/api/oauth/authorize/',
    base_url='https://coursys.sfu.ca')


# Adapted from https://github.com/litl/rauth
@login_required
def coursys_authentication_view(request):
    if request.method == 'POST':
        pin = request.POST['pin']
    
        # session = coursys.get_auth_session(request.user.coursys.request_token,
        #                            request.user.coursys.request_token_secret,
        #                            method='POST',
        #                            data={'oauth_verifier': pin})

        # request.user.coursys.delete()   # Deletes temporary tokens, not the user

        # request.user.coursys_access_token = session.access_token
        # request.user.coursys_access_token_secret = session.access_token_secret
        # request.user.save()             # Save reusable tokens

        # print(session.get("https://coursys.sfu.ca/api/1/offerings/").text)

        try:
            # Save reusable tokens into the user's model without creating a session
            request.user.coursys_access_token, request.user.coursys_access_token_secret = coursys.get_access_token(
                                        request.user.coursys.request_token,
                                        request.user.coursys.request_token_secret,
                                        method='POST',
                                        data={'oauth_verifier': pin}
            )
        except:
            return render(request, 'registration/coursys_pin.html', context={'authorize_url': request.user.coursys.authorize_url, 'next': request.POST['next'], 'error': 'Please enter a valid PIN'})

        request.user.coursys.delete()   # Delete temporary tokens, not the user

        request.user.save() 

        return HttpResponseRedirect(request.POST['next'])
    
    else:
        # request_token, request_token_secret = coursys.get_request_token(decoder=parse_qs, params={'oauth_callback': 'oob'})
        response = coursys.get_raw_request_token(params={'oauth_callback': 'oob'})  # oob means that we request a PIN and we do not want Coursys to redirect to our site (because it doesn't exist)
        pprint(response.content)
        response = parse_qs(response.text) # Convert into a dictionary
        assert(response['oauth_callback_confirmed'][0] == 'true')
        request_token = response['oauth_token'][0]
        request_token_secret = response['oauth_token_secret'][0]

        # Create a URL where user can obtain the PIN
        authorize_url = coursys.get_authorize_url(request_token)

        # Save the user's request token and secret
        CoursysRequestToken(owner=request.user, request_token=request_token, request_token_secret=request_token_secret, authorize_url=authorize_url).save()

        return render(request, 'registration/coursys_pin.html', context={'authorize_url': authorize_url, 'next': request.GET['next']})

# This session can be used to make calls to Coursys API
# @login_required
# @user_passes_test(lambda user: user.has_coursys_access(), login_url=reverse('authentication:oauth_coursys'))
# def get_coursys_session(request):
#     return coursys.get_session((request.user.coursys_access_token, request.user.coursys_access_token_secret))
def get_coursys_session(access_token, access_token_secret):
    return coursys.get_session((access_token, access_token_secret))
