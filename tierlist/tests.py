from django.test import TestCase
from django.urls import reverse

from .models import Category, CategoryChoice, Choice


class ChoiceOrderingTests(TestCase):
    def test_index_uses_choice_order_not_alpha_name_order(self):
        Choice.objects.create(name='Second', order=1)
        Choice.objects.create(name='First', order=0)

        response = self.client.get(reverse('tierlist:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Second')
        self.assertContains(response, 'First')

        html = response.content.decode()
        first_index = html.find('Second')
        second_index = html.find('First')
        self.assertLess(first_index, second_index)

    def test_update_order_persists_item_sequence(self):
        first = Choice.objects.create(name='First', order=0)
        second = Choice.objects.create(name='Second', order=1)

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
        category = Category.objects.create(name='Top tier')
        choice = Choice.objects.create(name='Choice')

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
        first_category = Category.objects.create(name='Top tier')
        second_category = Category.objects.create(name='Second tier')
        choice = Choice.objects.create(name='Choice')

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
        category = Category.objects.create(name='Top tier')
        choice = Choice.objects.create(name='Choice')

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
        category = Category.objects.create(name='Top tier')
        first = Choice.objects.create(name='First')
        second = Choice.objects.create(name='Second')
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
        category = Category.objects.create(name='Top tier')
        choice = Choice.objects.create(name='Choice')
        CategoryChoice.objects.create(category=category, choice=choice)

        response = self.client.post(
            reverse('tierlist:delete_choice', args=[choice.pk]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Choice.objects.filter(pk=choice.pk).exists())
        self.assertFalse(CategoryChoice.objects.filter(choice=choice).exists())

    def test_remove_category_choice_keeps_choice_and_other_memberships(self):
        first_category = Category.objects.create(name='Top tier')
        second_category = Category.objects.create(name='Second tier')
        choice = Choice.objects.create(name='Choice')
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
