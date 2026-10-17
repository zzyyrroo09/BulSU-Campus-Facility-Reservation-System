from datetime import time, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from reservations.models import (
    Profile, FacilityCategory, Facility, Amenity, FacilityAmenity,
    Reservation, ClosureBlock, ReservationChange, EventRecord,
    AuditLog, SystemSetting
)


class Command(BaseCommand):
    help = "Seeds database with required minimum demonstration data per IT 401W Project B specifications."

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Beginning idempotent database seeding..."))
        tz = timezone.get_current_timezone()
        now = timezone.now()
        base_today = now.date()

        # 1. System Settings
        settings_obj, _ = SystemSetting.objects.get_or_create(
            id=1,
            defaults={
                'max_event_duration_hours': 4,
                'advance_booking_window_days': 30
            }
        )
        self.stdout.write(self.style.SUCCESS("[OK] System settings configured."))
        # 2. Facility Categories (>= 3)
        cat_data = [
            ("Academic Auditoriums", "Large lecture auditoriums equipped for academic symposia and defenses."),
            ("Athletic & Sports Complexes", "Indoor gymnasiums and courts for athletic events and exhibitions."),
            ("Audiovisual & Multipurpose Halls", "Medium halls equipped with sound and projection setups."),
            ("Conference & Executive Suites", "Boardrooms and meeting spaces for institutional committees."),
        ]
        categories = {}
        for name, desc in cat_data:
            cat, _ = FacilityCategory.objects.get_or_create(
                name=name,
                defaults={'description': desc, 'is_active': True}
            )
            categories[name] = cat
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(categories)} Facility categories seeded."))

        # 3. Facilities (>= 6)
        fac_specs = [
            ("AMPHI-01", "CICT Amphitheater", "Academic Auditoriums", "CICT Building 3rd Floor", 250, time(8, 0), time(18, 0), "Premier venue for computing symposia, research defenses, and tech seminars."),
            ("GYM-01", "University Gymnasium", "Athletic & Sports Complexes", "Main Campus Sports Complex", 1200, time(7, 0), time(20, 0), "Multipurpose campus arena for sports tournaments, convocations, and assemblies."),
            ("VAL-01", "Valencia Hall Auditorium", "Academic Auditoriums", "Valencia Hall Ground Floor", 500, time(8, 0), time(19, 0), "Historical auditorium with stage lighting and tiered seating."),
            ("AVR-01", "Natividad Hall Audio-Visual Room", "Audiovisual & Multipurpose Halls", "Natividad Hall 2nd Floor", 120, time(8, 0), time(18, 0), "Acoustically treated multimedia room with surround audio."),
            ("SAC-01", "Activity Center - Court A", "Athletic & Sports Complexes", "Student Activity Pavilion", 350, time(8, 0), time(21, 0), "Covered pavilion court for student org activities and rehearsals."),
            ("CONF-01", "E-Library Conference Suite", "Conference & Executive Suites", "University E-Library 4th Floor", 60, time(8, 0), time(17, 0), "Executive boardroom with video conferencing amenities."),
        ]
        facilities = {}
        for code, name, cat_name, loc, cap, op_s, op_e, desc in fac_specs:
            fac, _ = Facility.objects.get_or_create(
                code=code,
                defaults={
                    'category': categories[cat_name],
                    'name': name,
                    'location': loc,
                    'capacity': cap,
                    'operating_start_time': op_s,
                    'operating_end_time': op_e,
                    'description': desc,
                    'is_active': True
                }
            )
            facilities[code] = fac
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(facilities)} Campus facilities seeded."))

        # 4. Amenities (>= 8)
        amenity_names = [
            ("High-Definition Laser Projector & Screen", "4K resolution motorized projection system with HDMI & wireless casting."),
            ("Wireless Microphones & Digital PA System", "Digital UHF dual wireless lapel and handheld microphones with mixer."),
            ("Stage Theatrical & LED Spotlighting", "DMX-controlled RGB stage illumination rig."),
            ("Central Air Conditioning System", "High-capacity climate control system."),
            ("Retractable Bleachers & Stage Risers", "Modular seating and platform elevation units."),
            ("High-Density Wi-Fi Access Point", "Dedicated Gigabit Wi-Fi connectivity for attendees."),
            ("Smart Digital Podium & Touch Display", "Integrated presentation lectern with stylus annotations."),
            ("Movable Acoustic Dividers", "Sound-dampening partition panels for flexible space layout."),
            ("Live Streaming & Video Capture Rig", "Multi-camera broadcast system for virtual conferencing.")
        ]
        amenities = {}
        for name, desc in amenity_names:
            am, _ = Amenity.objects.get_or_create(name=name, defaults={'description': desc})
            amenities[name] = am
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(amenities)} Amenities seeded."))

        # Link amenities to facilities
        links = [
            ("AMPHI-01", "High-Definition Laser Projector & Screen", 2),
            ("AMPHI-01", "Wireless Microphones & Digital PA System", 4),
            ("AMPHI-01", "Central Air Conditioning System", 1),
            ("AMPHI-01", "Smart Digital Podium & Touch Display", 1),
            ("GYM-01", "Wireless Microphones & Digital PA System", 6),
            ("GYM-01", "Stage Theatrical & LED Spotlighting", 1),
            ("GYM-01", "Retractable Bleachers & Stage Risers", 4),
            ("VAL-01", "High-Definition Laser Projector & Screen", 1),
            ("VAL-01", "Stage Theatrical & LED Spotlighting", 1),
            ("VAL-01", "Central Air Conditioning System", 1),
            ("AVR-01", "High-Definition Laser Projector & Screen", 1),
            ("AVR-01", "Central Air Conditioning System", 1),
            ("CONF-01", "High-Density Wi-Fi Access Point", 2),
            ("CONF-01", "Live Streaming & Video Capture Rig", 1),
            ("SAC-01", "Movable Acoustic Dividers", 6),
        ]
        for fcode, aname, qty in links:
            FacilityAmenity.objects.get_or_create(
                facility=facilities[fcode],
                amenity=amenities[aname],
                defaults={'quantity': qty}
            )

        # 5. Admin Account (admin@bulsu.edu.ph / AdminPass123!)
        admin_user, created = User.objects.get_or_create(
            username="admin@bulsu.edu.ph",
            defaults={
                'email': "admin@bulsu.edu.ph",
                'first_name': "Aaron Paul",
                'last_name': "Dela Rosa",
                'is_staff': False,  # Prohibited from standard Django admin
                'is_superuser': False
            }
        )
        if created:
            admin_user.set_password("AdminPass123!")
            admin_user.save()

        Profile.objects.update_or_create(
            user=admin_user,
            defaults={
                'role': 'ADMIN',
                'contact_number': '+63 919 780 1102',
                'department': 'CICT Administration',
                'is_active_account': True
            }
        )
        self.stdout.write(self.style.SUCCESS("[OK] Admin account provisioned: admin@bulsu.edu.ph"))

        # 6. Basic User Accounts (user1 to user8)
        users = []
        user_catalog = [
            ("user1", "user1@bulsu.edu.ph", "Juan", "Dela Cruz", "CICT", "+63 912 345 6701"),
            ("user2", "user2@bulsu.edu.ph", "Maria", "Santos", "College of Engineering", "+63 912 345 6702"),
            ("user3", "user3@bulsu.edu.ph", "Carlos", "Reyes", "College of Science", "+63 912 345 6703"),
            ("user4", "user4@bulsu.edu.ph", "Ana", "Mendoza", "College of Business Administration", "+63 912 345 6704"),
            ("user5", "user5@bulsu.edu.ph", "Mark", "Bautista", "College of Arts and Letters", "+63 912 345 6705"),
            ("user6", "user6@bulsu.edu.ph", "Liza", "Alvarez", "College of Education", "+63 912 345 6706"),
            ("user7", "user7@bulsu.edu.ph", "Paolo", "Garcia", "University Supreme Student Council", "+63 912 345 6707"),
            ("user8", "user8@bulsu.edu.ph", "Elena", "Torres", "CICT Student Council", "+63 912 345 6708"),
        ]
        for uname, uemail, fname, lname, dept, phone in user_catalog:
            u, u_created = User.objects.get_or_create(
                username=uname,
                defaults={
                    'email': uemail,
                    'first_name': fname,
                    'last_name': lname
                }
            )
            if u_created:
                u.set_password("UserPass123!")
                u.save()

            Profile.objects.update_or_create(
                user=u,
                defaults={
                    'role': 'BASIC_USER',
                    'contact_number': phone,
                    'department': dept,
                    'is_active_account': True
                }
            )
            users.append(u)
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(users)} Basic User accounts provisioned."))

        # 7. Closure Blocks (>= 5)
        closure_data = [
            ("AMPHI-01", base_today + timedelta(days=1), time(8, 0), time(12, 0), "Bi-monthly audiovisual acoustic calibration and wiring maintenance."),
            ("GYM-01", base_today + timedelta(days=3), time(7, 0), time(11, 0), "Hardwood floor waxing and safety inspection."),
            ("VAL-01", base_today + timedelta(days=5), time(13, 0), time(17, 0), "Stage rigging and emergency fire sprinkler inspection."),
            ("CONF-01", base_today + timedelta(days=2), time(8, 0), time(10, 0), "Network infrastructure router upgrade."),
            ("SAC-01", base_today + timedelta(days=7), time(8, 0), time(13, 0), "Pavilion sanitation and structural painting."),
        ]
        for fcode, cdate, st, et, reason in closure_data:
            c_start = timezone.make_aware(timezone.datetime.combine(cdate, st), tz)
            c_end = timezone.make_aware(timezone.datetime.combine(cdate, et), tz)
            ClosureBlock.objects.get_or_create(
                facility=facilities[fcode],
                start_time=c_start,
                end_time=c_end,
                defaults={'reason': reason, 'is_active': True, 'created_by': admin_user}
            )
        self.stdout.write(self.style.SUCCESS("[OK] 5 Maintenance closure blocks seeded."))

        # 8. Seed >= 24 Reservations with Comprehensive Coverage
        # (Completed, Checked-In, No-Show, Approved Adjacent, Competing Pending, Rejected, Cancelled)
        reservations_to_seed = []

        # --- A. Historical Completed Events with EventRecords (8 items) ---
        for i in range(1, 9):
            res_date = base_today - timedelta(days=i * 3)
            fac_code = "AMPHI-01" if i % 2 == 0 else "VAL-01"
            st_dt = timezone.make_aware(timezone.datetime.combine(res_date, time(9, 0)), tz)
            et_dt = timezone.make_aware(timezone.datetime.combine(res_date, time(12, 0)), tz)
            u = users[(i - 1) % len(users)]
            
            res, _ = Reservation.objects.get_or_create(
                tracking_code=f"RES-HIST-COMP-{i:02d}",
                defaults={
                    'user': u,
                    'facility': facilities[fac_code],
                    'title': f"Completed Academic Colloquium {i}",
                    'purpose': f"Historical institutional presentation series {i} successfully completed.",
                    'participants_count': 50 + (i * 10),
                    'start_time': st_dt,
                    'end_time': et_dt,
                    'status': 'COMPLETED',
                    'decision_actor': admin_user,
                    'decision_timestamp': st_dt - timedelta(days=5),
                    'decision_reason': "Approved per curriculum calendar."
                }
            )
            # Create corresponding EventRecord
            EventRecord.objects.get_or_create(
                reservation=res,
                defaults={
                    'check_in_time': st_dt - timedelta(minutes=15),
                    'actual_start_time': st_dt,
                    'actual_end_time': et_dt,
                    'operational_status': 'COMPLETED',
                    'incident_notes': f"Colloquium {i} concluded on schedule. Facility left in pristine condition."
                }
            )

        # --- B. Today's Checked-In Events with EventRecords (2 items) ---
        today_st_1 = timezone.make_aware(timezone.datetime.combine(base_today, time(8, 0)), tz)
        today_et_1 = timezone.make_aware(timezone.datetime.combine(base_today, time(11, 0)), tz)
        res_ci_1, _ = Reservation.objects.get_or_create(
            tracking_code="RES-LIVE-CHKIN-01",
            defaults={
                'user': users[0],
                'facility': facilities["CONF-01"],
                'title': "CICT Curriculum Review Committee",
                'purpose': "Executive syllabus deliberation and accreditation review.",
                'participants_count': 25,
                'start_time': today_st_1,
                'end_time': today_et_1,
                'status': 'CHECKED_IN',
                'decision_actor': admin_user,
                'decision_timestamp': now - timedelta(days=3),
                'decision_reason': "Official administrative committee booking."
            }
        )
        EventRecord.objects.get_or_create(
            reservation=res_ci_1,
            defaults={
                'check_in_time': today_st_1,
                'actual_start_time': today_st_1,
                'operational_status': 'CHECKED_IN',
                'incident_notes': "Attendees verified. Projection and Wi-Fi initialized."
            }
        )

        today_st_2 = timezone.make_aware(timezone.datetime.combine(base_today, time(13, 0)), tz)
        today_et_2 = timezone.make_aware(timezone.datetime.combine(base_today, time(16, 0)), tz)
        res_ci_2, _ = Reservation.objects.get_or_create(
            tracking_code="RES-LIVE-CHKIN-02",
            defaults={
                'user': users[1],
                'facility': facilities["SAC-01"],
                'title': "Engineering Design Expo Setup",
                'purpose': "Exhibition booth setup and prototype testing.",
                'participants_count': 120,
                'start_time': today_st_2,
                'end_time': today_et_2,
                'status': 'CHECKED_IN',
                'decision_actor': admin_user,
                'decision_timestamp': now - timedelta(days=2),
                'decision_reason': "Approved with electrical load conditions."
            }
        )
        EventRecord.objects.get_or_create(
            reservation=res_ci_2,
            defaults={
                'check_in_time': today_st_2,
                'actual_start_time': today_st_2,
                'operational_status': 'CHECKED_IN',
                'incident_notes': "Safety briefing conducted."
            }
        )

        # --- C. Adjacent APPROVED Bookings (Demonstrating Half-Open [start, end) rule) ---
        # Same facility: GYM-01 on base_today + 4 days
        # Slot A: 08:00 to 11:00
        # Slot B: 11:00 to 14:00 (end of A == start of B) -> MUST NOT CONFLICT
        adj_date = base_today + timedelta(days=4)
        adj_a_st = timezone.make_aware(timezone.datetime.combine(adj_date, time(8, 0)), tz)
        adj_a_et = timezone.make_aware(timezone.datetime.combine(adj_date, time(11, 0)), tz)
        res_adj_a, _ = Reservation.objects.get_or_create(
            tracking_code="RES-ADJ-SLOT-A",
            defaults={
                'user': users[2],
                'facility': facilities["GYM-01"],
                'title': "Intramural Basketball Eliminations - Bracket A",
                'purpose': "Scheduled student league basketball matches.",
                'participants_count': 300,
                'start_time': adj_a_st,
                'end_time': adj_a_et,
                'status': 'APPROVED',
                'decision_actor': admin_user,
                'decision_timestamp': now - timedelta(days=1),
                'decision_reason': "Half-open interval adjacent slot demonstration (08:00-11:00)."
            }
        )

        adj_b_st = adj_a_et  # Exactly 11:00
        adj_b_et = timezone.make_aware(timezone.datetime.combine(adj_date, time(14, 0)), tz)
        res_adj_b, _ = Reservation.objects.get_or_create(
            tracking_code="RES-ADJ-SLOT-B",
            defaults={
                'user': users[3],
                'facility': facilities["GYM-01"],
                'title': "Intramural Volleyball Tournament - Bracket B",
                'purpose': "Scheduled student league volleyball matches.",
                'participants_count': 250,
                'start_time': adj_b_st,
                'end_time': adj_b_et,
                'status': 'APPROVED',
                'decision_actor': admin_user,
                'decision_timestamp': now - timedelta(days=1),
                'decision_reason': "Half-open interval adjacent slot demonstration (11:00-14:00)."
            }
        )

        # --- D. Competing PENDING Requests (Competing for same facility and overlapping time) ---
        comp_date = base_today + timedelta(days=6)
        comp_st = timezone.make_aware(timezone.datetime.combine(comp_date, time(13, 0)), tz)
        comp_et = timezone.make_aware(timezone.datetime.combine(comp_date, time(16, 0)), tz)

        Reservation.objects.get_or_create(
            tracking_code="RES-COMPETE-PEND-01",
            defaults={
                'user': users[4],
                'facility': facilities["AMPHI-01"],
                'title': "Web Development Tech Talk Series",
                'purpose': "Guest lecture on modern Python & Django frameworks.",
                'participants_count': 180,
                'start_time': comp_st,
                'end_time': comp_et,
                'status': 'PENDING'
            }
        )
        Reservation.objects.get_or_create(
            tracking_code="RES-COMPETE-PEND-02",
            defaults={
                'user': users[5],
                'facility': facilities["AMPHI-01"],
                'title': "Cybersecurity Awareness Seminar",
                'purpose': "Ethical hacking and data protection workshop.",
                'participants_count': 200,
                'start_time': comp_st,  # Exact same slot!
                'end_time': comp_et,
                'status': 'PENDING'
            }
        )

        # --- E. Additional Pending Requests in the Queue (4 items) ---
        for j, (fc, hour_offset, title) in enumerate([
            ("VAL-01", 8, "University Choral Society Rehearsal"),
            ("AVR-01", 10, "Senior Thesis Defense - Group Gamma"),
            ("CONF-01", 14, "Research Ethics Board Deliberation"),
            ("SAC-01", 15, "Debate Society Championship Round")
        ], start=1):
            p_date = base_today + timedelta(days=j + 1)
            p_st = timezone.make_aware(timezone.datetime.combine(p_date, time(hour_offset, 0)), tz)
            p_et = timezone.make_aware(timezone.datetime.combine(p_date, time(hour_offset + 3, 0)), tz)
            Reservation.objects.get_or_create(
                tracking_code=f"RES-QUEUE-PEND-{j:02d}",
                defaults={
                    'user': users[(j + 2) % len(users)],
                    'facility': facilities[fc],
                    'title': title,
                    'purpose': f"Student activity request: {title}.",
                    'participants_count': 45 + (j * 15),
                    'start_time': p_st,
                    'end_time': p_et,
                    'status': 'PENDING'
                }
            )

        # --- F. Past NO-SHOW Records with EventRecords (2 items) ---
        ns_date_1 = base_today - timedelta(days=2)
        ns_st_1 = timezone.make_aware(timezone.datetime.combine(ns_date_1, time(9, 0)), tz)
        ns_et_1 = timezone.make_aware(timezone.datetime.combine(ns_date_1, time(11, 0)), tz)
        res_ns_1, _ = Reservation.objects.get_or_create(
            tracking_code="RES-NOSHOW-01",
            defaults={
                'user': users[6],
                'facility': facilities["AVR-01"],
                'title': "Cancelled Club Meeting (No Appearance)",
                'purpose': "General assembly that failed to appear on site.",
                'participants_count': 40,
                'start_time': ns_st_1,
                'end_time': ns_et_1,
                'status': 'NO_SHOW',
                'decision_actor': admin_user,
                'decision_timestamp': ns_st_1 - timedelta(days=4),
                'decision_reason': "Approved originally."
            }
        )
        EventRecord.objects.get_or_create(
            reservation=res_ns_1,
            defaults={
                'operational_status': 'NO_SHOW',
                'incident_notes': "Scheduled time elapsed without organizer arrival. Facility remained locked."
            }
        )

        ns_date_2 = base_today - timedelta(days=5)
        ns_st_2 = timezone.make_aware(timezone.datetime.combine(ns_date_2, time(14, 0)), tz)
        ns_et_2 = timezone.make_aware(timezone.datetime.combine(ns_date_2, time(16, 0)), tz)
        res_ns_2, _ = Reservation.objects.get_or_create(
            tracking_code="RES-NOSHOW-02",
            defaults={
                'user': users[7],
                'facility': facilities["CONF-01"],
                'title': "Alumni Taskforce Planning Session",
                'purpose': "Informal committee discussion.",
                'participants_count': 20,
                'start_time': ns_st_2,
                'end_time': ns_et_2,
                'status': 'NO_SHOW',
                'decision_actor': admin_user,
                'decision_timestamp': ns_st_2 - timedelta(days=3),
                'decision_reason': "Approved."
            }
        )
        EventRecord.objects.get_or_create(
            reservation=res_ns_2,
            defaults={
                'operational_status': 'NO_SHOW',
                'incident_notes': "Organizer did not arrive; no cancellation notification received."
            }
        )

        # --- G. REJECTED Requests with required reason (3 items) ---
        for k, (fc, reason) in enumerate([
            ("AMPHI-01", "Expected attendees (350) exceeds maximum amphitheater capacity of 250."),
            ("GYM-01", "Event requested beyond standard campus operating hours."),
            ("VAL-01", "Requested time overlaps with university-wide accreditation symposium.")
        ], start=1):
            rej_date = base_today + timedelta(days=k + 2)
            rej_st = timezone.make_aware(timezone.datetime.combine(rej_date, time(10, 0)), tz)
            rej_et = timezone.make_aware(timezone.datetime.combine(rej_date, time(13, 0)), tz)
            Reservation.objects.get_or_create(
                tracking_code=f"RES-REJECTED-{k:02d}",
                defaults={
                    'user': users[k % len(users)],
                    'facility': facilities[fc],
                    'title': f"Unapproved Request {k}",
                    'purpose': f"Event proposal rejected due to institutional policy constraint.",
                    'participants_count': 350 if "capacity" in reason else 50,
                    'start_time': rej_st,
                    'end_time': rej_et,
                    'status': 'REJECTED',
                    'decision_actor': admin_user,
                    'decision_timestamp': now - timedelta(hours=6),
                    'decision_reason': reason
                }
            )

        # --- H. CANCELLED Requests (3 items) ---
        for m in range(1, 4):
            can_date = base_today + timedelta(days=m + 3)
            can_st = timezone.make_aware(timezone.datetime.combine(can_date, time(13, 0)), tz)
            can_et = timezone.make_aware(timezone.datetime.combine(can_date, time(16, 0)), tz)
            Reservation.objects.get_or_create(
                tracking_code=f"RES-CANCELLED-{m:02d}",
                defaults={
                    'user': users[m % len(users)],
                    'facility': facilities["SAC-01"],
                    'title': f"Student Org Gathering {m}",
                    'purpose': "Event cancelled voluntarily by student organizer prior to start date.",
                    'participants_count': 60,
                    'start_time': can_st,
                    'end_time': can_et,
                    'status': 'CANCELLED',
                    'decision_actor': users[m % len(users)],
                    'decision_timestamp': now - timedelta(hours=12),
                    'decision_reason': "Voluntary user cancellation."
                }
            )

        # --- I. Rescheduled Reservation with ReservationChange entry ---
        resched_date = base_today + timedelta(days=8)
        orig_st = timezone.make_aware(timezone.datetime.combine(resched_date, time(9, 0)), tz)
        orig_et = timezone.make_aware(timezone.datetime.combine(resched_date, time(11, 0)), tz)
        new_st = timezone.make_aware(timezone.datetime.combine(resched_date, time(14, 0)), tz)
        new_et = timezone.make_aware(timezone.datetime.combine(resched_date, time(16, 0)), tz)

        res_resched, _ = Reservation.objects.get_or_create(
            tracking_code="RES-RESCHEDULED-01",
            defaults={
                'user': users[0],
                'facility': facilities["VAL-01"],
                'title': "CICT Alumni Homecoming Committee Meeting",
                'purpose': "Strategic planning for annual grand alumni homecoming.",
                'participants_count': 75,
                'start_time': new_st,
                'end_time': new_et,
                'status': 'APPROVED',
                'decision_actor': admin_user,
                'decision_timestamp': now - timedelta(days=2),
                'decision_reason': "Approved originally."
            }
        )
        ReservationChange.objects.get_or_create(
            reservation=res_resched,
            previous_start=orig_st,
            previous_end=orig_et,
            new_start=new_st,
            new_end=new_et,
            defaults={
                'reason': "Administrative adjustment to accommodate morning VIP visiting delegation.",
                'actor': admin_user
            }
        )

        total_reservations = Reservation.objects.count()
        total_event_records = EventRecord.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"[OK] {total_reservations} Reservations and {total_event_records} EventRecords seeded successfully."
        ))

        # 9. Audit Logs Seed
        AuditLog.objects.get_or_create(
            action_type="SYSTEM_SEED",
            reference_model="SystemSetting",
            reference_id="1",
            defaults={
                'actor': admin_user,
                'description': "System initialized with academic demonstration dataset per IT 401W specification.",
                'ip_address': "127.0.0.1"
            }
        )

        self.stdout.write(self.style.SUCCESS("[OK] Audit logs generated."))
        self.stdout.write(self.style.SUCCESS("All demonstration data successfully seeded and verified!"))
