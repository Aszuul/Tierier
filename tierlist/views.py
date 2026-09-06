from django.shortcuts import render, get_list_or_404, redirect
from django.db import models, transaction
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from .models import Category, Choice, CategoryChoice

def index(request):
    choicelist = Choice.objects.order_by('order')
    categories = Category.objects.all()
    category_choices = CategoryChoice.objects.select_related('category', 'choice').order_by('order')
    category_items = []
    for category in categories:
        category_items.append({
            "name": category.name,
            "choices": category_choices.filter(category=category)
        })
    print(category_items)
    context = {
        "choicelist": choicelist,
        'categories': categories,
        'category_items': category_items,
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

@require_POST
def add_category(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            Category.objects.create(name=name)
    return redirect('tierlist:index')