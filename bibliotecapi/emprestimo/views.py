from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def emprestar(request):
    return HttpResponse('emprestimo de livro')
