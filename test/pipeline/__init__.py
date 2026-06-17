"""
pipeline — YouTube 版权音乐有声书流水线核心包

# 方案 B 用法（推荐 — 类型安全，适合本地开发）
from pipeline.config import RuntimeConfig
from pipeline.core import run_pipeline

cfg = RuntimeConfig.from_dict({"POSTGRES_DSN": "..."})
run_pipeline(cfg)

# 方案 A 用法（兼容 — globals 模式，适合 Colab 快速运行）
import pipeline

pipeline.run_pipeline({"POSTGRES_DSN": "..."})
pipeline.POSTGRES_DSN  # ✅ 仍可访问全局变量
pipeline.apply_runtime_config({"POSTGRES_DSN": "..."})
"""

from __future__ import annotations

import os
import sys as _sys

# 确保包内模块可被相对导入
_package_dir = os.path.dirname(os.path.abspath(__file__))
if _package_dir not in _sys.path:
    _sys.path.insert(0, os.path.dirname(_package_dir))

# ---- 方案 A 兼容层：模块级全局变量 ----
# 这些变量由 apply_runtime_config 动态设置
# 当通过 `import pipeline; pipeline.POSTGRES_DSN` 访问时，fallback 到函数查找

from pipeline.config import (
    RuntimeConfig,
    DEFAULT_RUNTIME_CONFIG,
    normalize_runtime_source,
    collect_runtime_config_snapshot,
    get_remaining_runtime_seconds as _get_remaining,
)
from pipeline.logger import log, SimpleLogger, set_runtime_config as _set_logger_cfg
from pipeline.utils import (
    sanitize_filename,
    normalize_text_items,
    make_json_compatible,
    write_json_file,
    read_json_file,
    format_seconds_hhmmss,
    parse_duration_to_seconds,
    build_supabase_text_update,
    append_unique_text_items,
    parse_text_list_config,
)
from pipeline.models.types import BookResult
from pipeline.db.connection import (
    get_postgres_dsn,
    get_public_table_identifier,
    execute_postgres_fetchone,
    execute_postgres_fetchall,
    execute_postgres,
    execute_postgres_fetchval,
)
from pipeline.db.books import fetch_books_page, update_book_status, update_book_tags, delete_book_from_database
from pipeline.db.states import (
    load_split_processing_state,
    save_split_processing_state,
    initialize_split_processing_state,
    delete_split_processing_state,
    list_interrupted_book_states,
    evaluate_split_completion_state,
    get_split_part_state,
    get_split_playlist_state,
    cleanup_completed_split_states,
)
from pipeline.audio.download import download_file, download_audio_file, download_chapter_items, sync_music_library_if_enabled
from pipeline.audio.processing import (
    merge_audio_ffmpeg,
    denoise_audio_paths_parallel,
    build_split_part_plans,
    build_final_audio_from_chapter_paths,
    setup_deep_filter,
    estimate_chapter_duration_seconds,
    probe_audio_duration_seconds,
    MIN_BOOK_DURATION_SECONDS,
)
from pipeline.audio.bgm import mix_with_bgm, analyze_audio, advanced_music_calibration
from pipeline.ai.modelscope import generate_cover_image, load_runtime_token, rotate_modelscope_token
from pipeline.ai.cover import generate_book_cover
from pipeline.ai.seo import generate_seo_text
from pipeline.youtube.auth import get_authenticated_youtube
from pipeline.youtube.upload import upload_video_with_retries
from pipeline.youtube.playlist import get_or_create_playlist, add_video_to_playlist, list_book_playlists
from pipeline.youtube.podcast import (
    ensure_podcast_show,
    build_podcast_show_description,
    add_to_podcast_playlist,
    get_podcast_text_client,
)

from pipeline.core import (
    run_pipeline,
    process_book,
    process_standard_book,
    process_split_book,
    save_run_summary,
    generate_video,
    generate_youtube_timestamps,
    validate_runtime_config as _validate_cfg,
    _propagate_config as _propagate_cfg,
)

# ---- 方案 A 全局变量兼容 ----
_active_cfg: RuntimeConfig | None = None


def _get_global(name: str, default=None):
    """从当前激活的 RuntimeConfig 中获取配置值"""
    if _active_cfg is None:
        return default
    # 转换全大写键名到 dataclass 字段名
    field_name = name.lower()
    if hasattr(_active_cfg, field_name):
        return getattr(_active_cfg, field_name)
    return default


def apply_runtime_config(runtime_config: dict | None = None):
    """
    方案 A 兼容：globals() 模式

    用法：
        apply_runtime_config({"POSTGRES_DSN": "..."})
        print(POSTGRES_DSN)  # 通过 __getattr__ 获取
    """
    global _active_cfg
    merged = dict(DEFAULT_RUNTIME_CONFIG)
    if runtime_config:
        merged.update(runtime_config)
    _active_cfg = RuntimeConfig.from_dict(merged)
    _propagate_cfg(_active_cfg)
    # 回写默认值
    if not _active_cfg.project_flag:
        _active_cfg.project_flag = _active_cfg.youtube_channel_name
    if not _active_cfg.music_dir:
        _active_cfg.music_dir = _active_cfg.local_music_dir
    return _active_cfg


