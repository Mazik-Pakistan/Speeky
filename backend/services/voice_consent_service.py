from datetime import datetime, timezone
from typing import Dict

from fastapi import Depends

from lib.kv_store import store
from middlewares.auth_middleware import require_auth
from schemas.voice_consent_schemas import (
    VOICE_CONSENT_POLICY_VERSION,
    VoiceConsentPreferenceSchema,
    VoiceConsentUpdateSchema,
    VoiceSampleDeletionSchema,
)
from utils.app_error import AppError

NAMESPACE = "voice_data_consent"
RAW_AUDIO_RETENTION_DAYS = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_record(user_id: str) -> Dict:
    return {
        "user_id": user_id,
        "granted": False,
        "policyVersion": VOICE_CONSENT_POLICY_VERSION,
        "retentionDays": RAW_AUDIO_RETENTION_DAYS,
        "rawAudioRetained": False,
        "consentedAt": None,
        "withdrawnAt": None,
        "rawAudioDeletedAt": None,
        "region": None,
    }


async def _get_record(user_id: str) -> Dict:
    return await store.get(NAMESPACE, user_id) or _default_record(user_id)


async def _save_record(user_id: str, record: Dict) -> Dict:
    existing = await store.get(NAMESPACE, user_id)
    if existing:
        return await store.update(NAMESPACE, user_id, record)
    return await store.create(NAMESPACE, user_id, record)


def _to_schema(record: Dict) -> VoiceConsentPreferenceSchema:
    return VoiceConsentPreferenceSchema(
        granted=bool(record.get("granted")),
        policy_version=record.get("policyVersion", VOICE_CONSENT_POLICY_VERSION),
        retention_days=int(record.get("retentionDays", RAW_AUDIO_RETENTION_DAYS)),
        raw_audio_retained=bool(record.get("rawAudioRetained", False)),
        consented_at=record.get("consentedAt"),
        withdrawn_at=record.get("withdrawnAt"),
        raw_audio_deleted_at=record.get("rawAudioDeletedAt"),
        region=record.get("region"),
    )


async def get_voice_consent(user_id: str = Depends(require_auth)):
    return _to_schema(await _get_record(user_id))


async def update_voice_consent(
    payload: VoiceConsentUpdateSchema,
    user_id: str = Depends(require_auth),
):
    record = await _get_record(user_id)

    record["policyVersion"] = payload.policy_version
    record["region"] = payload.region or record.get("region")

    if payload.granted:
        record["granted"] = True
        record["consentedAt"] = _now()
        record["withdrawnAt"] = None
    else:
        record["granted"] = False
        record["withdrawnAt"] = _now()
        record["rawAudioDeletedAt"] = _now()

    await _save_record(user_id, record)
    return _to_schema(record)


async def ensure_voice_consent(user_id: str) -> None:
    record = await _get_record(user_id)
    if not record.get("granted"):
        raise AppError(
            "Voice data consent is required before starting Accent Assessment.",
            403,
        )


async def delete_voice_samples(user_id: str = Depends(require_auth)):
    record = await _get_record(user_id)
    record["rawAudioDeletedAt"] = _now()
    record["rawAudioRetained"] = False
    await _save_record(user_id, record)

    return VoiceSampleDeletionSchema(
        deleted_audio_samples=0,
        raw_audio_retained=False,
        message="No raw voice recordings are currently retained. Derived accent profile scores were kept.",
    )