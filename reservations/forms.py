from datetime import datetime
from django import forms
from django.contrib.auth.models import User
from django.utils import timezone
from .models import (
    Profile, FacilityCategory, Facility, Amenity,
    FacilityAmenity, Reservation, ClosureBlock, SystemSetting
)
from .services import validate_booking_rules


class UserRegistrationForm(forms.Form):
    """
    Public registration form for Campus Users.
    STRICT COMPLIANCE: Hardcoded to create only BASIC_USER role.
    Admin self-promotion is architecturally prohibited.
    """
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., jdelacruz'})
    )
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Juan'})
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dela Cruz'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'jdelacruz@bulsu.edu.ph'})
    )
    contact_number = forms.CharField(
        max_length=30, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+63 912 345 6789'})
    )
    department = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., CICT, COE, CBA'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'At least 6 characters'}),
        min_length=6
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Repeat your password'}),
        label="Confirm Password"
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Passwords do not match.")
        return cleaned_data

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name']
        )
        # Force BASIC_USER role
        Profile.objects.create(
            user=user,
            role='BASIC_USER',
            contact_number=data.get('contact_number', ''),
            department=data.get('department', ''),
            is_active_account=True
        )
        return user


class UserProfileForm(forms.ModelForm):
    """
    Basic user profile update form.
    Role and activation fields are strictly omitted.
    """
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    contact_number = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    department = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Profile
        fields = ['contact_number', 'department']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            if commit:
                self.user.save()
        if commit:
            profile.save()
        return profile


class FacilityCategoryForm(forms.ModelForm):
    class Meta:
        model = FacilityCategory
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class FacilityForm(forms.ModelForm):
    class Meta:
        model = Facility
        fields = [
            'code', 'category', 'name', 'location', 'capacity',
            'operating_start_time', 'operating_end_time', 'description', 'is_active'
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. GYM-01'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'operating_start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'operating_end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AmenityForm(forms.ModelForm):
    class Meta:
        model = Amenity
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class FacilityAmenityForm(forms.ModelForm):
    class Meta:
        model = FacilityAmenity
        fields = ['amenity', 'quantity']
        widgets = {
            'amenity': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


class ReservationRequestForm(forms.ModelForm):
    """
    Basic user reservation booking form with comprehensive domain validation.
    """
    booking_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        help_text="Events must occur within operating hours on this date."
    )
    start_time_input = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        label="Start Time"
    )
    end_time_input = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        label="End Time"
    )

    class Meta:
        model = Reservation
        fields = ['facility', 'title', 'purpose', 'participants_count']
        widgets = {
            'facility': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Title'}),
            'purpose': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Detailed objective of the event...'}),
            'participants_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only active facilities can be selected
        self.fields['facility'].queryset = Facility.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        facility = cleaned_data.get('facility')
        booking_date = cleaned_data.get('booking_date')
        start_time_val = cleaned_data.get('start_time_input')
        end_time_val = cleaned_data.get('end_time_input')
        participants_count = cleaned_data.get('participants_count')

        if facility and booking_date and start_time_val and end_time_val and participants_count:
            # Combine into timezone-aware datetimes (Asia/Manila)
            start_naive = datetime.combine(booking_date, start_time_val)
            end_naive = datetime.combine(booking_date, end_time_val)

            tz = timezone.get_current_timezone()
            start_dt = timezone.make_aware(start_naive, tz)
            end_dt = timezone.make_aware(end_naive, tz)

            try:
                validate_booking_rules(
                    facility=facility,
                    start_time=start_dt,
                    end_time=end_dt,
                    participants_count=participants_count,
                    enforce_future=True
                )
            except forms.ValidationError as e:
                self.add_error(None, e)

            cleaned_data['computed_start_time'] = start_dt
            cleaned_data['computed_end_time'] = end_dt

        return cleaned_data


class AdminRescheduleForm(forms.Form):
    """
    Form for Administrator to reschedule an approved booking.
    """
    booking_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="New Date"
    )
    start_time_input = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        label="New Start Time"
    )
    end_time_input = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        label="New End Time"
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Required reason for rescheduling...'}),
        required=True,
        label="Rescheduling Justification"
    )


class ClosureBlockForm(forms.ModelForm):
    """
    Facility maintenance / closure form with date and time pickers.
    """
    closure_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Date"
    )
    start_time_input = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        label="Start Time"
    )
    end_time_input = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        label="End Time"
    )

    class Meta:
        model = ClosureBlock
        fields = ['facility', 'reason']
        widgets = {
            'facility': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Electrical maintenance, Floor sanitation'}),
        }


class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = ['max_event_duration_hours', 'advance_booking_window_days']
        widgets = {
            'max_event_duration_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 24}),
            'advance_booking_window_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 365}),
        }
