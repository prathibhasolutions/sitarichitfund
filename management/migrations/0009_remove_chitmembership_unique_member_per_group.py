from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0008_chitmembership_committed_lift'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='chitmembership',
            unique_together={('chit_group', 'slot_number')},
        ),
    ]
