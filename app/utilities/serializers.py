from rest_framework import serializers

from app.authentication.models import Member
from app.location.models import Location


class ImageMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ("id", "resized_avatar", "is_verified")


class LocationTagSerializer(serializers.ModelSerializer):
    has_seen = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = (
            "id", "name", "vicinity", "image", "is_registered", "has_seen",
            "place_id", "admin"
        )

    def get_has_seen(self, obj):
        if self.context is None:
            return False
        user = self.context.get("user")
        post = self.context.get("post")
        return user.has_seen_location_tag(post, obj)
