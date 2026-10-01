from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import get_object_or_404, render, redirect
from django.db import models, transaction
from django.views.decorators.http import require_POST
from django.http import HttpResponse
import re
import secrets
from types import SimpleNamespace

from .models import Category, Choice, CategoryChoice, TierList, default_tierlist_palette


BUILT_IN_PALETTES = {
    'standard': default_tierlist_palette(),
    'garden': ['#287a5c', '#a4bb45', '#d3a844', '#4b8fa2', '#c46e55', '#7563a8'],
    'berry': ['#d94f70', '#7a4eab', '#3876b8', '#278c87', '#92a83f', '#db873c'],
}


def normalize_palette(palette):
    default = default_tierlist_palette()
    if not isinstance(palette, list) or len(palette) != len(default):
        return default
    if any(
        not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color)
        for color in palette
    ):
        return default
    return [color.lower() for color in palette]


def choose_choice_color(palette, used_colors):
    used = {color.lower() for color in used_colors}
    for color in palette:
        if color.lower() not in used:
            return color
    while True:
        color = f'#{secrets.token_hex(3)}'
        if color not in used:
            return color


def get_palette_preset_name(palette):
    return next(
        (name for name, preset in BUILT_IN_PALETTES.items() if preset == palette),
        '',
    )


def get_guest_draft(request):
    draft = request.session.setdefault('tierlist_draft', {
        'choices': [],
        'categories': [],
        'next_choice_id': 1,
        'next_category_id': 1,
        'palette': default_tierlist_palette(),
    })
    changed = False
    if 'palette' not in draft:
        draft['palette'] = default_tierlist_palette()
        changed = True
    normalized_palette = normalize_palette(draft['palette'])
    if normalized_palette != draft['palette']:
        draft['palette'] = normalized_palette
        changed = True
    used_colors = []
    for choice in sorted(draft['choices'], key=lambda item: item['order']):
        color = choice.get('color')
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            old_override = choice.get('color_override', '')
            old_slot = choice.get('color_slot', len(used_colors))
            if isinstance(old_override, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', old_override):
                color = old_override.lower()
            else:
                color = draft['palette'][old_slot % len(draft['palette'])]
            choice['color'] = color
            changed = True
        if choice.pop('color_slot', None) is not None:
            changed = True
        if choice.pop('color_override', None) is not None:
            changed = True
        used_colors.append(color)
    if draft.pop('next_color_slot', None) is not None:
        changed = True
    if changed:
        request.session.modified = True
    return draft


def get_user_tier_list(request):
    tier_list, _ = TierList.objects.get_or_create(owner=request.user)
    return tier_list


def build_index_context(choices, categories, memberships, palette):
    category_items = []
    scores = {}
    category_choice_ids = []
    for category in categories:
        category_choices = memberships.get(category.id, [])
        category_choice_ids.append({item.choice.id for item in category_choices})
        for index, item in enumerate(category_choices):
            choice_id = item.choice.id
            scores[choice_id] = scores.get(choice_id, 0) + index * category.weight
        category_items.append({
            'id': category.id,
            'name': category.name,
            'choices': category_choices,
            'weight': category.weight,
        })

    ranked_choice_ids = set.intersection(*category_choice_ids) if category_choice_ids else set()
    choices_by_id = {choice.id: choice for choice in choices}
    rankings = [
        {'choice': choices_by_id[choice_id], 'score': score}
        for choice_id, score in scores.items()
        if choice_id in ranked_choice_ids and choice_id in choices_by_id
    ]
    rankings.sort(key=lambda ranking: ranking['score'])
    return {
        'choicelist': choices,
        'categories': categories,
        'category_items': category_items,
        'rankings': rankings,
        'choice_limit_reached': len(choices) >= 50,
        'category_limit_reached': len(categories) >= 10,
        'palette': palette,
        'palette_presets': BUILT_IN_PALETTES,
        'current_palette_preset': get_palette_preset_name(palette),
    }


def register(request):
    if request.user.is_authenticated:
        return redirect('tierlist:index')

    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        from django.contrib.auth import login
        login(request, user)
        if request.session.get('tierlist_draft'):
            return redirect('tierlist:save')
        return redirect('tierlist:index')
    return render(request, 'registration/register.html', {'form': form})

def index(request):
    if not request.user.is_authenticated:
        draft = get_guest_draft(request)
        palette = draft['palette']
        choices_by_id = {
            choice['id']: SimpleNamespace(**choice)
            for choice in draft['choices']
        }
        choices = sorted(choices_by_id.values(), key=lambda choice: choice.order, reverse=True)
        categories = [SimpleNamespace(**category) for category in draft['categories']]
        memberships = {
            category.id: [
                SimpleNamespace(
                    choice=choices_by_id[item['choice_id']],
                    order=item['order'],
                )
                for item in sorted(category.choices, key=lambda membership: membership['order'])
                if item['choice_id'] in choices_by_id
            ]
            for category in categories
        }
    else:
        tier_list = get_user_tier_list(request)
        palette = normalize_palette(tier_list.palette)
        choices = list(Choice.objects.filter(tier_list=tier_list).order_by('-order'))
        categories = list(Category.objects.filter(tier_list=tier_list))
        memberships = {category.id: [] for category in categories}
        for membership in CategoryChoice.objects.filter(
            category__tier_list=tier_list,
            choice__tier_list=tier_list,
        ).select_related('choice').order_by('order'):
            memberships[membership.category_id].append(membership)

    return render(
        request,
        'tierlist/index.html',
        build_index_context(choices, categories, memberships, palette),
    )

@require_POST
def update_order(request):
    if not request.user.is_authenticated:
        draft = get_guest_draft(request)
        item_ids = list(dict.fromkeys(request.POST.getlist('item_id')))
        category_id = request.POST.get('category_id')
        choices_by_id = {str(choice['id']): choice for choice in draft['choices']}
        if category_id:
            category = next(
                (item for item in draft['categories'] if str(item['id']) == category_id),
                None,
            )
            if category:
                category['choices'] = [
                    {'choice_id': int(item_id), 'order': index}
                    for index, item_id in enumerate(item_ids)
                    if item_id in choices_by_id
                ]
        else:
            for index, item_id in enumerate(item_ids):
                if item_id in choices_by_id:
                    choices_by_id[item_id]['order'] = index
        request.session.modified = True
        return HttpResponse(status=200)

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

@require_POST
def add_choice(request):
    if not request.user.is_authenticated:
        draft = get_guest_draft(request)
        name = request.POST.get('name', '').strip()
        if name and len(draft['choices']) < 50:
            choice_id = draft['next_choice_id']
            draft['next_choice_id'] += 1
            color = choose_choice_color(
                draft['palette'],
                [choice['color'] for choice in draft['choices']],
            )
            draft['choices'].append({
                'id': choice_id,
                'name': name,
                'order': max((choice['order'] for choice in draft['choices']), default=-1) + 1,
                'color': color,
            })
            request.session.modified = True
        return redirect('tierlist:index')

    tier_list = get_user_tier_list(request)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name and Choice.objects.filter(tier_list=tier_list).count() < 50:
            existing = Choice.objects.filter(tier_list=tier_list)
            max_order = existing.aggregate(max_order=models.Max('order'))['max_order']
            color = choose_choice_color(
                normalize_palette(tier_list.palette),
                existing.values_list('color', flat=True),
            )
            Choice.objects.create(
                tier_list=tier_list,
                name=name,
                order=(max_order if max_order is not None else -1) + 1,
                color=color,
            )
    return redirect('tierlist:index')

@require_POST
def add_category(request):
    if not request.user.is_authenticated:
        draft = get_guest_draft(request)
        name = request.POST.get('name', '').strip()
        if name and len(draft['categories']) < 10:
            category_id = draft['next_category_id']
            draft['next_category_id'] += 1
            draft['categories'].append({
                'id': category_id,
                'name': name,
                'weight': 1,
                'choices': [],
            })
            request.session.modified = True
        return redirect('tierlist:index')

    tier_list = get_user_tier_list(request)
    if request.method == 'POST':
        name = request.POST.get('name')
        if name and Category.objects.filter(tier_list=tier_list).count() < 10:
            Category.objects.create(tier_list=tier_list, name=name)
    return redirect('tierlist:index')

@require_POST
def update_category(request, category_id):
    if not request.user.is_authenticated:
        draft = get_guest_draft(request)
        category = next(
            (item for item in draft['categories'] if item['id'] == category_id),
            None,
        )
        name = request.POST.get('name', '').strip()
        try:
            weight = float(request.POST.get('weight', ''))
        except (TypeError, ValueError):
            weight = None
        if category and name and weight is not None and 0.1 <= weight <= 1:
            category.update({'name': name, 'weight': weight})
            request.session.modified = True
        return redirect('tierlist:index')

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

@require_POST
def delete_category(request, category_id):
    if not request.user.is_authenticated:
        draft = get_guest_draft(request)
        draft['categories'] = [
            item for item in draft['categories'] if item['id'] != category_id
        ]
        request.session.modified = True
        return redirect('tierlist:index')

    Category.objects.filter(id=category_id, tier_list=get_user_tier_list(request)).delete()
    return redirect('tierlist:index')

@require_POST
def delete_choice(request, choice_id):
    if not request.user.is_authenticated:
        draft = get_guest_draft(request)
        draft['choices'] = [item for item in draft['choices'] if item['id'] != choice_id]
        for category in draft['categories']:
            category['choices'] = [
                item for item in category['choices'] if item['choice_id'] != choice_id
            ]
        request.session.modified = True
        return redirect('tierlist:index')

    Choice.objects.filter(id=choice_id, tier_list=get_user_tier_list(request)).delete()
    return redirect('tierlist:index')

@require_POST
def remove_category_choice(request, category_id, choice_id):
    if not request.user.is_authenticated:
        draft = get_guest_draft(request)
        category = next(
            (item for item in draft['categories'] if item['id'] == category_id),
            None,
        )
        if category:
            category['choices'] = [
                item for item in category['choices'] if item['choice_id'] != choice_id
            ]
            request.session.modified = True
        return redirect('tierlist:index')

    CategoryChoice.objects.filter(
        category_id=category_id,
        choice_id=choice_id,
        category__tier_list=get_user_tier_list(request),
        choice__tier_list=get_user_tier_list(request),
    ).delete()
    return redirect('tierlist:index')


@login_required
def save_draft(request):
    draft = request.session.get('tierlist_draft')
    if draft:
        draft = get_guest_draft(request)
        tier_list = get_user_tier_list(request)
        tier_list.palette = normalize_palette(draft['palette'])
        tier_list.save(update_fields=['palette'])
        choice_offset = Choice.objects.filter(tier_list=tier_list).count()
        choices_by_id = {}
        for choice in sorted(draft['choices'], key=lambda item: item['order']):
            choices_by_id[choice['id']] = Choice.objects.create(
                tier_list=tier_list,
                name=choice['name'],
                order=choice_offset + choice['order'],
            color=choice['color'],
            )
        for category in draft['categories']:
            saved_category = Category.objects.create(
                tier_list=tier_list,
                name=category['name'],
                weight=category['weight'],
            )
            for item in category['choices']:
                choice = choices_by_id.get(item['choice_id'])
                if choice:
                    CategoryChoice.objects.create(
                        category=saved_category,
                        choice=choice,
                        order=item['order'],
                    )
        del request.session['tierlist_draft']
    return redirect('tierlist:index')


@require_POST
def update_palette(request):
    if request.user.is_authenticated:
        tier_list = get_user_tier_list(request)
        palette = normalize_palette(tier_list.palette)
    else:
        draft = get_guest_draft(request)
        palette = normalize_palette(draft['palette'])

    preset = request.POST.get('preset')
    if preset:
        palette = BUILT_IN_PALETTES.get(preset, palette)
    else:
        try:
            palette_index = int(request.POST.get('palette_index', ''))
        except (TypeError, ValueError):
            palette_index = -1
        color = request.POST.get('color', '')
        if 0 <= palette_index < len(palette) and re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            palette[palette_index] = color.lower()

    if request.user.is_authenticated:
        tier_list.palette = palette
        tier_list.save(update_fields=['palette'])
    else:
        draft['palette'] = palette
        request.session.modified = True
    return redirect('tierlist:index')


@require_POST
def update_choice_color(request, choice_id):
    color = '' if request.POST.get('reset') else request.POST.get('color', '')
    if color and not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        return redirect('tierlist:index')

    if request.user.is_authenticated:
        tier_list = get_user_tier_list(request)
        choice = Choice.objects.filter(
            id=choice_id,
            tier_list=tier_list,
        ).first()
        if choice:
            if not color:
                used_colors = Choice.objects.filter(tier_list=tier_list).exclude(
                    id=choice_id,
                ).values_list('color', flat=True)
                color = choose_choice_color(normalize_palette(tier_list.palette), used_colors)
            choice.color = color.lower()
            choice.save(update_fields=['color'])
    else:
        draft = get_guest_draft(request)
        choice = next((item for item in draft['choices'] if item['id'] == choice_id), None)
        if choice:
            if not color:
                used_colors = [
                    item['color'] for item in draft['choices']
                    if item['id'] != choice_id
                ]
                color = choose_choice_color(draft['palette'], used_colors)
            choice['color'] = color.lower()
            request.session.modified = True
    return redirect('tierlist:index')