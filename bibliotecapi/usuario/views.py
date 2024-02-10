from django.shortcuts import render
from django.http import HttpResponse

def index(request):
    return HttpResponse("Olá, você está na página de usuários")
# Create your views here.
