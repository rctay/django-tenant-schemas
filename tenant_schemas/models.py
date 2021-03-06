from django.conf import settings
from django.db import models, connection, transaction
from tenant_schemas.postgresql_backend.base import _check_identifier
from django.core.management import call_command
from tenant_schemas.utils import django_is_in_test_mode

class TenantMixin(models.Model):
    auto_create_schema = True # set this flag to false on a parent class if
                              # you dont want the schema to be automatically
                              # created upon save.

    domain_url = models.CharField(max_length=128, unique=True)
    schema_name = models.CharField(max_length=63)

    class Meta:
        abstract = True


    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super(TenantMixin, self).save(*args, **kwargs)

        if is_new and self.auto_create_schema:
            self.create_schema(check_if_exists=True)

        transaction.commit_unless_managed()

    def create_schema(self, check_if_exists = False, sync_schema = True):
        """
        Creates the schema 'schema_name' for this tenant. Optionally checks if the schema
        already exists before creating it. Returns true if the schema was created, false
        otherwise.
        """

        # safety check
        _check_identifier(self.schema_name)
        cursor = connection.cursor()

        if check_if_exists:
            # check if this schema already exists in the db
            sql = 'SELECT schema_name FROM information_schema.schemata '\
                  'WHERE schema_name = %s'
            cursor.execute(sql, (self.schema_name,))

            if len(cursor.fetchall()) > 0:
                # we already have a row
                return False

        # create the schema
        cursor.execute('CREATE SCHEMA %s' % self.schema_name)

        if sync_schema:
            call_command('sync_schemas', schema_name=self.schema_name,
                    interactive=False) # don't ask to create an admin user

            # make sure you have SOUTH_TESTS_MIGRATE = false
            if 'south' in settings.INSTALLED_APPS and not django_is_in_test_mode():
                call_command('migrate_schemas', schema_name=self.schema_name)

        return True