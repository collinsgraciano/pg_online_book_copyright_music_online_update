# Pipeline 使用教程 & 配置说明

> 本教程适用于 `pipeline/` 包（原 `runtime_core.py` 拆分后的多模块架构），覆盖从零搭建到日常运维的完整流程。

---

## 目录

1. [架构概览](#1-架构概览)
2. [环境准备](#2-环境准备)
3. [配置参数详解](#3-配置参数详解)
4. [PostgreSQL 表结构](#4-postgresql-表结构)
5. [运行流程](#5-运行流程)
6. [Colab 部署](#6-colab-部署)
7. [本地开发与测试](#7-本地开发与测试)
8. [断点续跑机制](#8-断点续跑机制)
9. [Podcast 功能](#9-podcast-功能)
10. [常见问题](#10-常见问题)
11. [模块依赖图](#11-模块依赖图)

---

## 1. 架构概览

```
┌─────────────────────────────────────────────────────┐
│                colab_loader.ipynb                    │
│  (设置参数 → 下载 pipeline/ → import → run)         │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│                pipeline/__init__.py                  │
│   按顺序导入 13 个模块，保证副作用执行顺序            │
└───────┬──────────────────────────────────────────────┘
        │
        │  Layer 0: 基础
        ├── config.py    — 配置全局 / apply_runtime_config
        └── runtime.py   — 日志 / 工具 / 文本归一化
        │
        │  Layer 1: 功能模块（无环依赖）
        ├── db.py             — PostgreSQL 操作
        ├── state.py          — 断点续跑状态管理
        ├── audio.py          — 音频下载/合并
        ├── deepfilter.py     — 降噪
        ├── bgm.py            — BGM 混音
        ├── music_download.py — 版权音乐
        ├── cover.py          — AI 封面
        └── seo.py            — SEO 文案
        │
        │  Layer 2: 上传
        └── youtube.py — YouTube 上传 / 播放列表
        │
        │  Layer 3: 播客（后置注入）
        └── podcast.py — Podcast + monkey‑patch
        │
        │  Layer 4: 编排
        └── pipeline.py — run_pipeline / process_book
```

### 关键设计决策

| 项目 | 说明 |
|------|------|
| 配置访问 | `apply_runtime_config()` 把 ~95 个配置写进 `config.py` 模块全局，各模块用 `from . import config as cfg; cfg.MAX_RETRIES` 读写 |
| Monkey‑patch | `podcast.py` 在 import 时覆盖 `pipeline.py` 的 `process_standard_book` / `sync_split_playlist` / `finalize_book_result`，实现 podcast 后置同步 |
| 播放列表覆盖 | `podcast.py` 将带重试的版本注入 `youtube.py`，与原单文件覆盖行为一致 |
| 部署形态 | Notebook 逐文件下载 `pipeline/` 目录，本地 `sys.path.insert` 后 `import pipeline` |

---

## 2. 环境准备

### 2.1 依赖包

在 Colab 或任意 Linux 环境中执行：

```bash
pip install -q psycopg[binary] pydub numpy scipy openai Pillow huggingface_hub>=0.20.0
pip install -q google-api-python-client google-auth-httplib2 google-auth-oauthlib
pip install -q requests tqdm
# 可选（繁体中文本地化）：
pip install -q opencc-python-reimplemented
```

### 2.2 外部工具

```bash
# FFmpeg（音频合并 / 降噪 / 视频封装）
apt-get -y update -qq && apt-get -y install -qq ffmpeg

# DeepFilterNet 5.6（降噪二进制，流水线自动下载）
# 无需手动安装，首次运行 `setup_deep_filter()` 会自动下载
```

### 2.3 PostgreSQL

需要一台可从 Colab 访问的 PostgreSQL 实例（VPS / Supabase / 等）。

**最小版本要求**：PostgreSQL 12+（用于 `ON CONFLICT` upsert、JSONB 等）。

---

## 3. 配置参数详解

### 3.1 基础连接

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `POSTGRES_DSN` | `str` | `""` | PostgreSQL 连接串，格式 `postgresql://user:pass@host:5432/db?sslmode=require` |
| `YOUTUBE_CHANNEL_NAME` | `str` | `""` | 当前绑定的 YouTube 频道名 |
| `PROJECT_FLAG` | `str` | `""` | 项目标记（写入 `books.status` 防重复处理，空时回退为频道名） |
| `OUTPUT_ROOT` | `str` | `"/content/"` | 输出根目录，建议使用 Google Drive 路径 |
| `TARGET_CATEGORY` | `str` | `"文学小说"` | 图书分类过滤（空 = 全部） |

### 3.2 下载参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `DOWNLOAD_WORKERS` | `int` | `4` | 并发下载线程数 |
| `REQUEST_DELAY` | `float` | `0.3` | 每个章节下载完成后等待秒数 |
| `REQUEST_TIMEOUT` | `int` | `300` | 普通 HTTP 超时（秒） |
| `MAX_RETRIES` | `int` | `3` | 普通文件下载最大重试次数 |
| `AUDIO_DOWNLOAD_CONNECT_TIMEOUT` | `int` | `20` | 章节音频 TCP 连接超时（秒） |
| `AUDIO_DOWNLOAD_READ_TIMEOUT` | `int` | `90` | 章节音频读取超时（秒） |
| `AUDIO_DOWNLOAD_MAX_RETRY_ATTEMPTS` | `int` | `12` | 章节音频最大重试次数 |
| `AUDIO_DOWNLOAD_MAX_TOTAL_SECONDS` | `int` | `1800` | 单章节总耗时上限（秒） |
| `AUDIO_DOWNLOAD_STUCK_LOG_INTERVAL_SECONDS` | `int` | `30` | 卡住检测日志间隔（秒） |

### 3.3 运行时长控制

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `MAX_RUNTIME_HOURS` | `float` | `11.5` | Colab 单次运行时长上限（小时） |
| `STOP_BUFFER_MINUTES` | `int` | `20` | 到期前 N 分钟停止启动新书 |
| `MAX_PROCESS_COUNT` | `int` | `10` | 本次最多成功处理多少本书（0 = 不限制） |
| `SKIP_EXISTING` | `bool` | `True` | 跳过已存在的文件，直接复用 |
| `FORCE_REPROCESS` | `bool` | `False` | 强制重新处理所有书籍 |

### 3.4 长音频分片 & 断点续跑

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `LONG_AUDIO_SPLIT_TRIGGER_HOURS` | `float` | `12.0` | 触发分片的预估总时长阈值（小时） |
| `LONG_AUDIO_PART_TARGET_HOURS` | `float` | `11.8` | 每片目标时长（小时） |
| `BOOK_STATE_TABLE` | `str` | `"book_processing_states"` | 断点状态存储表名 |
| `CLEANUP_COMPLETED_SPLIT_STATES` | `bool` | `True` | 启动前自动清理已完成的分片状态 |
| `PRIORITIZE_INTERRUPTED_BOOKS` | `bool` | `True` | 优先处理有续跑状态的书籍 |

### 3.5 DeepFilter 降噪

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `ENABLE_DEEPFILTER` | `bool` | `True` | 是否启用 DeepFilterNet 降噪 |
| `segment_duration_minutes` | `int` | `60` | 降噪分片时长（分钟） |
| `DEEPFILTER_WORKERS` | `int` | `2` | 降噪并行线程数 |

### 3.6 AI 封面生成

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `ENABLE_COVER_GENERATION` | `bool` | `True` | 是否启用 AI 封面 |
| `MODELSCOPE_TOKEN_SOURCE` | `str` | `"database"` | Token 来源：`database` / `local` |
| `MODELSCOPE_TOKEN_TABLE` | `str` | `"modelscope_tokens"` | Token 专用表名 |
| `MODELSCOPE_TOKEN` | `str` | `""` | 本地固定 Token（仅 `source=local` 时） |
| `CLOUD_RUNTIME_SETTINGS_TABLE` | `str` | `"channel_runtime_settings"` | 云端运行时设置表 |
| `API_PRIORITY_ORDER` | `str` | `"modelscope,sensenova"` | API 调用优先级 |
| `MODELSCOPE_IMAGE_CONNECT_TIMEOUT` | `int` | `300` | 生图请求连接超时 |
| `MODELSCOPE_IMAGE_READ_TIMEOUT` | `int` | `300` | 生图请求读取超时 |
| `MODELSCOPE_TOKEN_SWITCH_DELAY_SECONDS` | `int` | `30` | Token 切换间隔 |

### 3.7 SEO 文案

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `ENABLE_SEO_GENERATION` | `bool` | `True` | 是否启用 AI SEO 文案生成 |

### 3.8 YouTube 上传

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `ENABLE_YOUTUBE_UPLOAD` | `bool` | `True` | 是否启用 YouTube 上传 |
| `YOUTUBE_PRIVACY_STATUS` | `str` | `"schedule"` | `private` / `unlisted` / `public` / `schedule` |
| `YOUTUBE_SCHEDULE_AFTER_HOURS` | `int` | `24` | 预约发布延迟（小时） |
| `YOUTUBE_DAILY_PUBLISH_LIMIT` | `int` | `3` | 每日发布上限 |
| `YOUTUBE_CATEGORY_ID` | `str` | `""` | 视频分类 ID（空 = 自动） |
| `YOUTUBE_DEFAULT_LANGUAGE` | `str` | `"zh-CN"` | 默认语言 |
| `ENABLE_YOUTUBE_TRADITIONAL_LOCALIZATION` | `bool` | `True` | 自动生成繁体中文本地化 |
| `APPEND_TAGS_TO_TITLE` | `bool` | `False` | 把标签追加到标题末尾 |
| `APPEND_TAGS_TO_DESC` | `bool` | `True` | 把标签追加到描述末尾 |

### 3.9 视频生成

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `ENABLE_VIDEO_GENERATION` | `bool` | `True` | 是否启用 MP4 封装 |
| `VIDEO_RESOLUTION` | `str` | `"1080p"` | `720p` / `1080p` |

### 3.10 音乐库 & BGM

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `DOWNLOAD_FROM_BUCKETS` | `bool` | `True` | 是否从 HF 下载版权音乐 |
| `HF_MUSIC_DOWNLOAD_METHOD` | `str` | `"datasets_zip_urls"` | `datasets_zip_urls` / `buckets` |
| `HF_DATASET_ZIP_URLS_SOURCE` | `str` | `"database"` | ZIP URL 来源 |
| `HF_DATASET_ZIP_URLS` | `str` | `""` | ZIP 下载链接（source=local 时） |
| `BUCKET_IDS_SOURCE` | `str` | `"database"` | Bucket ID 来源 |
| `BUCKET_IDS` | `str` | `""` | Bucket ID 列表（source=local 时） |
| `HF_TOKEN` | `str` | `""` | Hugging Face API Token |
| `LOCAL_MUSIC_DIR` | `str` | `"/content/music"` | 本地音乐存放目录 |
| `ENABLE_BGM_MIX` | `bool` | `True` | 是否叠加 BGM |
| `MUSIC_DIR` | `str` | `"/content/music"` | BGM 源目录 |
| `VOLUME_OFFSET_DB` | `int` | `-25` | BGM 音量偏移（dB） |
| `HIGHPASS_FREQ` | `int` | `150` | 高通滤波频率（Hz） |
| `FADE_DURATION_MS` | `int` | `3000` | 淡入淡出时长（毫秒） |
| `MIN_VOLUME_DB` | `int` | `-40` | 最小音量阈值（dB） |
| `ENABLE_DYNAMIC_VOLUME` | `bool` | `True` | 动态音量均衡 |
| `ENABLE_SPECTRAL_SHAPING` | `bool` | `True` | 频谱塑形增强 |
| `STEREO_OFFSET` | `float` | `0.0` | 立体声偏移 |

### 3.11 Podcast 模式

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `ENABLE_YOUTUBE_PODCAST_RUNTIME` | `bool` | `True` | 启用 YouTube Podcast 模式 |
| `ENABLE_YOUTUBE_PODCAST_UNIFIED_SHOW` | `bool` | `True` | 全部书归入同一个 Podcast Show |
| `ENABLE_YOUTUBE_PODCAST_SPLIT_PLAYLIST` | `bool` | `True` | 为分片书单独创建播放列表 |
| `YOUTUBE_PODCAST_SHOW_TITLE_TEMPLATE` | `str` | `"{channel_name}｜长篇有声书全集"` | Show 标题模板 |
| `YOUTUBE_PODCAST_IMAGE_SIZE` | `int` | `2048` | Podcast 封面尺寸（像素） |
| `YOUTUBE_PODCAST_IMAGE_MAX_BYTES` | `int` | `2097152` | 封面文件大小上限（2MB） |
| `SENSENOVA_BASE_URL` | `str` | `"https://token.sensenova.cn/v1"` | Sensenova/DeepSeek API 地址 |
| `SENSENOVA_API_KEY` | `str` | `""` | Sensenova API Key |
| `YOUTUBE_PODCAST_TEXT_MODEL_PRIMARY` | `str` | `"deepseek-v4-flash"` | 文本主模型 |
| `YOUTUBE_PODCAST_TEXT_MODEL_FALLBACK` | `str` | `"sensenova-6.7-flash-lite"` | 文本备选模型 |
| `YOUTUBE_PODCAST_IMAGE_MODEL_PRIMARY` | `str` | `"sensenova-u1-fast"` | 图片生成模型 |
| `YOUTUBE_PODCAST_TEXT_MODEL_RETRIES` | `int` | `2` | 文本生成重试 |
| `YOUTUBE_PODCAST_IMAGE_MODEL_RETRIES` | `int` | `3` | 图片生成重试 |
| `YOUTUBE_PODCAST_AI_RETRY_BASE_SECONDS` | `float` | `30.0` | AI 调用重试间隔 |
| `YOUTUBE_PODCAST_YT_RETRIES` | `int` | `5` | YouTube API 重试次数 |
| `YOUTUBE_PODCAST_YT_RETRY_BASE_SECONDS` | `float` | `3.0` | YouTube API 重试间隔 |
| `QUIET_RUNTIME_OUTPUT` | `bool` | `True` | 静默模式（只保留警告/错误） |

---

## 4. PostgreSQL 表结构

至少需要以下 6 张表（Notebook cell 3 会输出完整建表 SQL）：

### 4.1 `public.books`
```sql
CREATE TABLE IF NOT EXISTS public.books (
    book_id   text PRIMARY KEY,
    book_name text,
    author    text,
    category  text,
    total_chapters integer,
    book_data jsonb,
    tags      text[],
    note      text,
    status    text DEFAULT '',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
```

### 4.2 `public.book_processing_states`
```sql
CREATE TABLE IF NOT EXISTS public.book_processing_states (
    book_id       text NOT NULL,
    project_flag  text NOT NULL,
    book_name     text,
    category      text,
    pending_resume boolean NOT NULL DEFAULT true,
    state_status  text NOT NULL DEFAULT 'in_progress',
    current_part_index integer,
    completed_part_count integer NOT NULL DEFAULT 0,
    part_count    integer NOT NULL DEFAULT 1,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    created_at    timestamptz NOT NULL DEFAULT now(),
    state_json    jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT book_processing_states_pkey PRIMARY KEY (book_id, project_flag)
);
```

### 4.3 `public.youtube_credentials`
```sql
CREATE TABLE IF NOT EXISTS public.youtube_credentials (
    channel_name text PRIMARY KEY,
    token_json   jsonb NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
```

### 4.4 `public.modelscope_tokens`
```sql
CREATE TABLE IF NOT EXISTS public.modelscope_tokens (
    channel_name text PRIMARY KEY,
    token_text   text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
```

### 4.5 `public.channel_runtime_settings`
```sql
CREATE TABLE IF NOT EXISTS public.channel_runtime_settings (
    channel_name  text NOT NULL,
    setting_key   text NOT NULL,
    setting_value text NOT NULL DEFAULT '',
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT channel_runtime_settings_pkey PRIMARY KEY (channel_name, setting_key)
);
```

### 4.6 `public.task_queue`
```sql
CREATE TABLE IF NOT EXISTS public.task_queue (
    book_id   text PRIMARY KEY,
    status    text NOT NULL DEFAULT 'pending',
    worker_id text,
    claimed_at timestamptz,
    finished_at timestamptz,
    retry_count integer NOT NULL DEFAULT 0,
    error_msg text,
    category  text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);
```

> **首次部署建议**：在 Colab cell 3 中打开 `SHOW_CREATE_ALL_POSTGRES_TABLES_SQL = True`，把输出的 SQL 在 VPS 上执行一次。以后无需重复。

---

## 5. 运行流程

### 5.1 整体流程图

```
run_pipeline(config)
│
├─ apply_runtime_config()         注入配置全局
├─ validate_runtime_config()      校验参数完整性
├─ execute_postgres_fetchval()    DB 连通性检查
├─ apply_cloud_runtime_overrides()从 DB 读取 cloud 设置
├─ sync_music_library_if_enabled()下载 HF 版权音乐
├─ _fetch_books_page_from_database() 拉取 books 列表
├─ list_interrupted_book_states()    恢复断点状态
├─ cleanup_completed_split_states()  清理已完成的分片记录
│
└─ for each book:
    │
    ├─ process_book(book_record)
    │   │
    │   ├─ 解析 book_data JSON
    │   ├─ 对 chapters_data 排序
    │   ├─ 计算预估总时长
    │   │
    │   ├─ 总时长 < 30 分钟 → skip_and_delete_short_book()
    │   │
    │   ├─ 总时长 > LONG_AUDIO_SPLIT_TRIGGER_HOURS?
    │   │   │
    │   │   ├─ YES → process_split_book()
    │   │   │   ├─ build_split_part_plans()    拆分计划
    │   │   │   ├─ initialize_split_processing_state()
    │   │   │   ├─ restore_split_shared_assets_from_state()
    │   │   │   ├─ prepare_book_cover_and_seo()     封面+SEO
    │   │   │   ├─ reconcile_split_part_upload_states()  恢复上传引用
    │   │   │   └─ for each part:
    │   │   │       └─ process_split_part()
    │   │   │           ├─ download_chapter_items()     下载章节
    │   │   │           ├─ denoise_audio_paths_parallel()降噪
    │   │   │           ├─ build_final_audio_from_chapter_paths()合并/混音
    │   │   │           ├─ generate_video()              封装 MP4
    │   │   │           └─ upload_to_youtube_detailed()  上传
    │   │   │   └─ sync_split_playlist() 同步/创建播放列表
    │   │   │
    │   │   └─ NO  → process_standard_book()
    │   │       ├─ download_chapter_items()
    │   │       ├─ denoise_audio_paths_parallel()
    │   │       ├─ build_final_audio_from_chapter_paths()
    │   │       ├─ prepare_standard_book_cover_and_seo_with_state()
    │   │       ├─ generate_video()
    │   │       └─ upload_to_youtube_detailed()
    │   │
    │   └─ finalize_book_result()  评估完成度
    │
    ├─ finalize_successful_book_for_project()  写 books.status
    └─ save_run_summary()  写 _run_reports/
```

### 5.2 状态持久化

每个阶段完成后都会 `save_split_processing_state()`，写入 PostgreSQL。下次启动时 `list_interrupted_book_states()` 恢复未完成的进度。关键 checkpoint 点包括：

- 分片计划就绪
- 章节下载完成
- 降噪完成
- 音频合并/混音完成
- MP4 封装完成
- YouTube 上传完成（含回执持久化）
- 播放列表同步完成

---

## 6. Colab 部署

### 6.1 首次使用（8 步）

1. **Cell 1**：安装依赖，准备 FFmpeg —— 执行。
2. **Cell 2**：填写运行参数 —— **至少填 `POSTGRES_DSN` 和 `YOUTUBE_CHANNEL_NAME`**。
3. **Cell 3**：`SHOW_CREATE_ALL_POSTGRES_TABLES_SQL = True` → 执行 → 把输出的 SQL 在 VPS 上执行（仅首次）。
4. **Cell 4**：`ENABLE_SYNC_CLOUD_RUNTIME_SETTINGS = True` → 执行一次，把 token 等写入 PostgreSQL（之后关闭）。
5. **Cell 5**：`FORCE_REAUTH = True` → 执行一次，完成 YouTube OAuth 并写入 `youtube_credentials`。
6. **Cell 6**：检查 `REMOTE_PIPELINE_BASE_URL` 指向正确的仓库 `main` 分支。
7. **Cell 7**：执行 —— 下载 `pipeline/` 包 → `import pipeline` → `pipeline.run_pipeline(config)`。

### 6.2 后续日常运行

1. 打开 Notebook → 确认 cell 1（依赖）已安装。
2. Cell 6 + cell 7 直接执行即可。
3. 参数可微调（如 `MAX_PROCESS_COUNT`、`TARGET_CATEGORY`），无需重复 OAuth。

### 6.3 多频道运行

```python
# Cell 2
YOUTUBE_CHANNEL_NAME = "ChannelA"  # 改频道名
PROJECT_FLAG = "ChannelA"          # 改项目标记

# Cell 5: 每个新频道做一次 OAuth 写入
BIND_CHANNEL_NAME = "ChannelA"
FORCE_REAUTH = True
```

### 6.4 多 token 轮换（防限流）

```sql
-- 在 modelscope_tokens 表中写入多个 token（同一个 channel_name = '__shared__'）
INSERT INTO public.modelscope_tokens (channel_name, token_text, updated_at)
VALUES ('__shared__', 'ms-token-xxxxx', now());

INSERT INTO public.channel_runtime_settings (channel_name, setting_key, setting_value, updated_at)
VALUES ('__shared__', 'MODELSCOPE_TOKEN', 'ms-token-xxxxx,ms-token-yyyyy', now());
```

逗号分隔多个 token，生图/文案时自动轮换。429 限流后自动切换到下一个 token。

---

## 7. 本地开发与测试

### 7.1 包结构导入

```python
import sys
sys.path.insert(0, ".")  # 项目根目录
import pipeline

# 独立测试某个模块
from pipeline.config import apply_runtime_config
from pipeline.runtime import log, sanitize_filename
from pipeline.db import execute_postgres_fetchone
```

### 7.2 配置快照测试

```python
from pipeline.config import collect_runtime_config_snapshot
import json

# 模拟 Notebook 传参
pipeline.apply_runtime_config({"POSTGRES_DSN": "...", "MAX_PROCESS_COUNT": 5})

snapshot = collect_runtime_config_snapshot()
print(json.dumps(snapshot, indent=2, ensure_ascii=False))
```

### 7.3 与旧 runtime_core.py 的配置 diff 对比

```python
# ----- 旧 -----
import importlib.util
spec = importlib.util.spec_from_file_location("old", "runtime_core.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
old_snapshot = old.collect_runtime_config_snapshot()

# ----- 新 -----
import pipeline
new_snapshot = pipeline.config.collect_runtime_config_snapshot()

# diff after same config applied
```

### 7.4 循环依赖检查

```bash
python -c "
import sys; sys.path.insert(0, '.')
import pipeline.config   # Layer 0 ✓
import pipeline.runtime  # Layer 0 ✓
import pipeline.db       # Layer 1 ✓
import pipeline.state    # Layer 1 ✓
print('All layer imports passed')
"
```

---

## 8. 断点续跑机制

### 8.1 工作原理

```
┌─────────────┐     ┌───────────────────────────┐
│  run 开始    │────▶│ 查 book_processing_states │
└─────────────┘     │ WHERE pending_resume=true │
                    └───────────┬───────────────┘
                                │
                    ┌───────────▼───────────────┐
                    │  按 updated_at 排序        │
                    │  中断的书排在前面           │
                    └───────────┬───────────────┘
                                │
                    ┌───────────▼───────────────┐
                    │  逐本书恢复：              │
                    │  · 恢复共享资产（封面/SEO）│
                    │  · 恢复各分片上传回执      │
                    │  · 跳过已完成的分片        │
                    │  · 从未完成的 step 继续    │
                    └───────────────────────────┘
```

### 8.2 状态字段说明

```json
{
  "state_version": 5,
  "mode": "split_upload|standard_upload",
  "book_id": "...",
  "plan_signature": "md5...",
  "parts": [
    {
      "part_index": 1,
      "status": "pending|in_progress|completed|failed",
      "last_stage": "download|denoise|merge_audio|generate_video|upload_youtube|completed",
      "audio_path": "...",
      "video_path": "...",
      "video_id": "...",
      "youtube_url": "...",
      "error": "..."
    }
  ],
  "playlist": {
    "playlist_id": "...",
    "status": "...",
    "video_ids": [...]
  },
  "shared_assets": {
    "seo_title": "...",
    "cover_image_base64": "..."
  }
}
```

### 8.3 常见续跑场景

| 场景 | 处理方式 |
|------|----------|
| Colab 断连 | 下次启动自动恢复，从最后 checkpoint 继续 |
| 某分片上传失败 | 标记 `failed`，下次从该分片下载重新开始 |
| YouTube 视频被删 | `reconcile_split_part_upload_states()` 检测缺失，重置上传状态 |
| 播放列表丢失 | 自动重建并重新加入已上传视频 |
| 配置变化（拆分阈值） | `plan_signature` 变化 → 重新计算分片；若结构兼容则复用已上传的引用 |

---

## 9. Podcast 功能

### 9.1 启用条件

```python
ENABLE_YOUTUBE_UPLOAD = True
YOUTUBE_CHANNEL_NAME = "YourChannel"
ENABLE_YOUTUBE_PODCAST_RUNTIME = True
ENABLE_YOUTUBE_PODCAST_UNIFIED_SHOW = True
```

### 9.2 工作流程

1. 每本单 P 书上传成功后 → 自动加入统一的 Podcast Show 播放列表（`_podcast_show_title(channel_name)`）。
2. 长音频分片书 → 所有分片上传完成后 → 创建独立播放列表 → 自动切换 podcastStatus = enabled → 上传 AI 生成的正方形封面。
3. Show 封面：AI 生成一次（Sensenova `sensenova-u1-fast`），失败时回退到文字渐变封面或现有缩略图裁剪。
4. Podcast 状态通过 `_podcast_wait_for_playlist_podcast_status()` 等待 YouTube API 确认。

### 9.3 配置示例

```python
# 中文有声书播客
YOUTUBE_PODCAST_SHOW_TITLE_TEMPLATE = "{channel_name}｜长篇有声书全集"
SENSENOVA_API_KEY = "sk-..."
YOUTUBE_PODCAST_TEXT_MODEL_PRIMARY = "deepseek-v4-flash"   # DeepSeek V4 生成文案
YOUTUBE_PODCAST_IMAGE_MODEL_PRIMARY = "sensenova-u1-fast"  # Sensenova 生成封面
```

---

## 10. 常见问题

### Q1: `PostgreSQL 连接失败`
- 检查 `POSTGRES_DSN` 格式：`postgresql://user:pass@host:5432/db?sslmode=require`
- 确认 VPS 防火墙放行 5432 端口
- 确认 PostgreSQL 监听地址非仅 `localhost`（需 `*` 或 `0.0.0.0`）

### Q2: `找不到 ModelScope Token`
- 检查 `modelscope_tokens` 表中是否有 `channel_name='__shared__'` 的 token
- 或切换到本地模式：`MODELSCOPE_TOKEN_SOURCE = "local"; MODELSCOPE_TOKEN = "ms-xxx"`
- 或在 Notebook cell 4 中同步一次

### Q3: YouTube 上传卡住
- 检查 `youtube_credentials` 表中 token 是否过期（可重新运行 cell 5 授权）
- 如果长时间卡在"传送视频大本尊"，可能是 Google 限速——等待或降低 `VIDEO_RESOLUTION` 到 `720p`

### Q4: 封面生成失败
- ModelScope 单 token 每日 ~50 次额度 — 建议 `MODELSCOPE_TOKEN_SOURCE=database` 并多 token 轮换
- 或启用 Sensenova 回退：`API_PRIORITY_ORDER = "modelscope,sensenova"` 并提供 `SENSENOVA_API_KEY`
- 封面审核拒绝 → 自动回退到 books 表中的 `picUrl`

### Q5: 运行中断后如何恢复
- 无需任何操作。下次启动时自动 `PRIORITIZE_INTERRUPTED_BOOKS = True` 优先恢复。
- 若要从头重跑所有书：`FORCE_REPROCESS = True`

### Q6: 音频下载一直超时
- 调大 `AUDIO_DOWNLOAD_CONNECT_TIMEOUT = 60`
- 调大 `AUDIO_DOWNLOAD_READ_TIMEOUT = 300`
- 调大 `AUDIO_DOWNLOAD_MAX_TOTAL_SECONDS = 3600`
- 减小 `DOWNLOAD_WORKERS = 2`（降低并发，缓解源站压力）

---

## 11. 模块依赖图

```
config ─────────────────────────────────────────────┐
  │ (无外部依赖)                                     │
runtime ── (import config) ────────────────────────┤
  │                                                  │
db ────── (import config, runtime) ─────────────────┤
state ─── (import config, runtime, db, audio) ──────┤
  │                                                  │
audio ─── (import config, runtime) ─────────────────┤
deepfilter (import config, runtime, audio) ──────────┤
bgm ───── (import config, runtime) ─────────────────┤
music_download (import config, runtime, db, audio) ─┤
cover ─── (import config, runtime, db) ─────────────┤
seo ───── (import config, runtime, cover) ──────────┤
  │                                                  │
youtube ─ (import config, runtime, db) ─────────────┤
  │                                                  │
podcast ─ (import config, runtime, db, youtube, ────┤
           cover)                                    │
  │                                                  │
pipeline ─ (import all above) ──────────────────────┘
```

**无循环依赖**：所有依赖方向均为单向（Layer 0 → 1 → 2 → 3 → 4）。

---

## 附录：快速检查清单

- [ ] `POSTGRES_DSN` 已填写且可从 Colab 访问
- [ ] 6 张核心表已在 VPS 上建好
- [ ] YouTube OAuth 已写入 `youtube_credentials`
- [ ] ModelScope Token 已写入 `modelscope_tokens`（或本地填写）
- [ ] `OUTPUT_ROOT` 建议设为 Google Drive 路径（避免断连丢文件）
- [ ] 先用 1 本书做 smoke test（`MAX_PROCESS_COUNT=1`）
- [ ] 验证通过后再开启 `ENABLE_COVER_GENERATION`、`ENABLE_SEO_GENERATION`、`ENABLE_YOUTUBE_UPLOAD`