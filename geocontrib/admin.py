import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.flatpages.admin import FlatPageAdmin
from django.contrib.flatpages.models import FlatPage
from django.contrib.gis import admin
from django.db import connections
from django.forms import formset_factory
from django.forms import modelformset_factory
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

from geocontrib.forms import FeatureTypeAdminForm
from geocontrib.forms import CustomFieldModelAdminForm
from geocontrib.forms import HiddenDeleteBaseFormSet
from geocontrib.forms import HiddenDeleteModelFormSet
from geocontrib.forms import FeatureSelectFieldAdminForm
from geocontrib.forms import AddPosgresViewAdminForm
from geocontrib.models import Authorization
from geocontrib.models import Feature
from geocontrib.models import Project
from geocontrib.models import Subscription
from geocontrib.models import FeatureType
from geocontrib.models import Layer
from geocontrib.models import CustomField
from geocontrib.models import UserLevelPermission
# from geocontrib.models import CustomFieldInterface

logger = logging.getLogger(__name__)
User = get_user_model()


class UserAdmin(DjangoUserAdmin):

    list_display = (
        'email', 'last_name', 'first_name',
        'is_superuser', 'is_administrator', 'is_staff', 'is_active'
    )
    search_fields = ('id', 'email', 'first_name', 'last_name')

    ordering = ('-pk', )
    verbose_name_plural = 'utilisateurs'
    verbose_name = 'utilisateur'

    readonly_fields = (
        'id',
        'date_joined',
        'last_login',
    )

    fieldsets = (
        (None, {
            'fields': ('username', 'email', 'password')
        }),
        (_('Personal info'), {
            'fields': ('first_name', 'last_name',)
        }),
        (_('Permissions'), {
            'fields': (
                'is_active', 'is_staff', 'is_superuser', 'is_administrator',
                'groups', 'user_permissions'),
        }),
        (_('Important dates'), {
            'fields': (
                'last_login', 'date_joined'),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'password1', 'password2', 'first_name', 'last_name',
                'is_active', 'is_staff', 'is_superuser'),
        }),
    )


class CustomFieldTabular(admin.TabularInline):
    model = CustomField
    extra = 0
    can_delete = False
    can_order = True
    show_change_link = True
    view_on_site = False


class FeatureTypeAdmin(admin.ModelAdmin):
    form = FeatureTypeAdminForm
    readonly_fields = ('geom_type', )
    inlines = (
        CustomFieldTabular,
    )

    change_form_template = 'admin/geocontrib/with_create_postrgres_view.html'

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                '<int:feature_type_id>/create-postgres-view/',
                self.admin_site.admin_view(self.create_postgres_view),
                name='create_postgres_view'),
        ]
        return my_urls + urls

    def pop_deleted_forms(self, cleaned_data):
        return [row for row in cleaned_data if row.get('DELETE') is False]

    def exec_sql(self, request, sql_create_view, view_name):
        success = False
        with connections['default'].cursor() as cursor:
            try:
                cursor.execute(sql_create_view)
            except Exception as err:
                logger.exception('Postgres view creation failed: {0}'.format(sql_create_view))
                messages.error(request, "La vue postgres n'a pas pu etre générée: {0}".format(err))
            else:
                messages.success(request, "La vue postgres '{0}' est diponible. ".format(view_name))
                success = True
        return success

    def create_postgres_view(self, request, feature_type_id, *args, **kwargs):

        FeatureDetailSelectionFormset = formset_factory(
            FeatureSelectFieldAdminForm,
            formset=HiddenDeleteBaseFormSet,
            can_delete=True,
            extra=1
        )

        CustomFieldsFormSet = modelformset_factory(
            CustomField,
            can_delete=True,
            form=CustomFieldModelAdminForm,
            formset=HiddenDeleteModelFormSet,
            extra=0,
        )

        if request.method == 'POST':
            fds_formset = FeatureDetailSelectionFormset(request.POST or None, prefix='fds')
            cfs_formset = CustomFieldsFormSet(request.POST or None, prefix='cfs')

            pg_form = AddPosgresViewAdminForm(request.POST or None)
            if fds_formset.is_valid() and pg_form.is_valid() and cfs_formset.is_valid():
                view_name = pg_form.cleaned_data.get('name')

                fds_data = self.pop_deleted_forms(fds_formset.cleaned_data)
                cfs_data = self.pop_deleted_forms(cfs_formset.cleaned_data)

                feature_detail_selection = ", ".join([
                    "geocontrib_feature.{}{}".format(
                        row.get('related_field'),
                        " AS {}".format(row.get('alias')) if len(row.get('alias')) > 0 else ""
                    ) for row in fds_data])

                custom_field_selection = ", ".join([
                    "geocontrib_feature.feature_data ->> '{}'::text AS {}".format(
                        row.get('name'),
                        slugify(row.get('alias') if len(row.get('alias')) > 0 else row.get('name'))
                    ) for row in cfs_data])

                search_condition = "AND geocontrib_feature.status = '{}'".format(pg_form.cleaned_data.get('status'))
                sql = """
DROP VIEW IF EXISTS  {schema}.{view_name};
CREATE OR REPLACE VIEW {schema}.{view_name} AS
    SELECT {feature_detail_selection},
        {custom_field_selection}
    FROM geocontrib_feature
    WHERE
        geocontrib_feature.feature_type_id = '{feature_type_id}'
        {search_condition};
ALTER TABLE {schema}.{view_name} OWNER TO {user}""".format(
                    feature_detail_selection=feature_detail_selection,
                    custom_field_selection=custom_field_selection,
                    feature_type_id=feature_type_id,
                    search_condition=search_condition,
                    schema=getattr(settings, 'DB_SCHEMA', 'public'),
                    view_name=view_name,
                    user=settings.DATABASES['default']['USER'],
                )

                its_alright = self.exec_sql(request, sql, view_name)
                if its_alright:
                    return redirect('admin:geocontrib_featuretype_change', feature_type_id)

            else:
                for formset in [fds_formset, pg_form, cfs_formset]:
                    logger.error(formset.errors)

        else:
            pg_form = AddPosgresViewAdminForm()
            fds_formset = FeatureDetailSelectionFormset(prefix='fds')
            cfs_formset = CustomFieldsFormSet(
                queryset=CustomField.objects.filter(feature_type__pk=feature_type_id),
                prefix='cfs')

        context = self.admin_site.each_context(request)
        context['opts'] = self.model._meta
        context['fds_formset'] = fds_formset
        context['cfs_formset'] = cfs_formset
        context['pg_form'] = pg_form

        return TemplateResponse(request, "admin/geocontrib/create_postrges_view_form.html", context)


class FlatPageAdmin(FlatPageAdmin):
    fieldsets = (
        (None, {'fields': ('url', 'title', 'content', 'sites')}),
        (_('Advanced options'), {
            'classes': ('collapse',),
            'fields': (
                'enable_comments',
                'registration_required',
                'template_name',
            ),
        }),
    )


admin.site.register(User, UserAdmin)
admin.site.register(CustomField)
admin.site.register(Layer)
admin.site.register(Authorization)
admin.site.register(Feature)
admin.site.register(FeatureType, FeatureTypeAdmin)
admin.site.register(Project)
admin.site.register(Subscription)
admin.site.register(UserLevelPermission)
# admin.site.register(CustomFieldInterface)
admin.site.unregister(FlatPage)
admin.site.register(FlatPage, FlatPageAdmin)
