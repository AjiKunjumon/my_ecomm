
from datetime import timedelta

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import validate_email
from django.db.models import Q, Case, When
f
from django.utils.timezone import now
from fcm_django.models import FCMDevice
from rest_framework import  status
from rest_framework.generics import ListAPIView, RetrieveAPIView, get_object_or_404, UpdateAPIView, CreateAPIView, \
    DestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from app.authentication.models import Member
from app.authentication.permissions import IsSuperAdminOrSeller, IsSuperAdmin
from app.authentication.serializers import GetSellerSerializer, CustomerListSerializer, \
    GuestListSerializer, CustomerDetailSerializer, CustomerEditSerializer, AddEditAddressSerializer, AddressSerializer, \
    CityDetailsSerializer, MemberSettingsSerializer, ChangePasswordSerializer, AddSuperAdminSerializer, \
    EditSuperAdminSerializer

from app.product.utils import json_list
from app.store.models import Address, City, SellerSubAdmins, Store
from app.utilities.api import validation_error
from app.utilities.utils import is_email_valid


class SellerLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def add_fcm_device(self, request):
        name = request.data.get("name", None)
        device_id = request.data.get("device_id", None)
        type = request.data.get("type", None)
        ip_address = request.data.get("ip_address", None)
        registration_id = request.data.get("registration_id", None)
        nationality_code = request.data.get("nationality_code", None)
        latitude = request.data.get("latitude", 0.0)
        longitude = request.data.get("longitude", 0.0)

        if registration_id:
            if request.user.is_authenticated:
                user_fcm_devices = FCMDevice.objects.filter(
                    name=name, device_id=device_id, type=type,
                    registration_id=registration_id,
                    nationality_code=nationality_code,
                    active=True, user=request.user,
                    ip_address=ip_address
                )
                if user_fcm_devices.exists():
                    fcm_device = user_fcm_devices.latest('id')
                    fcm_device.latitude = latitude
                    fcm_device.longitude = longitude
                    fcm_device.save()
                else:
                    fcm_device = FCMDevice.objects.create(
                        name=name, device_id=device_id, type=type,
                        registration_id=registration_id,
                        nationality_code=nationality_code,
                        active=True, user=request.user,
                        latitude=latitude,
                        longitude=longitude,
                        is_ecomm_user=True,
                        ip_address=ip_address
                    )
            else:
                user_fcm_devices = FCMDevice.objects.filter(
                    name=name, device_id=device_id, type=type,
                    registration_id=registration_id,
                    nationality_code=nationality_code,
                    active=True,
                    ip_address=ip_address
                )
                if user_fcm_devices.exists():
                    fcm_device = user_fcm_devices.latest('id')
                    fcm_device.latitude = latitude
                    fcm_device.longitude = longitude
                    fcm_device.save()
                else:
                    fcm_device = FCMDevice.objects.create(
                        name=name, device_id=device_id, type=type,
                        registration_id=registration_id,
                        nationality_code=nationality_code,
                        active=True, latitude=latitude,
                        longitude=longitude,
                        is_ecomm_user=True,
                        ip_address=ip_address
                    )

            return fcm_device
        return None

    def update_user_in_fcm_device(self, member, fcm_token, device_id):
        fcm_device = None
        if fcm_token != "":
            try:
                fcm_device = FCMDevice.objects.filter(
                    registration_id=fcm_token, active=True).latest('id')
            except FCMDevice.DoesNotExist:
                fcm_device = None
        elif device_id != "":
            try:
                fcm_device = FCMDevice.objects.filter(
                    device_id=device_id, active=True).latest('id')
            except FCMDevice.DoesNotExist:
                fcm_device = None
        if fcm_device:
            fcm_device.user = member
            fcm_device.save()

        return fcm_device

    def post(self, request):
        fcm_token = self.request.query_params.get("fcm_token", "")
        device_id = self.request.query_params.get("device_id", "")

        email = request.data.get("email", None)
        password = request.data.get("password", None)

        member = authenticate(username=email, password=password)

        if member:
            if not member.is_active or member.status == "IN":
                return Response(
                    {"error": "Email/Password combination invalid"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not member.can_login_to_dashboard_app():
                return Response(
                    {"error": "User authentication failed"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            member.last_login = now()
            member.save()
            fcm_device = self.update_user_in_fcm_device(
                member, fcm_token, device_id)

            if fcm_device is None:
                fcm_device = self.add_fcm_device(request)
                if fcm_device:
                    fcm_device.user = member
                    fcm_device.save()

            return Response(GetSellerSerializer(member).data)
        return Response(
            {"error": "Email/Password combination invalid"},
            status=status.HTTP_401_UNAUTHORIZED
        )


class SellerDetailByToken(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def get(self, request):
        return Response(GetSellerSerializer(request.user).data)


class ForgotPassword(APIView):
    authentication_classes = []
    permission_classes = []

    def validate_email_address(self, email):
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False

    def post(self, request):
        try:
            data = request.data.get('email', None)
            if data is None:
                return validation_error("Email address is required")
            if not is_email_valid(data):
                return validation_error("Invalid email address")
            if self.validate_email_address(data):
                associated_user = Member.objects.filter(email__iexact=data)
                if associated_user.exists():
                    associated_user_latest = associated_user.latest('id')
                    if associated_user_latest.is_super_admin or associated_user_latest.is_seller:
                        return Response({"message": "Reset Password Email Sent Successfully",
                                         "resetPassString": associated_user_latest.resetPassString})
                return validation_error("Email entered doesn't exist ")
            return validation_error("Invalid email address")
        except Exception as e:
            print(e)
            return validation_error("Failed to send email")


class SellerDetails(RetrieveAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = CustomerDetailSerializer

    def get_object(self):
        obj = get_object_or_404(Member, pk=self.kwargs.get("pk"))
        return obj

    def get_serializer_context(self):
        return {"user": self.request.user}


class CustomerList(ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = CustomerListSerializer
    queryset = Member.objects.all()
    http_method_names = [u'get', u'post']

    def _allowed_methods(self):
        return [m.upper() for m in self.http_method_names if hasattr(self, m)]

    def search(self, qs, search_string):
        for qstring in search_string.split(" "):
            qs = qs.filter(
                Q(email__icontains=qstring) |
                Q(full_name__icontains=qstring)
            ).order_by('id').distinct()
        return qs

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        search_string = self.request.query_params.get("search_string", "")
        customer_status = self.request.query_params.get("customer_status", "")
        sort_by = self.request.query_params.get("sort_by", "")
        shipping_area_ids = self.request.data.get("shipping_area_ids", "")
        devices_list = self.request.data.get("devices_list", "")

        qs = Member.objects.filter(
            is_business=False, is_location=False,
            is_admin=False, is_tag=False,
            is_super_admin=False, is_seller=False
        ).order_by('-created_at')

        if customer_status == "IN":
            qs = qs.filter(status='IN')
        if customer_status == "AC":
            qs = qs.filter(status='AC')
        if search_string != "":
            qs = self.search(qs, search_string)

        if shipping_area_ids != "" and json_list(shipping_area_ids)[0]:
            address_customers = Address.objects.filter(
                customer__pk__in=qs.values_list('id', flat=True),
                area__pk__in=json_list(shipping_area_ids)[1]
            ).order_by('customer__id').values_list(
                'customer__id', flat=True).distinct('customer__id')

            qs = qs.filter(id__in=address_customers)

        if devices_list != "" and json_list(devices_list)[0]:
            user_ids = FCMDevice.objects.filter(
                Q(type__in=json_list(devices_list)[1]),
                active=True).values_list(
                'user__id', flat=True)
            qs = qs.filter(id__in=user_ids)

        if sort_by != "":
            if sort_by == "ATOZ":
                qs = qs.order_by('full_name')
            if sort_by == "ZTOA":
                qs = qs.order_by('-full_name')

            if sort_by == "new_first":
                qs = qs.order_by('-created_at')
            if sort_by == "old_first":
                qs = qs.order_by('created_at')

            if sort_by == "wishlist_low_to_high":
                qs = sorted(qs,
                            key=lambda t: t.get_wishlist_count(),
                            reverse=False)
            if sort_by == "wishlist_high_to_low":
                qs = sorted(qs,
                            key=lambda t: t.get_wishlist_count(),
                            reverse=True)

            if sort_by == "cart_low_to_high":
                qs = sorted(qs,
                            key=lambda t: t.get_cart_count(),
                            reverse=False)
            if sort_by == "cart_high_to_low":
                qs = sorted(qs,
                            key=lambda t: t.get_cart_count(),
                            reverse=True)

            if sort_by == "orders_low_to_high":
                qs = sorted(qs,
                            key=lambda t: t.get_order_count(),
                            reverse=False)
            if sort_by == "orders_high_to_low":
                qs = sorted(qs,
                            key=lambda t: t.get_order_count(),
                            reverse=True)

            if sort_by == "purchase_low_to_high":
                qs = sorted(qs,
                            key=lambda t: t.get_total_purchase_float(),
                            reverse=False)
            if sort_by == "purchase_high_to_low":
                qs = sorted(qs,
                            key=lambda t: t.get_total_purchase_float(),
                            reverse=True)
        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class ChangeCustomerStatus(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        customer_ids = request.data.get("customer_ids", "")
        customer_status = request.data.get("customer_status", "")

        if customer_ids != "" and json_list(customer_ids)[0]:
            if customer_status != "":
                Member.objects.filter(
                    pk__in=json_list(customer_ids)[1]
                ).update(status=customer_status)
                return Response({"detail": f"Successfully added customers to {customer_status}"})
            return Response({"error": "Please select customer status"},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"error": "Please select atleast one customer"},
                        status=status.HTTP_400_BAD_REQUEST)


class GuestList(ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = GuestListSerializer
    queryset = FCMDevice.objects.all()
    http_method_names = [u'get', u'post']

    def _allowed_methods(self):
        return [m.upper() for m in self.http_method_names if hasattr(self, m)]

    def search(self, qs, search_string):
        for qstring in search_string.split(" "):
            qs = qs.filter(
                Q(name__icontains=qstring)
            ).order_by('id').distinct()
        return qs

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        search_string = self.request.query_params.get("search_string", "")
        device_types = self.request.data.get("device_types", "")
        sort_by = self.request.query_params.get("sort_by", "")
        days = self.request.data.get("days", None)
        from_date = self.request.data.get("from_date", None)
        to_date = self.request.data.get("to_date", None)

        qs = FCMDevice.objects.filter(
            user__isnull=True).order_by('-date_created')

        if device_types != "" and json_list(device_types)[0]:
            qs = qs.filter(Q(type__in=json_list(device_types)[1]))

        if search_string != "":
            qs = self.search(qs, search_string)

        if days == 0 or days:
            date_selected = now() - timedelta(days=int(days))
            qs = qs.filter(date_created__date__gte=date_selected.date())

        if from_date and to_date:
            qs = qs.filter(
                date_created__date__gte=from_date,
                date_created__date__lte=to_date)

        if sort_by != "":
            if sort_by == "ATOZ":
                qs = qs.order_by('name')
            if sort_by == "ZTOA":
                qs = qs.order_by('-name')

            if sort_by == "newest_first":
                qs = qs.order_by('-date_created')
            if sort_by == "oldest_first":
                qs = qs.order_by('date_created')

        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class CustomerDetails(RetrieveAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = CustomerDetailSerializer

    def get_object(self):
        obj = get_object_or_404(Member, pk=self.kwargs.get("pk"))
        return obj

    def get_serializer_context(self):
        return {"user": self.request.user}


class CustomerEdit(UpdateAPIView):
    serializer_class = CustomerEditSerializer
    queryset = Member.objects.all()

    def update(self, request, *args, **kwargs):
        obj = get_object_or_404(Member, pk=kwargs.get("pk"))
        mem_serializer = CustomerEditSerializer(instance=obj, data=request.data)
        if mem_serializer.is_valid():
            mem = mem_serializer.save()
            return Response(
                CustomerDetailSerializer(mem).data
            )
        return Response(mem_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AddAddress(CreateAPIView):
    queryset = Address.objects.all()
    serializer_class = AddEditAddressSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            return Response(
                AddressSerializer(
                    instance, context={"user": request.user}
                ).data
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EditAddress(UpdateAPIView):
    serializer_class = AddEditAddressSerializer

    def get_object(self):
        return get_object_or_404(Address, pk=self.kwargs.get("pk"))

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = self.serializer_class(obj, data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            return Response(
                AddressSerializer(
                    instance, context={"user": request.user}
                ).data
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ShippingAreaList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = CityDetailsSerializer
    queryset = Member.objects.all()
    http_method_names = [u'get', u'post']

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        qs = City.objects.all()
        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class SettingsAdminList(ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = MemberSettingsSerializer
    queryset = Member.objects.all()

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        qs = Member.objects.filter(is_super_admin=True).order_by(
                Case(When(id=self.request.user.id, then=0), default=1)).distinct()
        return qs

    def post(self, request, *args, **kwargs):
        seller = get_object_or_404(Store, pk=2)
        return self.list(request, *args, **kwargs)


class SettingsSellerList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = MemberSettingsSerializer
    queryset = Member.objects.all()

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        if self.request.user.is_super_admin:
            qs = Member.objects.filter(is_seller=True).distinct()
        else:
            try:
                store = self.request.user.stores
                member_ids = SellerSubAdmins.objects.filter(
                    store=store).values_list(
                    'member_id', flat=True).distinct()
                member_ids_list = list(member_ids)
                member_ids_list.append(self.request.user.id)
                print("settings-seller-list")
                print(member_ids_list)
                qs = Member.objects.filter(pk__in=member_ids_list).distinct()
            except ObjectDoesNotExist:
                member_ids = self.request.user.seller_sub_admins.all().values_list(
                    'member_id', flat=True)
                member_ids_list = list(member_ids)
                if self.request.user.seller_sub_admins.exists():
                    sub_admin = self.request.user.seller_sub_admins.all().latest('id')
                    seller = sub_admin.store.member
                    member_ids_list.append(seller.id)
                member_ids_list.append(self.request.user.id)
                print("settings-seller-list-noneobject")
                print(member_ids_list)
                qs = Member.objects.filter(pk__in=member_ids_list).distinct()
        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class ChangePassword(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request):
        print("request")
        print(request.data)
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.reset()
            return Response({"detail": "Password has been reset"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AddAdmin(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request):
        serializer = AddSuperAdminSerializer(data=request.data)
        if serializer.is_valid():
            member = serializer.save()
            member.ecomm_member_permissions_for.all().update(
                created_by=request.user
            )
            password = "Becon" + "_" + str(member.pk) + "@123"
            member.set_password(password)
            member.save()
            if self.request.user.is_super_admin:
                try:
                    store = get_object_or_404(
                        Store, name=member.company)
                    SellerSubAdmins.objects.get_or_create(
                        store=store,
                        member=member,
                        designation=member.designation,
                        company=store.name
                    )
                    member.company = store.name
                    member.save()
                except ObjectDoesNotExist:
                    member.delete()
                    return Response(
                        {"error": "No store exists"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            elif self.request.user.is_seller:
                try:
                    store = self.request.user.stores
                    SellerSubAdmins.objects.get_or_create(
                        store=store,
                        member=member,
                        designation=member.designation,
                        company=store.name
                    )
                    member.company = store.name
                    member.save()
                except ObjectDoesNotExist:
                    member.delete()
                    return Response(
                        {"error": "No store exists"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            return Response(
                MemberSettingsSerializer(member).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EditAdmin(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def put(self, request, pk):
        obj = get_object_or_404(Member, pk=pk)
        serializer = EditSuperAdminSerializer(
            instance=obj, data=request.data)
        if serializer.is_valid():
            member = serializer.save()
            member.ecomm_member_permissions_for.all().update(
                created_by=request.user
            )
            member.seller_sub_admins.all().update(
                designation=member.designation,
                company=member.company
            )
            return Response(
                MemberSettingsSerializer(member).data
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeactivateUser(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request, pk):
        obj = get_object_or_404(Member, pk=pk)
        obj.status = "IN"
        obj.save()
        return Response({"detail": "User deactivated successfully"})


class ActivateUser(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request, pk):
        obj = get_object_or_404(Member, pk=pk)
        obj.status = "AC"
        obj.save()
        return Response({"detail": "User activated successfully"})


class RemoveUser(DestroyAPIView):
    permission_classes = [IsSuperAdminOrSeller]

    def destroy(self, request, *args, **kwargs):
        obj = get_object_or_404(Member, pk=kwargs.get("pk"))
        obj.delete()
        return Response({"detail": "User deleted successfully"})


class SetPassword(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request):
        password = request.data.get("password", None)
        if password and password != "":
            request.user.set_password(password)
            request.user.save()
        return Response({"detail": "Member password changed"})
