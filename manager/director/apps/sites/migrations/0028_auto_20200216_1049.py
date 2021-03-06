# Generated by Django 2.2.10 on 2020-02-16 15:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0027_siteresourcelimits'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteresourcelimits',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='operation',
            name='type',
            field=models.CharField(choices=[('create_site', 'Creating site'), ('rename_site', 'Renaming site'), ('edit_site_names', 'Changing site name/domains'), ('change_site_type', 'Changing site type'), ('regen_nginx_config', 'Regenerating Nginx configuration'), ('create_site_database', 'Creating site database'), ('delete_site_database', 'Deleting site database'), ('regen_site_secrets', 'Regenerating site secrets'), ('update_resource_limits', 'Updating site resource limits'), ('update_docker_image', 'Updating site Docker image'), ('delete_site', 'Deleting site'), ('restart_site', 'Restarting site')], max_length=24),
        ),
    ]
