from django.test import TestCase
from django.urls import reverse

from .models import Choice


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