def validate_runtime_config():
    """方案 A 兼容：验证当前配置"""
    if _active_cfg is None:
        raise RuntimeError("请先调用 apply_runtime_config()")
    _validate_cfg(_active_cfg)


def get_remaining_runtime_seconds(run_started_at: float):
    """方案 A 兼容"""
    if _active_cfg is None:
        return None
    import time
    return _active_cfg.max_runtime_hours * 3600 - (time.time() - run_started_at)


def should_stop_before_next_book(run_started_at: float):
    """方案 A 兼容"""
    if _active_cfg is None:
        return False, None
    remaining = get_remaining_runtime_seconds(run_started_at)
    if remaining is None:
        return False, None
    buffer_seconds = max(0, _active_cfg.stop_buffer_minutes * 60)
    return remaining <= buffer_seconds, remaining


# ---- 模块级 __getattr__：支持方案 A 的 `import pipeline; pipeline.POSTGRES_DSN` ----
_active_cfg_refs = {
    # 全大写键名 -> dataclass 字段名
    "POSTGRES_DSN": "postgres_dsn",
    "YOUTUBE_CHANNEL_NAME": "youtube_channel_name",
    "MAX_PROCESS_COUNT": "max_process_count",
    "PROJECT_FLAG": "project_flag",
    "OUTPUT_ROOT": "output_root",
    "TARGET_CATEGORY": "target_category",
    "DOWNLOAD_WORKERS": "download_workers",
    "REQUEST_DELAY": "request_delay",
    "REQUEST_TIMEOUT": "request_timeout",
    "MODELSCOPE_IMAGE_CONNECT_TIMEOUT": "modelscope_image_connect_timeout",
    "MODELSCOPE_IMAGE_READ_TIMEOUT": "modelscope_image_read_timeout",
    "MODELSCOPE_IMAGE_POLL_CONNECT_TIMEOUT": "modelscope_image_poll_connect_timeout",
    "MODELSCOPE_IMAGE_POLL_READ_TIMEOUT": "modelscope_image_poll_read_timeout",
    "MODELSCOPE_TOKEN_SWITCH_DELAY_SECONDS": "modelscope_token_switch_delay_seconds",
    "MAX_RETRIES": "max_retries",
    "AUDIO_DOWNLOAD_CONNECT_TIMEOUT": "audio_download_connect_timeout",
    "AUDIO_DOWNLOAD_READ_TIMEOUT": "audio_download_read_timeout",
    "AUDIO_DOWNLOAD_MAX_RETRY_ATTEMPTS": "audio_download_max_retry_attempts",
    "AUDIO_DOWNLOAD_MAX_TOTAL_SECONDS": "audio_download_max_total_seconds",
    "AUDIO_DOWNLOAD_STUCK_LOG_INTERVAL_SECONDS": "audio_download_stuck_log_interval_seconds",
    "SKIP_EXISTING": "skip_existing",
    "FORCE_REPROCESS": "force_reprocess",
    "MAX_RUNTIME_HOURS": "max_runtime_hours",
    "STOP_BUFFER_MINUTES": "stop_buffer_minutes",
    "LONG_AUDIO_SPLIT_TRIGGER_HOURS": "long_audio_split_trigger_hours",
    "LONG_AUDIO_PART_TARGET_HOURS": "long_audio_part_target_hours",
    "BOOK_STATE_TABLE": "book_state_table",
    "CLEANUP_COMPLETED_SPLIT_STATES": "cleanup_completed_split_states",
    "PRIORITIZE_INTERRUPTED_BOOKS": "prioritize_interrupted_books",
    "QUIET_RUNTIME_OUTPUT": "quiet_runtime_output",
    "ENABLE_DEEPFILTER": "enable_deepfilter",
    "segment_duration_minutes": "segment_duration_minutes",
    "DEEPFILTER_WORKERS": "deepfilter_workers",
    "ENABLE_COVER_GENERATION": "enable_cover_generation",
    "MODELSCOPE_TOKEN_SOURCE": "modelscope_token_source",
    "CLOUD_RUNTIME_SETTINGS_TABLE": "cloud_runtime_settings_table",
    "MODELSCOPE_TOKEN_TABLE": "modelscope_token_table",
    "MODELSCOPE_TOKEN": "modelscope_token",
    "ENABLE_SEO_GENERATION": "enable_seo_generation",
    "ENABLE_YOUTUBE_UPLOAD": "enable_youtube_upload",
    "YOUTUBE_PRIVACY_STATUS": "youtube_privacy_status",
    "YOUTUBE_SCHEDULE_AFTER_HOURS": "youtube_schedule_after_hours",
    "YOUTUBE_DAILY_PUBLISH_LIMIT": "youtube_daily_publish_limit",
    "YOUTUBE_CATEGORY_ID": "youtube_category_id",
    "YOUTUBE_DEFAULT_LANGUAGE": "youtube_default_language",
    "ENABLE_YOUTUBE_TRADITIONAL_LOCALIZATION": "enable_youtube_traditional_localization",
    "YOUTUBE_LOCALIZATION_LOCALES": "youtube_localization_locales",
    "YOUTUBE_TRADITIONAL_LOCALE": "youtube_traditional_locale",
    "YOUTUBE_TRADITIONAL_OPENCC_CONFIG": "youtube_traditional_opencc_config",
    "ENABLE_AUTO_INSTALL_OPENCC": "enable_auto_install_opencc",
    "APPEND_TAGS_TO_TITLE": "append_tags_to_title",
    "APPEND_TAGS_TO_DESC": "append_tags_to_desc",
    "ENABLE_VIDEO_GENERATION": "enable_video_generation",
    "VIDEO_RESOLUTION": "video_resolution",
    "DOWNLOAD_FROM_BUCKETS": "download_from_buckets",
    "HF_MUSIC_DOWNLOAD_METHOD": "hf_music_download_method",
    "HF_DATASET_ZIP_URLS_SOURCE": "hf_dataset_zip_urls_source",
    "HF_DATASET_ZIP_URLS": "hf_dataset_zip_urls",
    "BUCKET_IDS_SOURCE": "bucket_ids_source",
    "BUCKET_IDS": "bucket_ids",
    "HF_TOKEN": "hf_token",
    "LOCAL_MUSIC_DIR": "local_music_dir",
    "ENABLE_BGM_MIX": "enable_bgm_mix",
    "MUSIC_DIR": "music_dir",
    "VOLUME_OFFSET_DB": "volume_offset_db",
    "HIGHPASS_FREQ": "highpass_freq",
    "FADE_DURATION_MS": "fade_duration_ms",
    "MIN_VOLUME_DB": "min_volume_db",
    "ENABLE_DYNAMIC_VOLUME": "enable_dynamic_volume",
    "ENABLE_SPECTRAL_SHAPING": "enable_spectral_shaping",
    "STEREO_OFFSET": "stereo_offset",
    "ENABLE_YOUTUBE_PODCAST_RUNTIME": "enable_youtube_podcast_runtime",
    "ENABLE_YOUTUBE_PODCAST_UNIFIED_SHOW": "enable_youtube_podcast_unified_show",
    "ENABLE_YOUTUBE_PODCAST_SPLIT_PLAYLIST": "enable_youtube_podcast_split_playlist",
    "YOUTUBE_PODCAST_SHOW_TITLE_TEMPLATE": "youtube_podcast_show_title_template",
    "YOUTUBE_PODCAST_IMAGE_SIZE": "youtube_podcast_image_size",
    "YOUTUBE_PODCAST_IMAGE_MAX_BYTES": "youtube_podcast_image_max_bytes",
    "YOUTUBE_PODCAST_SHOW_PLAYLIST_SETTING_KEY": "youtube_podcast_show_playlist_setting_key",
    "SENSENOVA_BASE_URL": "sensenova_base_url",
    "SENSENOVA_API_KEY": "sensenova_api_key",
    "API_PRIORITY_ORDER": "api_priority_order",
    "YOUTUBE_PODCAST_TEXT_MODEL_PRIMARY": "youtube_podcast_text_model_primary",
    "YOUTUBE_PODCAST_TEXT_MODEL_FALLBACK": "youtube_podcast_text_model_fallback",
    "YOUTUBE_PODCAST_IMAGE_MODEL_PRIMARY": "youtube_podcast_image_model_primary",
    "YOUTUBE_PODCAST_TEXT_MODEL_RETRIES": "youtube_podcast_text_model_retries",
    "YOUTUBE_PODCAST_IMAGE_MODEL_RETRIES": "youtube_podcast_image_model_retries",
    "YOUTUBE_PODCAST_AI_RETRY_BASE_SECONDS": "youtube_podcast_ai_retry_base_seconds",
    "YOUTUBE_PODCAST_YT_RETRIES": "youtube_podcast_yt_retries",
    "YOUTUBE_PODCAST_YT_RETRY_BASE_SECONDS": "youtube_podcast_yt_retry_base_seconds",
    "YOUTUBE_PODCAST_FONT_CACHE_DIRNAME": "youtube_podcast_font_cache_dirname",
}


def __getattr__(name):
    """支持方案 A 的模块级全局变量访问"""
    if name in _active_cfg_refs and _active_cfg is not None:
        return getattr(_active_cfg, _active_cfg_refs[name])
    raise AttributeError(f"module 'pipeline' has no attribute '{name}'")


def __dir__():
    default = [
        "RuntimeConfig",
        "BookResult",
        "apply_runtime_config",
        "validate_runtime_config",
        "run_pipeline",
        "process_book",
        "log",
        "SimpleLogger",
    ]
    return sorted(set(default + list(_active_cfg_refs.keys())))