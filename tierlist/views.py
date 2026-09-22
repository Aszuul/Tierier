from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import get_object_or_404, render, redirect
from django.db import models, transaction
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from .models import Category, Choice, CategoryChoice, TierList


def get_user_tier_list(request):
    tier_list, _ = TierList.objects.get_or_create(owner=request.user)
    return tier_list


def register(request):
    if request.user.is_authenticated:
        return redirect('tierlist:index')

    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        from django.contrib.auth import login
        login(request, user)
        return redirect('tierlist:index')
    return render(request, 'registration/register.html', {'form': form})

@login_required
def index(request):
    tier_list = get_user_tier_list(request)
    choicelist = Choice.objects.filter(tier_list=tier_list).order_by('-order')
    categories = list(Category.objects.filter(tier_list=tier_list))
    category_choices = CategoryChoice.objects.filter(
        category__tier_list=tier_list,
        choice__tier_list=tier_list,
    ).select_related('choice').order_by('order')
    category_items = []
    scores = {}
    category_choice_ids = []
    for category in categories:
        choices = list(category_choices.filter(category=category))
        category_choice_ids.append({item.choice.id for item in choices})
        for index, item in enumerate(choices):
            choice_id = item.choice.id
            scores[choice_id] = scores.get(choice_id, 0) + index * category.weight
        category_items.append({
            "id": category.id,
            "name": category.name,
            "choices": choices,
            "weight": category.weight,
        })

    ranked_choice_ids = set.intersection(*category_choice_ids) if category_choice_ids else set()
    choices_by_id = {
        choice.id: choice
        for choice in Choice.objects.filter(tier_list=tier_list, id__in=ranked_choice_ids)
    }
    rankings = [
        {"choice": choices_by_id[choice_id], "score": score}
        for choice_id, score in scores.items()
        if choice_id in ranked_choice_ids
    ]
    rankings.sort(key=lambda ranking: ranking['score'])

    context = {
        "choicelist": choicelist,
        'categories': categories,
        'category_items': category_items,
        'rankings': rankings,
        'choice_limit_reached': choicelist.count() >= 50,
        'category_limit_reached': len(categories) >= 10,
    }
    return render(request, "tierlist/index.html", context)

@login_required
@require_POST
def update_order(request):
    tier_list = get_user_tier_list(request)
    item_ids = list(dict.fromkeys(request.POST.getlist('item_id')))
    category_id = request.POST.get('category_id')

    with transaction.atomic():
        if category_id:
            category = get_object_or_404(Category, id=category_id, tier_list=tier_list)
            for index, item_id in enumerate(item_ids):
                choice = get_object_or_404(Choice, id=item_id, tier_list=tier_list)
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
                Choice.objects.filter(id=item_id, tier_list=tier_list).update(order=index)
    return HttpResponse(status=200)

@login_required
@require_POST
def add_choice(request):
    tier_list = get_user_tier_list(request)
    if request.method == 'POST':
        name = request.POST.get('name')
        if name and Choice.objects.filter(tier_list=tier_list).count() < 50:
            max_order = Choice.objects.filter(tier_list=tier_list).aggregate(max_order=models.Max('order'))['max_order'] or 0
            Choice.objects.create(tier_list=tier_list, name=name, order=max_order + 1)
    return redirect('tierlist:index')

@login_required
@require_POST
def add_category(request):
    tier_list = get_user_tier_list(request)
    if request.method == 'POST':
        name = request.POST.get('name')
        if name and Category.objects.filter(tier_list=tier_list).count() < 10:
            Category.objects.create(tier_list=tier_list, name=name)
    return redirect('tierlist:index')

@login_required
@require_POST
def update_category(request, category_id):
    tier_list = get_user_tier_list(request)
    category = Category.objects.filter(id=category_id, tier_list=tier_list).first()
    name = request.POST.get('name', '').strip()
    weight_value = request.POST.get('weight', '').strip()

    if category and name:
        try:
            weight = float(weight_value)
        except (TypeError, ValueError):
            weight = None

        if weight is not None and 0.1 <= weight <= 1:
            category.name = name
            category.weight = weight
            category.save(update_fields=['name', 'weight'])

    return redirect('tierlist:index')

@login_required
@require_POST
def delete_category(request, category_id):
    Category.objects.filter(id=category_id, tier_list=get_user_tier_list(request)).delete()
    return redirect('tierlist:index')

@login_required
@require_POST
def delete_choice(request, choice_id):
    Choice.objects.filter(id=choice_id, tier_list=get_user_tier_list(request)).delete()
    return redirect('tierlist:index')

@login_required
@require_POST
def remove_category_choice(request, category_id, choice_id):
    CategoryChoice.objects.filter(
        category_id=category_id,
        choice_id=choice_id,
        category__tier_list=get_user_tier_list(request),
        choice__tier_list=get_user_tier_list(request),
    ).delete()
    return redirect('tierlist:index')