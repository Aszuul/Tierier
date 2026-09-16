from django.shortcuts import render, redirect
from django.db import models, transaction
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from .models import Category, Choice, CategoryChoice

def index(request):
    choicelist = Choice.objects.order_by('-order')
    categories = Category.objects.all()
    category_choices = CategoryChoice.objects.select_related('choice').order_by('order')
    category_items = []
    for category in categories:
        category_items.append({
            "id": category.id,
            "name": category.name,
            "choices": category_choices.filter(category=category)
        })
    context = {
        "choicelist": choicelist,
        'categories': categories,
        'category_items': category_items,
    }
    return render(request, "tierlist/index.html", context)

@require_POST
def update_order(request):
    item_ids = list(dict.fromkeys(request.POST.getlist('item_id')))
    category_id = request.POST.get('category_id')

    with transaction.atomic():
        if category_id:
            category = Category.objects.get(id=category_id)
            for index, item_id in enumerate(item_ids):
                choice = Choice.objects.get(id=item_id)
                category_choice, created = CategoryChoice.objects.get_or_create(
                    category=category,
                    choice=choice,
                    defaults={'category': category, 'order': index},
                )
                if not created:
                    category_choice.order = index
                    category_choice.save(update_fields=['order'])
        else:
            for index, item_id in enumerate(item_ids):
                Choice.objects.filter(id=item_id).update(order=index)
    return HttpResponse(status=200)

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

@require_POST
def delete_choice(request, choice_id):
    Choice.objects.filter(id=choice_id).delete()
    return redirect('tierlist:index')

@require_POST
def remove_category_choice(request, category_id, choice_id):
    CategoryChoice.objects.filter(
        category_id=category_id,
        choice_id=choice_id,
    ).delete()
    return redirect('tierlist:index')