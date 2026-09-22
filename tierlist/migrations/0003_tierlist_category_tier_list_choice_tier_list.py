from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tierlist', '0002_remove_category_weight_gte_zero_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TierList',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(default='My tier list', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='tier_list', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='category',
            name='tier_list',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='tierlist.tierlist'),
        ),
        migrations.AddField(
            model_name='choice',
            name='tier_list',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='tierlist.tierlist'),
        ),
        migrations.RunSQL(
            sql=(
                'DELETE FROM tierlist_categorychoice; '
                'DELETE FROM tierlist_choice; '
                'DELETE FROM tierlist_category;'
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name='category',
            name='tier_list',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tierlist.tierlist'),
        ),
        migrations.AlterField(
            model_name='choice',
            name='tier_list',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tierlist.tierlist'),
        ),
    ]
