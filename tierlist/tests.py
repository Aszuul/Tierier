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

        html = response.content.decode()
        first_index = html.find('Second')
        second_index = html.find('First')
        self.assertLess(first_index, second_index)

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

    def test_anonymous_users_are_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('tierlist:index'))
        self.assertRedirects(response, '/accounts/login/?next=/tierlist/')

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
