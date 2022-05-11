from django.utils import timezone


class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """
        Set the timezone for a Helpdesk Session. Persists as long as the user's Browser session is active
        """
        tzname = request.session.get('helpdesk_timezone')
        if tzname:
            timezone.activate(tzname)
        else:
            timezone.deactivate()
        return self.get_response(request)
