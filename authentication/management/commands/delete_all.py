from django.core.management.base import BaseCommand, CommandError
from accounts.models import Student

class Command(BaseCommand):
    help = 'Logs out all users'

    def handle(self, *args, **options):
        deleted = Student.objects.all().delete()[0]
        if deleted == 0:
            raise CommandError('There are no users to delete')
        self.stdout.write(self.style.SUCCESS('Successfully deleted %s user(s)' % deleted))