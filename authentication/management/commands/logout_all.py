from django.core.management.base import BaseCommand, CommandError
from django.contrib.sessions.models import Session

class Command(BaseCommand):
    help = 'Logs out all users'

    def handle(self, *args, **options):
        logged_out = Session.objects.all().delete()[0]
        if logged_out == 0:
            raise CommandError('No users have been logged out')
        self.stdout.write(self.style.SUCCESS('Successfully loggged out %s user(s)' % logged_out))