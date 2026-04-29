import requests as http_requests
from requests.exceptions import ConnectionError, Timeout
from celery import shared_task
from django.conf import settings

from errors.models import SystemErrorLog
from .models import ASDReport, ADHDReport


@shared_task(bind=True, max_retries=3)
def process_asd_videos_task(self, report_id):
    report = ASDReport.objects.get(id=report_id)

    try:
        with open(report.motion_video.path, "rb") as motion_file, open(report.emotion_video.path, "rb") as emotion_file:
            ai_response = http_requests.post(
                f"{settings.AI_SERVER_URL}/predict/observational",
                files={
                    "motion_video": motion_file,
                    "emotion_video": emotion_file,
                },
                data={"questionnaire": report.questionnaire_answers},
                timeout=(60, 1000),
            )

        ai_response.raise_for_status()
        ai_data = ai_response.json()

        report.videos_ai_response = ai_data
        report.risk_level = ai_data.get("risk_level", "low")
        report.recommendation = ai_data.get("recommendation", "")
        report.save(update_fields=[
            "videos_ai_response",
            "risk_level",
            "recommendation",
            "updated_at",
        ])

        return {
            "report_id": str(report.id),
            "type": "asd_videos",
            "status": "completed",
        }

    except (ConnectionError, Timeout) as e:
        SystemErrorLog.objects.create(
            error_type="AI_SERVER_CONNECTION_ERROR",
            message=str(e),
        )

        raise self.retry(exc=e, countdown=60)

    except http_requests.RequestException as e:
        SystemErrorLog.objects.create(
            error_type="AI_SERVER_REQUEST_ERROR",
            message=str(e),
        )
        raise

    except Exception as e:
        SystemErrorLog.objects.create(
            error_type="AI_SERVER_ERROR",
            message=str(e),
        )
        raise


@shared_task(bind=True, max_retries=3)
def process_asd_physiology_task(self, report_id):
    report = ASDReport.objects.get(id=report_id)

    try:
        with open(report.physiology_file.path, "rb") as physiology_file:
            ai_response = http_requests.post(
                f"{settings.AI_SERVER_URL}/predict/physiology",
                files={"physiology_file": physiology_file},
                timeout=(60, 600),
            )

        ai_response.raise_for_status()
        ai_data = ai_response.json()

        report.physiology_ai_response = ai_data
        report.save(update_fields=[
            "physiology_ai_response",
            "updated_at",
        ])

        return {
            "report_id": str(report.id),
            "type": "asd_physiology",
            "status": "completed",
        }

    except (ConnectionError, Timeout) as e:
        SystemErrorLog.objects.create(
            error_type="AI_SERVER_CONNECTION_ERROR",
            message=str(e),
        )

        raise self.retry(exc=e, countdown=60)

    except http_requests.RequestException as e:
        SystemErrorLog.objects.create(
            error_type="AI_SERVER_REQUEST_ERROR",
            message=str(e),
        )
        raise

    except Exception as e:
        SystemErrorLog.objects.create(
            error_type="AI_SERVER_ERROR",
            message=str(e),
        )
        raise


@shared_task(bind=True, max_retries=3)
def process_adhd_task(self, report_id):
    report = ADHDReport.objects.get(id=report_id)

    try:
        with open(report.eeg_file.path, "rb") as eeg_file:
            ai_response = http_requests.post(
                f"{settings.AI_SERVER_URL}/predict/adhd",
                files={"eeg_file": eeg_file},
                timeout=(60, 600),
            )

        ai_response.raise_for_status()
        ai_data = ai_response.json()

        report.ai_full_response = ai_data
        report.risk_level = ai_data.get("risk_level", "low")
        report.recommendation = ai_data.get("recommendation", "")
        report.save(update_fields=[
            "ai_full_response",
            "risk_level",
            "recommendation",
            "updated_at",
        ])

        return {
            "report_id": str(report.id),
            "type": "adhd",
            "status": "completed",
        }

    except (ConnectionError, Timeout) as e:
        SystemErrorLog.objects.create(
            error_type="AI_SERVER_CONNECTION_ERROR",
            message=str(e),
        )

        raise self.retry(exc=e, countdown=60)

    except http_requests.RequestException as e:
        SystemErrorLog.objects.create(
            error_type="AI_SERVER_REQUEST_ERROR",
            message=str(e),
        )
        raise

    except Exception as e:
        SystemErrorLog.objects.create(
            error_type="AI_SERVER_ERROR",
            message=str(e),
        )
        raise
