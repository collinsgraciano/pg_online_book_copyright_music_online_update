"""运行配置管理：RuntimeConfig dataclass + 配置加载 + 校验"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


DEFAULT_RUNTIME_CONFIG = {
    "POSTGRES_DSN": "",
    "YOUTUBE_CHANNEL_NAME": "",
    "MAX_PROCESS_COUNT": 10,
    "PROJECT_FLAG": "",
    "OUTPUT_ROOT": "/content/",
    "TARGET_CATEGORY": "文学小说",
    "DOWNLOAD_WORKERS": 4,
    "REQUEST_DELAY": 0.3,
    "REQUEST_TIMEOUT": 300,
    "MODELSCOPE_IMAGE_CONNECT_TIMEOUT": 300,
    "MODELSCOPE_IMAGE_READ_TIMEOUT": 300,
    "MODELSCOPE_IMAGE_POLL_CONNECT_TIMEOUT": 300,
    "MODELSCOPE_IMAGE_POLL_READ_TIMEOUT": 300,
    "MODELSCOPE_TOKEN_SWITCH_DELAY_SECONDS": 30,
    "API_PRIORITY_ORDER": "modelscope,sensenova",
    "MAX_RETRIES": 3,
    "AUDIO_DOWNLOAD_CONNECT_TIMEOUT": 20,
    "AUDIO_DOWNLOAD_READ_TIMEOUT": 90,
    "AUDIO_DOWNLOAD_MAX_RETRY_ATTEMPTS": 12,
    "AUDIO_DOWNLOAD_MAX_TOTAL_SECONDS": 1800,
    "AUDIO_DOWNLOAD_STUCK_LOG_INTERVAL_SECONDS": 30,
    "SKIP_EXISTING": True,
    "FORCE_REPROCESS": False,
    "MAX_RUNTIME_HOURS": 11.5,
    "STOP_BUFFER_MINUTES": 20,
    "LONG_AUDIO_SPLIT_TRIGGER_HOURS": 12.0,
    "LONG_AUDIO_PART_TARGET_HOURS": 11.8,
    "BOOK_STATE_TABLE": "book_processing_states",
    "CLEANUP_COMPLETED_SPLIT_STATES": True,
    "PRIORITIZE_INTERRUPTED_BOOKS": True,
    "QUIET_RUNTIME_OUTPUT": False,
    "ENABLE_DEEPFILTER": True,
    "segment_duration_minutes": 60,
    "DEEPFILTER_WORKERS": 2,
    "ENABLE_COVER_GENERATION": True,
    "MODELSCOPE_TOKEN_SOURCE": "database",
    "CLOUD_RUNTIME_SETTINGS_TABLE": "channel_runtime_settings",
    "MODELSCOPE_TOKEN_TABLE": "modelscope_tokens",
    "MODELSCOPE_TOKEN": "",
    "ENABLE_SEO_GENERATION": True,
    "ENABLE_YOUTUBE_UPLOAD": True,
    "YOUTUBE_PRIVACY_STATUS": "schedule",
    "YOUTUBE_SCHEDULE_AFTER_HOURS": 24,
    "YOUTUBE_DAILY_PUBLISH_LIMIT": 3,
    "YOUTUBE_CATEGORY_ID": "",
    "YOUTUBE_DEFAULT_LANGUAGE": "zh-CN",
    "ENABLE_YOUTUBE_TRADITIONAL_LOCALIZATION": True,
    "YOUTUBE_LOCALIZATION_LOCALES": "zh-TW,zh-HK,zh-SG,zh-Hant",
    "YOUTUBE_TRADITIONAL_LOCALE": "zh-TW",
    "YOUTUBE_TRADITIONAL_OPENCC_CONFIG": "s2t",
    "ENABLE_AUTO_INSTALL_OPENCC": True,
    "APPEND_TAGS_TO_TITLE": False,
    "APPEND_TAGS_TO_DESC": True,
    "ENABLE_VIDEO_GENERATION": True,
    "VIDEO_RESOLUTION": "1080p",
    "DOWNLOAD_FROM_BUCKETS": True,
    "HF_MUSIC_DOWNLOAD_METHOD": "datasets_zip_urls",
    "HF_DATASET_ZIP_URLS_SOURCE": "database",
    "HF_DATASET_ZIP_URLS": "",
    "BUCKET_IDS_SOURCE": "database",
    "BUCKET_IDS": "",
    "HF_TOKEN": "",
    "LOCAL_MUSIC_DIR": "/content/music",
    "ENABLE_BGM_MIX": True,
    "MUSIC_DIR": "/content/music",
    "VOLUME_OFFSET_DB": -25,
    "HIGHPASS_FREQ": 150,
    "FADE_DURATION_MS": 3000,
    "MIN_VOLUME_DB": -40,
    "ENABLE_DYNAMIC_VOLUME": True,
    "ENABLE_SPECTRAL_SHAPING": True,
    "STEREO_OFFSET": 0.0,
    # Podcast 运行配置
    "ENABLE_YOUTUBE_PODCAST_RUNTIME": True,
    "ENABLE_YOUTUBE_PODCAST_UNIFIED_SHOW": True,
    "ENABLE_YOUTUBE_PODCAST_SPLIT_PLAYLIST": True,
    "YOUTUBE_PODCAST_SHOW_TITLE_TEMPLATE": "{channel_name}｜长篇有声书全集",
    "YOUTUBE_PODCAST_IMAGE_SIZE": 2048,
    "YOUTUBE_PODCAST_IMAGE_MAX_BYTES": 2097152,
    "YOUTUBE_PODCAST_SHOW_PLAYLIST_SETTING_KEY": "podcast_longform_show_playlist_id",
    "SENSENOVA_BASE_URL": "https://token.sensenova.cn/v1",
    "SENSENOVA_API_KEY": "",
    "YOUTUBE_PODCAST_TEXT_MODEL_PRIMARY": "deepseek-v4-flash",
    "YOUTUBE_PODCAST_TEXT_MODEL_FALLBACK": "sensenova-6.7-flash-lite",
    "YOUTUBE_PODCAST_IMAGE_MODEL_PRIMARY": "sensenova-u1-fast",
    "YOUTUBE_PODCAST_TEXT_MODEL_RETRIES": 2,
    "YOUTUBE_PODCAST_IMAGE_MODEL_RETRIES": 3,
    "YOUTUBE_PODCAST_AI_RETRY_BASE_SECONDS": 30.0,
    "YOUTUBE_PODCAST_YT_RETRIES": 5,
    "YOUTUBE_PODCAST_YT_RETRY_BASE_SECONDS": 3.0,
    "YOUTUBE_PODCAST_FONT_CACHE_DIRNAME": "_podcast_font_cache",
}


@dataclass
class RuntimeConfig:
    """类型安全的运行配置，替代 globals() 隐式共享模式"""

    # --- 基础连接 ---
    postgres_dsn: str = ""
    youtube_channel_name: str = ""
    project_flag: str = ""
    output_root: str = "/content/"
    target_category: str = "文学小说"

    # --- 处理控制 ---
    max_process_count: int = 10
    max_runtime_hours: float = 11.5
    stop_buffer_minutes: int = 20
    skip_existing: bool = True
    force_reprocess: bool = False

    # --- 下载 ---
    download_workers: int = 4
    request_delay: float = 0.3
    request_timeout: int = 300
    max_retries: int = 3
    audio_download_connect_timeout: int = 20
    audio_download_read_timeout: int = 90
    audio_download_max_retry_attempts: int = 12
    audio_download_max_total_seconds: int = 1800
    audio_download_stuck_log_interval_seconds: int = 30

    # --- 长音频分片 ---
    long_audio_split_trigger_hours: float = 12.0
    long_audio_part_target_hours: float = 11.8
    book_state_table: str = "book_processing_states"
    cleanup_completed_split_states: bool = True
    prioritize_interrupted_books: bool = True

    # --- DeepFilter 降噪 ---
    enable_deepfilter: bool = True
    segment_duration_minutes: int = 60
    deepfilter_workers: int = 2

    # --- AI 封面 / SEO ---
    enable_cover_generation: bool = True
    enable_seo_generation: bool = True
    modelscope_token_source: str = "database"
    modelscope_token_table: str = "modelscope_tokens"
    modelscope_token: str = ""
    cloud_runtime_settings_table: str = "channel_runtime_settings"
    modelscope_image_connect_timeout: int = 300
    modelscope_image_read_timeout: int = 300
    modelscope_image_poll_connect_timeout: int = 300
    modelscope_image_poll_read_timeout: int = 300
    modelscope_token_switch_delay_seconds: int = 30
    api_priority_order: str = "modelscope,sensenova"

    # --- YouTube 上传 ---
    enable_youtube_upload: bool = True
    youtube_privacy_status: str = "schedule"
    youtube_schedule_after_hours: int = 24
    youtube_daily_publish_limit: int = 3
    youtube_category_id: str = ""
    youtube_default_language: str = "zh-CN"
    enable_youtube_traditional_localization: bool = True
    youtube_localization_locales: str = "zh-TW,zh-HK,zh-SG,zh-Hant"
    youtube_traditional_locale: str = "zh-TW"
    youtube_traditional_opencc_config: str = "s2t"
    enable_auto_install_opencc: bool = True
    append_tags_to_title: bool = False
    append_tags_to_desc: bool = True

    # --- 视频生成 ---
    enable_video_generation: bool = True
    video_resolution: str = "1080p"

    # --- BGM 混音 ---
    download_from_buckets: bool = True
    hf_music_download_method: str = "datasets_zip_urls"
    hf_dataset_zip_urls_source: str = "database"
    hf_dataset_zip_urls: str = ""
    bucket_ids_source: str = "database"
    bucket_ids: str = ""
    hf_token: str = ""
    local_music_dir: str = "/content/music"
    enable_bgm_mix: bool = True
    music_dir: str = "/content/music"
    volume_offset_db: int = -25
    highpass_freq: int = 150
    fade_duration_ms: int = 3000
    min_volume_db: int = -40
    enable_dynamic_volume: bool = True
    enable_spectral_shaping: bool = True
    stereo_offset: float = 0.0

    # --- Podcast 运行配置 ---
    enable_youtube_podcast_runtime: bool = True
    enable_youtube_podcast_unified_show: bool = True
    enable_youtube_podcast_split_playlist: bool = True
    youtube_podcast_show_title_template: str = "{channel_name}｜长篇有声书全集"
    youtube_podcast_image_size: int = 2048
    youtube_podcast_image_max_bytes: int = 2097152
    youtube_podcast_show_playlist_setting_key: str = "podcast_longform_show_playlist_id"
    sensenova_base_url: str = "https://token.sensenova.cn/v1"
    sensenova_api_key: str = ""
    youtube_podcast_text_model_primary: str = "deepseek-v4-flash"
    youtube_podcast_text_model_fallback: str = "sensenova-6.7-flash-lite"
    youtube_podcast_image_model_primary: str = "sensenova-u1-fast"
    youtube_podcast_text_model_retries: int = 2
    youtube_podcast_image_model_retries: int = 3
    youtube_podcast_ai_retry_base_seconds: float = 30.0
    youtube_podcast_yt_retries: int = 5
    youtube_podcast_yt_retry_base_seconds: float = 3.0
    youtube_podcast_font_cache_dirname: str = "_podcast_font_cache"

    # --- 静默输出 ---
    quiet_runtime_output: bool = True

    # --- 额外运行时属性（非配置项，运行时填充）---
    modelscope_token_source_normalized: str = "database"
    hf_dataset_zip_urls_source_normalized: str = "database"
    bucket_ids_source_normalized: str = "database"

    @classmethod
    def from_dict(cls, config_dict: dict | None = None) -> RuntimeConfig:
        """从字典（如 Colab 表单）构造 RuntimeConfig"""
        merged = dict(DEFAULT_RUNTIME_CONFIG)
        if config_dict:
            merged.update(config_dict)

        # 字段名映射：全大写键名 -> dataclass 字段名
        key_map = {k.lower().replace("-", "_"): k for k in merged}

        kwargs = {}
        for field_name in cls.__dataclass_fields__:
            dict_key = field_name.lower().replace("-", "_")
            # 尝试多种匹配方式
            for key in merged:
                if key.lower().replace("-", "_") == dict_key:
                    kwargs[field_name] = merged[key]
                    break
            else:
                # 尝试 find 方式
                for merged_key, merged_val in merged.items():
                    if merged_key.lower().replace("-", "_") == dict_key:
                        kwargs[field_name] = merged_val
                        break

        cfg = cls(**kwargs)

        # 自动填充 PROJECT_FLAG
        if not cfg.project_flag:
            cfg.project_flag = cfg.youtube_channel_name

        # 自动填充 MUSIC_DIR
        if not cfg.music_dir:
            cfg.music_dir = cfg.local_music_dir

        # 标准化 source 字段
        cfg.modelscope_token_source_normalized = normalize_runtime_source(cfg.modelscope_token_source, "database")
        cfg.hf_dataset_zip_urls_source_normalized = normalize_runtime_source(cfg.hf_dataset_zip_urls_source, "database")
        cfg.bucket_ids_source_normalized = normalize_runtime_source(cfg.bucket_ids_source, "database")

        return cfg


def normalize_runtime_source(source: str, default: str = "database") -> str:
    """规范化运行时来源配置"""
    mode = str(source or default).strip().lower()
    if not mode:
        return default
    if mode in {"supabase", "postgres", "postgresql", "db"}:
        return "database"
    return mode


def _bool_runtime_value(value, default=False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _read_positive_int_runtime_config(value, default_value: int) -> int:
    try:
        val = int(value or default_value)
    except Exception:
        val = default_value
    return max(1, val)


def collect_runtime_config_snapshot(cfg: RuntimeConfig) -> dict:
    """收集当前配置快照，用于写入运行报告"""
    return {
        "database_backend": "postgresql",
        "postgres_dsn_configured": bool(cfg.postgres_dsn),
        "project_flag": cfg.project_flag,
        "target_category": cfg.target_category,
        "max_process_count": cfg.max_process_count,
        "max_runtime_hours": cfg.max_runtime_hours,
        "stop_buffer_minutes": cfg.stop_buffer_minutes,
        "long_audio_split_trigger_hours": cfg.long_audio_split_trigger_hours,
        "long_audio_part_target_hours": cfg.long_audio_part_target_hours,
        "book_state_table": cfg.book_state_table,
        "prioritize_interrupted_books": cfg.prioritize_interrupted_books,
        "output_root": cfg.output_root,
        "download_workers": cfg.download_workers,
        "audio_download_connect_timeout": cfg.audio_download_connect_timeout,
        "audio_download_read_timeout": cfg.audio_download_read_timeout,
        "audio_download_max_retry_attempts": cfg.audio_download_max_retry_attempts,
        "audio_download_max_total_seconds": cfg.audio_download_max_total_seconds,
        "audio_download_stuck_log_interval_seconds": cfg.audio_download_stuck_log_interval_seconds,
        "hf_music_download_enabled": cfg.download_from_buckets,
        "hf_music_download_method": cfg.hf_music_download_method,
        "enable_deepfilter": cfg.enable_deepfilter,
        "deepfilter_workers": cfg.deepfilter_workers,
        "enable_bgm_mix": cfg.enable_bgm_mix,
        "music_dir": cfg.music_dir,
        "enable_cover_generation": cfg.enable_cover_generation,
        "cloud_runtime_settings_table": cfg.cloud_runtime_settings_table,
        "modelscope_token_source": cfg.modelscope_token_source_normalized,
        "modelscope_token_table": cfg.modelscope_token_table,
        "modelscope_image_connect_timeout": cfg.modelscope_image_connect_timeout,
        "modelscope_image_read_timeout": cfg.modelscope_image_read_timeout,
        "modelscope_image_poll_connect_timeout": cfg.modelscope_image_poll_connect_timeout,
        "modelscope_image_poll_read_timeout": cfg.modelscope_image_poll_read_timeout,
        "modelscope_token_switch_delay_seconds": cfg.modelscope_token_switch_delay_seconds,
        "enable_seo_generation": cfg.enable_seo_generation,
        "hf_dataset_zip_urls_source": cfg.hf_dataset_zip_urls_source_normalized,
        "bucket_ids_source": cfg.bucket_ids_source_normalized,
        "enable_video_generation": cfg.enable_video_generation,
        "enable_youtube_upload": cfg.enable_youtube_upload,
        "youtube_channel_name": cfg.youtube_channel_name,
        "youtube_privacy_status": cfg.youtube_privacy_status,
        "youtube_schedule_after_hours": cfg.youtube_schedule_after_hours,
        "youtube_schedule_local_timezone": "Asia/Shanghai",
        "youtube_daily_publish_limit": cfg.youtube_daily_publish_limit,
    }


def get_remaining_runtime_seconds(cfg: RuntimeConfig, run_started_at: float) -> Optional[float]:
    """计算剩余运行时间"""
    budget_hours = cfg.max_runtime_hours
    if budget_hours <= 0:
        return None
    import time
    return budget_hours * 3600 - (time.time() - run_started_at)


def should_stop_before_next_book(cfg: RuntimeConfig, run_started_at: float):
    """判断是否应在下一个任务前停止"""
    remaining = get_remaining_runtime_seconds(cfg, run_started_at)
    if remaining is None:
        return False, None
    buffer_seconds = max(0, cfg.stop_buffer_minutes * 60)
    return remaining <= buffer_seconds, remaining