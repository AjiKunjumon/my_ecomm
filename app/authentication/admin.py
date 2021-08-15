import csv
from datetime import date, timedelta

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import F, IntegerField, Q
from django.db.models.functions import Cast
from django.forms import BaseInlineFormSet
from django.http import HttpResponse
from django.utils.timezone import now

from rest_framework.authtoken.admin import TokenAdmin

from app.authentication.models import Member
from app.authentication.models.extensions import Rank
from app.authentication.models.member import EcommMemberPermission
from app.utilities.helpers import convert_date_time_to_kuwait_string
from django.contrib.auth.models import Permission


class MemberCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(
        label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = Member
        fields = (
            "first_name", "last_name", "username", "email", "gender",
            "birthday", "phone", "avatar", "is_verified", "groups",
            "country_code"
        )

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if username:
            if any(x.isupper() for x in username):
                raise forms.ValidationError("Username contains uppercase")
            return username
        return None

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super(MemberCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()

        return user


class MemberChangeForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = (
            "first_name", "last_name", "username", "email", "gender",
            "birthday", "phone", "avatar", "beams", "is_verified", "beams",
            "is_business", "is_tag", "is_location", "has_checkin_history",
            "groups", "country_code",
        )

    def clean_username(self):
        username = self.cleaned_data.get("username", None)
        if username:
            if any(x.isupper() for x in username):
                raise forms.ValidationError("Username contains uppercase")
            return username
        return None


class BeamersFilter(admin.SimpleListFilter):
    title = "Beamers"
    parameter_name = "beamers"

    def lookups(self, request, model_admin):
        return (
            (True, "Yes"),
            (False, "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "True":
            return queryset.filter(
                is_superuser=False, is_admin=False, is_business=False,
                is_location=False, is_tag=False
            )
        return queryset


class IsPrivateFilter(admin.SimpleListFilter):
    title = "Private"
    parameter_name = "is_private"

    def lookups(self, request, model_admin):
        return (
            (True, "Yes"),
            (False, "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "True":
            return queryset.filter(
                is_private=True
            )
        elif self.value() == "False":
            return queryset.filter(
                is_private=False
            )
        return queryset


class GenderFilter(admin.SimpleListFilter):
    title = "Gender"
    parameter_name = "gender"

    def lookups(self, request, model_admin):
        return (
            ("M", "Male"),
            ("F", "Female"),
            ("NA", "NA"),
        )

    def queryset(self, request, queryset):
        if self.value() == "M":
            return queryset.filter(
                gender='M'
            )
        elif self.value() == "F":
            return queryset.filter(
                gender='F'
            )
        elif self.value() == "NA":
            return queryset.filter(
                gender='NA'
            )
        return queryset


class AgeFilter(admin.SimpleListFilter):
    title = "Age"
    parameter_name = "birthday"
    age_choices = {
        '0': {'lower': 0, 'upper': 10},
        '1': {'lower': 10, 'upper': 20},
        '2': {'lower': 21, 'upper': 30},
        '3': {'lower': 31, 'upper': 40},
        '4': {'lower': 41, 'upper': 50},
        '5': {'lower': 51, 'upper': 60},
        '6': {'lower': 61, 'upper': 70},
        '7': {'lower': 71, 'upper': 80},
        '8': {'lower': 81, 'upper': 90},
        '9': {'lower': 91, 'upper': 100}
    }

    def lookups(self, request, model_admin):
        return (
            (0, '0-10'),
            (1, '10-20'),
            (2, '21-30'),
            (3, '31-40'),
            (4, '41-50'),
            (5, '51-60'),
            (6, '61-70'),
            (7, '71-80'),
            (8, '81-90'),
            (9, '91-100'),
        )

    def queryset(self, request, queryset):
        age_range = self.age_choices.get(self.value())
        if self.value() and age_range is not None:
            return queryset.annotate(
                age=Cast(date.today() - F('birthday'),
                         output_field=IntegerField())
            ).filter(age__gte=365.2425*age_range['lower'],
                     age__lte=365.2425*age_range['upper'])
        return queryset


class EligibleBeamersFilter(admin.SimpleListFilter):
    title = "Eligible For Beam Program"
    parameter_name = "beam_eligibility"

    def lookups(self, request, model_admin):
        return (
            (True, "Yes"),
            (False, "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "True":
            eligible_beamers = Member.members.eligible_beamers()
            eligible_beamers_filter = filter(lambda x: x.meets_country_follower_restriction_for_beams(),
                                      eligible_beamers)
            return eligible_beamers.filter(id__in=list([x.id for x in eligible_beamers_filter]))
        elif self.value() == "False":
            return queryset
        return queryset


class WithDrawRequestedFilter(admin.SimpleListFilter):
    title = "Requested for WithDrawal"
    parameter_name = "withdraw_requested"

    def lookups(self, request, model_admin):
        return (
            (True, "Yes"),
            (False, "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "True":
            return Member.objects.filter(
                member_beam_program_request__status="WR")
        elif self.value() == "False":
            return queryset
        return queryset


class EligibilityemailsentFilter(admin.SimpleListFilter):
    title = "Eligibility Email Sent"
    parameter_name = "beams_eligibility_email_sent"

    def lookups(self, request, model_admin):
        return (
            (True, "Yes"),
            (False, "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "True":
            return Member.objects.filter(
                beams_eligibility_email_sent=True)
        elif self.value() == "False":
            return queryset.filter(
                beams_eligibility_email_sent=False
            )
        return queryset


class EligibleButEmailNotVerifiedFilter(admin.SimpleListFilter):
    title = "Eligible for Beams Without Email Verified"
    parameter_name = "eligible_for_beams_without_email_verified"

    def lookups(self, request, model_admin):
        return (
            (True, "Yes"),
            (False, "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "True":
            eligible_beamers_without_email_verified = Member.members.eligible_beamers_without_email_verified()
            eligible_beamers_filter = filter(lambda x: x.meets_country_follower_restriction_for_beams(),
                                             eligible_beamers_without_email_verified)
            return eligible_beamers_without_email_verified.filter(id__in=list([x.id for x in eligible_beamers_filter]))
        elif self.value() == "False":
            return queryset
        return queryset


class ExportCsvMixin:
    def export_as_csv(self, request, queryset):

        meta = self.model._meta
        member_fields_to_fetch = ["username", "first_name", "last_name", "email", "birthday"]
        member_field_names = [field.name for field in meta.fields if field.name in member_fields_to_fetch]

        business_field_names = ["username", "first_name", "last_name", "is_business", "email",
                                "locations"]

        non_business = queryset.filter(is_business=False)

        if non_business.count() > 0:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=members.csv'
            writer = csv.writer(response)

            writer.writerow(member_field_names)
            for obj in queryset:
                row = writer.writerow([getattr(obj, field) for field in member_field_names])
        else:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=businesses.csv'
            writer = csv.writer(response)

            writer.writerow(business_field_names)
            for obj in queryset:
                row = writer.writerow([getattr(obj, field) if field != "locations"
                                       else obj.locations_count() for field in business_field_names])

        return response

    export_as_csv.short_description = "Export Selected"


class PostsCreatedBefore30Days(BaseInlineFormSet):
    def get_queryset(self):
        thirtydays_back = now() - timedelta(days=30)
        if not hasattr(self, '_queryset'):
            if settings.SITE_CODE == 1:
                qs = super(BaseInlineFormSet, self).get_queryset().filter(
                    created_at__lte=thirtydays_back,
                    member=self.instance, is_reposted=False,
                    is_media_uploaded=True)
            else:
                qs = super(BaseInlineFormSet, self).get_queryset().filter(
                    created_at__lte=thirtydays_back,
                    member=self.instance, is_reposted=False,
                    is_media_uploaded=True, has_been_added_for_beam_program=True)
            self._queryset = qs
        return self._queryset


class MemberAdmin(UserAdmin, ExportCsvMixin):
    form = MemberChangeForm
    add_form = MemberCreationForm

    list_display = (
        "username", "id", "beams", "is_private", "has_enabled_public_checkins", "created_at",
        "created_time_in_kuwait", "beams_eligibility_email_sent",
        "country_code", "nationality_code"
    )
    list_filter = (
        "is_verified", IsPrivateFilter, "is_business", "is_location", "is_active",
        "is_tag", BeamersFilter, GenderFilter, AgeFilter, EligibleBeamersFilter,
        WithDrawRequestedFilter, EligibilityemailsentFilter, EligibleButEmailNotVerifiedFilter,
        "is_superuser"
    )
    fieldsets = ((None, {
        "fields": (
            "first_name", "last_name", "username", "email", "contact_email",
            "birthday", "gender", "phone", "avatar", "resized_avatar", "is_verified",
            "is_active", "no_of_followers", "no_of_following", "beams",
            "is_business", "is_private", "is_location", "is_tag",
            "has_checkin_history", "groups", "is_email_verified",
            "country_code", "nationality_code", "has_enabled_public_checkins",
            "last_time_checked_nfs_api", "last_nfs_posts_count", "last_changed_to_public",
            "money_earned_for_beams", "req_money_for_beams", "beams_eligibility_email_sent",
            "beams_eligibility_email_sent_time", "share_profile_avatar", "can_download_media",
            "is_mobile_verified", "full_name", "wishlishted_products", "is_seller",
            "is_super_admin", "has_full_access", "status"
        )
    }),)

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "first_name", "last_name", "username", "email", "contact_email",
                "phone", "avatar", "password1", "password2", "birthday", "groups",
                "country_code",
            )
        }),
    )
    search_fields = ('email', 'contact_email', 'username', 'first_name', "last_name", "pk",
                     "phone")
    ordering = ('email',)
    filter_horizontal = ()
    actions = ["export_as_csv"]

    def created_time_in_kuwait(self, obj):
        return convert_date_time_to_kuwait_string(obj.created_at)

    def save_model(self, request, obj, form, change):
        groups = form.cleaned_data.get("groups", None)
        for group in groups:
            if group.name == "talent acquisition":
                obj.is_active = True
                obj.is_staff = True
                obj.is_admin = True
        if not obj.is_private and 'is_private' in form.changed_data:
            obj.last_changed_to_public = now()
        return super().save_model(request, obj, form, change)


class EcommMemberPermissionAdmin(admin.ModelAdmin):
    model = EcommMemberPermission
    list_display = (
         "module", "name", "has_view_access",
         "has_add_access", "has_edit_access",
         "has_delete_access"
    )


admin.site.register(Member, MemberAdmin)
admin.site.register(Rank)
admin.site.register(Permission)
admin.site.register(EcommMemberPermission, EcommMemberPermissionAdmin)

admin.site.site_header = "Becon Administration"
TokenAdmin.search_fields = ["user__username", ]
