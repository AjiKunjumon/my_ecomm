from rest_framework.test import APITestCase

from app.authentication.tests.factories import MemberFactory
from app.post.tests.factories import PostFactory, PostMediaFactory
from app.location.tests.factories import (
    FavouriteLocationFactory, LocationFactory, CheckInFactory
)
from app.business.tests.factories import BusinessFactory


class BaseTestCase(APITestCase):
    def setUp(self):
        self.member = MemberFactory()
        self.client.force_authenticate(user=self.member)

    def get_post(self):
        self.post = PostFactory(
            member=self.member, is_media_uploaded=True
        )
        PostMediaFactory(post=self.post, is_cover=True)
        return self.post

    def set_up_featured_post(self):
        featured_post = self.get_post()
        featured_post.is_featured = True
        featured_post.save()

    def set_up_fav_locations(self):
        FavouriteLocationFactory(
            location=LocationFactory(place_id="1234"),
            member=self.member, order=1)
        FavouriteLocationFactory(
            location=LocationFactory(place_id="1235"),
            member=self.member, order=2)
        FavouriteLocationFactory(
            location=LocationFactory(place_id="12346"),
            member=self.member, order=3)

    def set_up_beamers(self):
        self.member1 = MemberFactory(beams=300)
        self.member2 = MemberFactory(beams=200)
        self.member3 = MemberFactory(beams=100)

    def set_up_business(self):
        self.business = BusinessFactory()

    def set_up_business_locations(self):
        self.set_up_business()
        self.bus_loc1 = LocationFactory(
            business=self.business, place_id="123")
        self.bus_loc2 = LocationFactory(
            business=self.business, place_id="456")
        self.bus_loc3 = LocationFactory(
            business=self.business, place_id="789")

    def set_up_bus_loc_checkins(self):
        self.set_up_business_locations()
        CheckInFactory(location=self.bus_loc1)
        CheckInFactory(location=self.bus_loc2)
        CheckInFactory(location=self.bus_loc3)

    def set_up_unregistered_locations(self):
        self.location1 = LocationFactory(place_id="1234")
        self.location2 = LocationFactory(place_id="5678")
        self.location3 = LocationFactory(place_id="9101")
