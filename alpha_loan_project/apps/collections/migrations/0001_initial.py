"""Initial collections domain schema."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CollectionCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("account_id", models.CharField(db_index=True, max_length=100, unique=True)),
                ("partner_row_id", models.CharField(blank=True, db_index=True, max_length=100, null=True, unique=True)),
                ("borrower_name", models.CharField(max_length=255)),
                ("borrower_email", models.EmailField(blank=True, max_length=254, null=True)),
                ("borrower_phone", models.CharField(db_index=True, max_length=20)),
                ("principal_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("total_due", models.DecimalField(decimal_places=2, max_digits=12)),
                ("amount_paid", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                (
                    "current_workflow_step",
                    models.CharField(
                        choices=[
                            ("STEP_1", "Immediate Payment"),
                            ("STEP_2", "Double Payment"),
                            ("STEP_3", "Add NSF to Next Payment"),
                            ("STEP_4", "Split NSF"),
                            ("FINAL_PRESSURE", "Final Pressure"),
                        ],
                        db_index=True,
                        default="STEP_1",
                        max_length=20,
                    ),
                ),
                ("workflow_step_started_at", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ACTIVE", "Active"),
                            ("RESOLVED", "Resolved"),
                            ("LOST", "Lost"),
                            ("SUSPENDED", "Suspended"),
                        ],
                        db_index=True,
                        default="ACTIVE",
                        max_length=20,
                    ),
                ),
                (
                    "automation_status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("PAUSED", "Paused"), ("STOPPED", "Stopped")],
                        db_index=True,
                        default="ACTIVE",
                        max_length=20,
                    ),
                ),
                ("delinquent_date", models.DateField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_contact_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("next_followup_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("next_action_time", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("does_not_call", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
            ],
            options={
                "db_table": "collections_case",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PaymentCommitment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("committed_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("amount_paid", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("CONFIRMED", "Confirmed"),
                            ("PARTIAL_PAID", "Partially Paid"),
                            ("FULFILLED", "Fulfilled"),
                            ("BROKEN", "Broken"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("promised_date", models.DateField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("payment_method", models.CharField(blank=True, help_text="ACH, Check, Credit Card, etc.", max_length=50)),
                ("commitment_source", models.CharField(blank=True, help_text="SMS, Voice, Email, etc.", max_length=50)),
                ("notes", models.TextField(blank=True)),
                (
                    "collection_case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commitments",
                        to="collections.collectioncase",
                    ),
                ),
            ],
            options={
                "db_table": "collections_payment_commitment",
                "ordering": ["-promised_date"],
            },
        ),
        migrations.CreateModel(
            name="InteractionLedger",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "channel",
                    models.CharField(
                        choices=[("SMS", "SMS/Text"), ("EMAIL", "Email"), ("VOICE", "Voice Call"), ("MANUAL", "Manual Contact")],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                (
                    "interaction_type",
                    models.CharField(choices=[("OUTBOUND", "Outbound"), ("INBOUND", "Inbound")], db_index=True, max_length=20),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("SENT", "Sent"),
                            ("DELIVERED", "Delivered"),
                            ("READ", "Read"),
                            ("REPLIED", "Replied"),
                            ("FAILED", "Failed"),
                            ("BOUNCED", "Bounced"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("subject", models.CharField(blank=True, max_length=255)),
                ("message_content", models.TextField()),
                ("external_id", models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("replied_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("ai_intent_detected", models.CharField(blank=True, max_length=100, null=True)),
                ("ai_sentiment_score", models.FloatField(blank=True, null=True)),
                ("ai_processed_at", models.DateTimeField(blank=True, null=True)),
                ("reply_message", models.TextField(blank=True, null=True)),
                ("ai_generated", models.BooleanField(default=False)),
                (
                    "collection_case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interactions",
                        to="collections.collectioncase",
                    ),
                ),
            ],
            options={
                "db_table": "collections_interaction_ledger",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="TransactionLedger",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "transaction_type",
                    models.CharField(
                        choices=[
                            ("PAYMENT", "Payment Received"),
                            ("ADJUSTMENT", "Adjustment"),
                            ("FEE", "Fee Applied"),
                            ("NSF", "Non-Sufficient Funds"),
                            ("REVERSAL", "Reversal"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("description", models.TextField(blank=True)),
                ("external_reference", models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ("posted_date", models.DateField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.CharField(blank=True, max_length=255)),
                (
                    "collection_case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transactions",
                        to="collections.collectioncase",
                    ),
                ),
            ],
            options={
                "db_table": "collections_transaction_ledger",
                "ordering": ["-posted_date", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="collectioncase",
            index=models.Index(fields=["status", "current_workflow_step"], name="collections_status_99f4ea_idx"),
        ),
        migrations.AddIndex(
            model_name="collectioncase",
            index=models.Index(fields=["automation_status", "next_action_time"], name="collections_automat_4ec01d_idx"),
        ),
        migrations.AddIndex(
            model_name="collectioncase",
            index=models.Index(fields=["borrower_phone"], name="collections_borrower_30ef76_idx"),
        ),
        migrations.AddIndex(
            model_name="collectioncase",
            index=models.Index(fields=["next_followup_at"], name="collections_next_fo_667f30_idx"),
        ),
        migrations.AddIndex(
            model_name="interactionledger",
            index=models.Index(fields=["collection_case", "created_at"], name="collections_collecti_46f693_idx"),
        ),
        migrations.AddIndex(
            model_name="interactionledger",
            index=models.Index(fields=["channel", "status"], name="collections_channel_f0f55d_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentcommitment",
            index=models.Index(fields=["collection_case", "promised_date"], name="collections_collecti_7e6f9f_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentcommitment",
            index=models.Index(fields=["status"], name="collections_status_9f0638_idx"),
        ),
        migrations.AddIndex(
            model_name="transactionledger",
            index=models.Index(fields=["collection_case", "posted_date"], name="collections_collecti_542a89_idx"),
        ),
    ]

