from django.shortcuts import render, get_list_or_404
from django.db import transaction
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from .models import Choice

def index(request):
    context = {
        "choicelist": get_list_or_404(Choice)
    }
    return render(request, "tierlist/index.html", context)

@require_POST
def update_order(request):
    item_ids = request.POST.getlist('item_id')
    with transaction.atomic():
        for index, item_id in enumerate(item_ids):
            Choice.objects.filter(id=item_id).update(order=index)
    return HttpResponse(status=200)
