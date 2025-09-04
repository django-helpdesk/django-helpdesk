# Add this function to your staff.py views file
from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    """Log the user out and redirect to login page"""
    logout(request)
    return redirect('helpdesk:login')