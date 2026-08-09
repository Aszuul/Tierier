from django.shortcuts import render, get_list_or_404, redirect
from django.db import models, transaction
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from .models import Choice

def index(request):
    context = {
        "choicelist": Choice.objects.order_by('order'),
    }
    return render(request, "tierlist/index.html", context)

@require_POST
def update_order(request):
    item_ids = request.POST.getlist('item_id')
    with transaction.atomic():
        for index, item_id in enumerate(item_ids):
            Choice.objects.filter(id=item_id).update(order=index)
    return HttpResponse(status=204)

@require_POST
def add_choice(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            max_order = Choice.objects.aggregate(max_order=models.Max('order'))['max_order'] or 0
            Choice.objects.create(name=name, order=max_order + 1)
    return redirect('tierlist:index')