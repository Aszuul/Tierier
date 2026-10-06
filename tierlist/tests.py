from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import Category, CategoryChoice, Choice, TierList


class ChoiceOrderingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='owner',
            password='test-password-123',
        )
        self.client.login(username='owner', password='test-password-123')
        self.tier_list = TierList.objects.create(owner=self.user)

    def test_index_uses_choice_order_not_alpha_name_order(self):
        Choice.objects.create(tier_list=self.tier_list, name='Second', order=1)
        Choice.objects.create(tier_list=self.tier_list, name='First', order=0)

        response = self.client.get(reverse('tierlist:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Second')
        self.assertContains(response, 'First')
        self.assertContains(response, 'id="theme-toggle"')
        self.assertContains(response, 'Edit palette color 1')

        html = response.content.decode()
        first_index = html.find('Second')
        second_index = html.find('First')
        self.assertLess(first_index, second_index)

    def test_new_choices_receive_unique_colors_from_palette_then_random_fallback(self):
        palette = self.tier_list.palette
        for index in range(len(palette) + 1):
            self.client.post(
                reverse('tierlist:add_choice'),
                {'name': f'Choice {index}'},
            )
        choices = list(Choice.objects.filter(tier_list=self.tier_list).order_by('order'))

        self.assertEqual([choice.color for choice in choices[:-1]], palette)
        self.assertNotIn(choices[-1].color, palette)
        self.assertRegex(choices[-1].color, r'^#[0-9a-f]{6}$')

    def test_palette_and_choice_override_render_in_pool_and_category(self):
        category = Category.objects.create(tier_list=self.tier_list, name='Top tier')
        choice = Choice.objects.create(tier_list=self.tier_list, name='Shared color')
        CategoryChoice.objects.create(category=category, choice=choice)

        self.client.post(
            reverse('tierlist:update_palette'),
            {'palette_index': '0', 'color': '#123abc'},
        )
        response = self.client.post(
            reverse('tierlist:update_choice_color', args=[choice.pk]),
            {'color': '#abcdef'},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse('tierlist:index'))
        self.assertEqual(response.content.decode().count('--choice-color: #abcdef'), 3)

        response = self.client.post(
            reverse('tierlist:update_choice_color', args=[choice.pk]),
            {'color': '#abcdef', 'reset': '1'},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse('tierlist:index'))
        self.assertEqual(response.content.decode().count('--choice-color: #123abc'), 3)

        self.client.post(
            reverse('tierlist:update_palette'),
            {'preset': 'garden'},
        )
        self.client.post(
            reverse('tierlist:add_choice'),
            {'name': 'Added after palette change'},
        )
        response = self.client.get(reverse('tierlist:index'))
        self.assertEqual(response.content.decode().count('--choice-color: #123abc'), 3)
        self.assertEqual(response.content.decode().count('--choice-color: #287a5c'), 1)

    def test_update_order_persists_item_sequence(self):
        first = Choice.objects.create(tier_list=self.tier_list, name='First', order=0)
        second = Choice.objects.create(tier_list=self.tier_list, name='Second', order=1)

        response = self.client.post(
            reverse('tierlist:update_order'),
            {'item_id': [str(second.pk), str(first.pk)]},
        )

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.order, 1)
        self.assertEqual(second.order, 0)

    def test_update_order_adds_choice_to_category(self):
        category = Category.objects.create(tier_list=self.tier_list, name='Top tier')
        choice = Choice.objects.create(tier_list=self.tier_list, name='Choice')

        response = self.client.post(
            reverse('tierlist:update_order'),
            {'category_id': str(category.pk), 'item_id': [str(choice.pk)]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            CategoryChoice.objects.get(category=category, choice=choice).order,
            0,
        )
        index_response = self.client.get(reverse('tierlist:index'))
        self.assertIn(choice, index_response.context['choicelist'])

    def test_update_order_allows_choice_in_multiple_categories(self):
        first_category = Category.objects.create(tier_list=self.tier_list, name='Top tier')
        second_category = Category.objects.create(tier_list=self.tier_list, name='Second tier')
        choice = Choice.objects.create(tier_list=self.tier_list, name='Choice')

        for category in (first_category, second_category):
            response = self.client.post(
                reverse('tierlist:update_order'),
                {'category_id': str(category.pk), 'item_id': [str(choice.pk)]},
            )
            self.assertEqual(response.status_code, 200)

        self.assertEqual(
            CategoryChoice.objects.filter(choice=choice).count(),
            2,
        )

    def test_update_order_deduplicates_choice_within_category(self):
        category = Category.objects.create(tier_list=self.tier_list, name='Top tier')
        choice = Choice.objects.create(tier_list=self.tier_list, name='Choice')

        response = self.client.post(
            reverse('tierlist:update_order'),
            {
                'category_id': str(category.pk),
                'item_id': [str(choice.pk), str(choice.pk)],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            CategoryChoice.objects.filter(category=category, choice=choice).count(),
            1,
        )

    def test_update_order_reorders_category_items(self):
        category = Category.objects.create(tier_list=self.tier_list, name='Top tier')
        first = Choice.objects.create(tier_list=self.tier_list, name='First')
        second = Choice.objects.create(tier_list=self.tier_list, name='Second')
        CategoryChoice.objects.create(category=category, choice=first, order=0)
        CategoryChoice.objects.create(category=category, choice=second, order=1)

        response = self.client.post(
            reverse('tierlist:update_order'),
            {
                'category_id': str(category.pk),
                'item_id': [str(second.pk), str(first.pk)],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            CategoryChoice.objects.get(category=category, choice=second).order,
            0,
        )
        self.assertEqual(
            CategoryChoice.objects.get(category=category, choice=first).order,
            1,
        )

    def test_delete_choice_cascades_to_category_memberships(self):
        category = Category.objects.create(tier_list=self.tier_list, name='Top tier')
        choice = Choice.objects.create(tier_list=self.tier_list, name='Choice')
        CategoryChoice.objects.create(category=category, choice=choice)

        response = self.client.post(
            reverse('tierlist:delete_choice', args=[choice.pk]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Choice.objects.filter(pk=choice.pk).exists())
        self.assertFalse(CategoryChoice.objects.filter(choice=choice).exists())

    def test_remove_category_choice_keeps_choice_and_other_memberships(self):
        first_category = Category.objects.create(tier_list=self.tier_list, name='Top tier')
        second_category = Category.objects.create(tier_list=self.tier_list, name='Second tier')
        choice = Choice.objects.create(tier_list=self.tier_list, name='Choice')
        CategoryChoice.objects.create(category=first_category, choice=choice)
        CategoryChoice.objects.create(category=second_category, choice=choice)

        response = self.client.post(
            reverse(
                'tierlist:remove_category_choice',
                args=[first_category.pk, choice.pk],
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Choice.objects.filter(pk=choice.pk).exists())
        self.assertFalse(
            CategoryChoice.objects.filter(
                category=first_category,
                choice=choice,
            ).exists()
        )
        self.assertTrue(
            CategoryChoice.objects.filter(
                category=second_category,
                choice=choice,
            ).exists()
        )

    def test_delete_category_cascades_to_category_memberships(self):
        category = Category.objects.create(tier_list=self.tier_list, name='Top tier')
        choice = Choice.objects.create(tier_list=self.tier_list, name='Choice')
        CategoryChoice.objects.create(category=category, choice=choice)

        response = self.client.post(
            reverse('tierlist:delete_category', args=[category.pk]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Category.objects.filter(pk=category.pk).exists())
        self.assertTrue(Choice.objects.filter(pk=choice.pk).exists())
        self.assertFalse(CategoryChoice.objects.filter(category=category).exists())

    def test_update_category_persists_name_and_weight(self):
        category = Category.objects.create(tier_list=self.tier_list, name='Top tier', weight=0.2)

        response = self.client.post(
            reverse('tierlist:update_category', args=[category.pk]),
            {'name': 'Best tier', 'weight': '0.85'},
        )

        self.assertEqual(response.status_code, 302)
        category.refresh_from_db()
        self.assertEqual(category.name, 'Best tier')
        self.assertEqual(category.weight, 0.85)

    def test_update_category_rejects_invalid_weight(self):
        category = Category.objects.create(tier_list=self.tier_list, name='Top tier', weight=0.2)

        response = self.client.post(
            reverse('tierlist:update_category', args=[category.pk]),
            {'name': 'Changed tier', 'weight': '1.5'},
        )

        self.assertEqual(response.status_code, 302)
        category.refresh_from_db()
        self.assertEqual(category.name, 'Top tier')
        self.assertEqual(category.weight, 0.2)

    def test_update_category_rejects_weight_below_point_one(self):
        category = Category.objects.create(tier_list=self.tier_list, name='Top tier', weight=0.2)

        response = self.client.post(
            reverse('tierlist:update_category', args=[category.pk]),
            {'name': 'Changed tier', 'weight': '0.05'},
        )

        self.assertEqual(response.status_code, 302)
        category.refresh_from_db()
        self.assertEqual(category.name, 'Top tier')
        self.assertEqual(category.weight, 0.2)

    def test_add_choice_stops_at_fifty_choices(self):
        Choice.objects.bulk_create(
            [Choice(tier_list=self.tier_list, name=f'Choice {index}', order=index) for index in range(50)]
        )

        response = self.client.post(
            reverse('tierlist:add_choice'),
            {'name': 'Choice 51'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Choice.objects.count(), 50)

    def test_add_category_stops_at_ten_categories(self):
        Category.objects.bulk_create(
            [Category(tier_list=self.tier_list, name=f'Category {index}') for index in range(10)]
        )

        response = self.client.post(
            reverse('tierlist:add_category'),
            {'name': 'Category 11'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Category.objects.count(), 10)

    def test_ranking_includes_only_choices_in_every_category(self):
        first_category = Category.objects.create(tier_list=self.tier_list, name='First', weight=1)
        second_category = Category.objects.create(tier_list=self.tier_list, name='Second', weight=0.5)
        ranked = Choice.objects.create(tier_list=self.tier_list, name='Ranked')
        incomplete = Choice.objects.create(tier_list=self.tier_list, name='Incomplete')
        CategoryChoice.objects.create(category=first_category, choice=ranked, order=1)
        CategoryChoice.objects.create(category=second_category, choice=ranked, order=0)
        CategoryChoice.objects.create(category=first_category, choice=incomplete, order=0)

        response = self.client.get(reverse('tierlist:index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['choice'] for item in response.context['rankings']], [ranked])
        self.assertEqual(response.context['rankings'][0]['score'], 1.0)

    def test_ranking_is_sorted_by_score(self):
        first_category = Category.objects.create(tier_list=self.tier_list, name='First', weight=1)
        second_category = Category.objects.create(tier_list=self.tier_list, name='Second', weight=1)
        best = Choice.objects.create(tier_list=self.tier_list, name='Best')
        next_choice = Choice.objects.create(tier_list=self.tier_list, name='Next')
        CategoryChoice.objects.create(category=first_category, choice=best, order=0)
        CategoryChoice.objects.create(category=second_category, choice=best, order=1)
        CategoryChoice.objects.create(category=first_category, choice=next_choice, order=1)
        CategoryChoice.objects.create(category=second_category, choice=next_choice, order=0)

        response = self.client.get(reverse('tierlist:index'))

        self.assertEqual(
            [item['choice'] for item in response.context['rankings']],
            [best, next_choice],
        )

    def test_users_cannot_see_or_mutate_each_others_data(self):
        choice = Choice.objects.create(tier_list=self.tier_list, name='Private')
        other = get_user_model().objects.create_user(
            username='other',
            password='test-password-123',
        )
        other_list = TierList.objects.create(owner=other)

        self.client.login(username='other', password='test-password-123')
        response = self.client.get(reverse('tierlist:index'))
        self.assertNotContains(response, 'Private')

        self.client.post(reverse('tierlist:delete_choice', args=[choice.pk]))
        self.assertTrue(Choice.objects.filter(pk=choice.pk, tier_list=self.tier_list).exists())
        self.assertFalse(Choice.objects.filter(tier_list=other_list).exists())

    def test_anonymous_users_can_open_an_empty_tierlist(self):
        self.client.logout()
        response = self.client.get(reverse('tierlist:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No choices yet.')

    def test_anonymous_choice_order_matches_visible_order(self):
        self.client.logout()
        self.client.post(reverse('tierlist:add_choice'), {'name': 'First'})
        self.client.post(reverse('tierlist:add_choice'), {'name': 'Second'})
        first, second = self.client.session['tierlist_draft']['choices']
        self.assertEqual(first['color'], self.tier_list.palette[0])
        self.assertEqual(second['color'], self.tier_list.palette[1])
        self.assertNotEqual(first['color'], second['color'])

        self.client.post(
            reverse('tierlist:update_order'),
            {'item_id': [str(first['id']), str(second['id'])]},
        )

        response = self.client.get(reverse('tierlist:index'))
        html = response.content.decode()
        self.assertLess(html.find('Second'), html.find('First'))

    def test_anonymous_draft_can_be_edited_and_saved_after_login(self):
        self.client.logout()
        self.client.post(reverse('tierlist:add_choice'), {'name': 'Guest choice'})
        self.client.post(reverse('tierlist:add_category'), {'name': 'Guest category'})
        choice_id = self.client.session['tierlist_draft']['choices'][0]['id']
        category_id = self.client.session['tierlist_draft']['categories'][0]['id']
        self.client.post(
            reverse('tierlist:update_palette'),
            {'palette_index': '1', 'color': '#a1b2c3'},
        )
        self.client.post(
            reverse('tierlist:update_choice_color', args=[choice_id]),
            {'color': '#d4e5f6'},
        )
        self.client.post(
            reverse('tierlist:update_order'),
            {'category_id': str(category_id), 'item_id': [str(choice_id)]},
        )
        guest_response = self.client.get(reverse('tierlist:index'))
        self.assertEqual(guest_response.content.decode().count('--choice-color: #d4e5f6'), 3)

        response = self.client.get(reverse('tierlist:save'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('tierlist:save')}",
        )
        self.assertFalse(
            Choice.objects.filter(tier_list=self.tier_list, name='Guest choice').exists()
        )

        self.client.login(username='owner', password='test-password-123')
        response = self.client.post(reverse('tierlist:save'))

        self.assertRedirects(response, reverse('tierlist:index'))
        saved_choice = Choice.objects.get(tier_list=self.tier_list, name='Guest choice')
        saved_category = Category.objects.get(tier_list=self.tier_list, name='Guest category')
        self.tier_list.refresh_from_db()
        self.assertEqual(self.tier_list.palette[1], '#a1b2c3')
        self.assertEqual(saved_choice.color, '#d4e5f6')
        self.assertEqual(saved_category.weight, 1)
        self.assertTrue(
            CategoryChoice.objects.filter(category=saved_category, choice=saved_choice).exists()
        )
        self.assertNotIn('tierlist_draft', self.client.session)

    def test_save_draft_requires_post(self):
        response = self.client.get(reverse('tierlist:save'))

        self.assertEqual(response.status_code, 405)

    def test_registration_creates_user_and_personal_tier_list(self):
        self.client.logout()
        response = self.client.post(
            reverse('tierlist:register'),
            {
                'username': 'new-user',
                'password1': 'new-password-123',
                'password2': 'new-password-123',
            },
        )

        self.assertRedirects(response, reverse('tierlist:index'))
        new_user = get_user_model().objects.get(username='new-user')
        self.assertTrue(TierList.objects.filter(owner=new_user).exists())
