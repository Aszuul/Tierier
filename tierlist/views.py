from django.shortcuts import render


def index(request):
    context = {}
    return render(request, "tierlist/index.html", context)
