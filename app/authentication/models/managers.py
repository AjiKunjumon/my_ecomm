from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet, Q
from django.utils.timezone import now, timedelta
from django.contrib.auth.models import BaseUserManager


class MemberManager(BaseUserManager):
    def create_user(self, first_name, last_name, username, email, birthday,
                    gender, phone=None, password=None):
        if not first_name:
            raise ValueError("First name is required")

        if not last_name:
            raise ValueError("Last name is required")

        if not username:
            raise ValueError("Username is required")

        if not email:
            raise ValueError("Email is required")

        if not birthday:
            raise ValueError("Birthday is required")

        if not gender:
            raise ValueError("Gender is required")

        user = self.model(
            first_name=first_name, last_name=last_name, username=username,
            email=email, birthday=birthday, gender=gender, phone=phone
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(
        self, first_name, last_name, username, email, birthday, gender,
        phone=None, password=None
    ):
        user = self.create_user(
            first_name=first_name, last_name=last_name, username=username,
            email=email, birthday=birthday, gender=gender, phone=phone,
            password=password
        )

        user.is_superuser = True
        user.is_admin = True
        user.is_staff = True
        user.save(using=self._db)

        return user

    def make_location_admin(self, location):
        pk = location.pk
        first_name = "location_fname_%s" % pk
        last_name = "location_lname_%s" % pk
        username = "locatin_uname_%s" % pk
        email = "location_email%s@becontemp.com" % pk

        admin = self.create_user(
            first_name, last_name, username, email, "1989-12-04", "M")

        admin.is_location = True
        admin.save()

        location.admin = admin
        location.save()

        return admin


class MemberQueryset(QuerySet):
    def businesses(self):
        return self.filter(is_business=True, is_active=True)

    def locations(self):
        return self.filter(is_location=True, is_active=True)

    def private_members(self):
        return self.filter(is_private=True, is_active=True)

    def verified_members(self):
        return self.filter(is_verified=True, is_active=True)

    def beamer_members(self):
        return self.filter(
            is_business=False, is_location=False, is_admin=False,
            is_active=True, is_tag=False
        )

    def private_beamers(self):
        return self.beamer_members().filter(is_private=True)

    def beamers(self, user, exclude_self=True):
        return self.beamer_members().exclude(
            pk__in=user.exclude_users(exclude_self=exclude_self))

    def non_beamers(self, user):
        return self.filter(
            is_admin=False, is_active=True
        ).exclude(pk__in=user.exclude_users(exclude_self=False))

    def business_n_user_members(self, user):
        return self.non_beamers(user).filter(is_location=False, is_tag=False)

    def top_kuwait_beamers_explore(self, user):
        members = self.beamers(user, exclude_self=False).order_by("-beams")
        if members.count() > 10:
            return members[:10]
        return members

    def get_suitable_members(self, user, is_exploring):
        if is_exploring:
            return self.beamers(user)
        return self.business_n_user_members(user)

    def search_qs(self, qs, search_string):
        if search_string != "":
            return qs.filter(
                Q(username__icontains=search_string) |
                Q(first_name__icontains=search_string) |
                Q(last_name__icontains=search_string)
            )
        return qs

    def search(self, user, search_string, is_exploring):
        qs = self.get_suitable_members(user, is_exploring)
        return self.search_qs(qs, search_string)

    def top_beamers(self, user):
        excluded_ids = user.exclude_users(exclude_self=False)
        return self.beamer_members().exclude(
            pk__in=excluded_ids).order_by("-beams")

    def top_county_beamers(self, user):
        excluded_ids = user.exclude_users(exclude_self=True)
        rest = self.beamer_members().exclude(
            pk__in=excluded_ids, username="becon").order_by("-beams")
        becon_users = self.filter(username="becon")
        data = [x for x in becon_users]
        for user in rest:
            data.append(user)
        return data

    def new_trendings_members(self):
        last_hour = now() - timedelta(hours=1)
        members = self.beamer_members().filter(updated_at__gte=last_hour)
        list_data = []
        for user in members:
            list_data.append((0, user.pk, user.last_hour_followers()))
        return sorted(
            list_data, key=lambda x: x[2], reverse=True
        )[:settings.MEMBER_COUNT]


class RankQueryset(QuerySet):
    def create_object(self, member, current_rank):
        return self.create(
            member=member,
            current_rank=current_rank,
            previous_rank=0,
            beams=member.beams
        )

    def get_member_rank(self, member, ranks):
        try:
            rank = ranks.get(member=member)
            return rank
        except ObjectDoesNotExist:
            current_rank = ranks.count() + 1
            return self.create_object(member, current_rank)