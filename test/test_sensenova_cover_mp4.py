"""
Sensenova 封面图 + FFmpeg MP4 封装测试脚本
使用"三国冷知识"实际数据验证：
  1. Sensenova 生成 2K 封面图
  2. PIL 自动压缩为 1920x1080 JPEG
  3. FFmpeg 封装 MP4 视频
"""

import os
import sys
import subprocess
import tempfile
import shutil
import json

# 将项目根目录加入路径，以便导入 test.py 中的函数
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 模拟 Colab 运行时所需的全局变量
os.environ["SENSENOVA_BASE_URL"] = "https://token.sensenova.cn/v1"
os.environ["SENSENOVA_API_KEY"] = "sk-8Tr86c17YvA5jBEoem2uYYAQGXGzmpDU"
os.environ["YOUTUBE_PODCAST_IMAGE_MODEL_PRIMARY"] = "sensenova-u1-fast"
os.environ["YOUTUBE_PODCAST_IMAGE_MODEL_RETRIES"] = "3"
os.environ["YOUTUBE_PODCAST_AI_RETRY_BASE_SECONDS"] = "5"
os.environ["REQUEST_TIMEOUT"] = "300"
os.environ["QUIET_RUNTIME_OUTPUT"] = "False"

# =====================================================================
# 测试数据：三国冷知识 - 来自实际运行日志
# =====================================================================
TEST_BOOK_NAME = "三国冷知识"
TEST_BOOK_DESC = (
    "你以为的三国全是假的？99% 的人被演义骗了一辈子！"
    "刘备借荆州真是赖账？周瑜竟被冤枉千年？"
    "诸葛亮老婆其实是大美女？三英战吕布纯属虚构？"
    "本有声书基于正史史料，逻辑严密颠覆你的历史认知！"
)
TEST_AUDIO_PATH = None  # 将在测试中生成或使用模拟音频
TEST_COVER_PATH = None  # 由 Sensenova 生成
TEST_VIDEO_PATH = None  # FFmpeg 封装输出
TEST_RESOLUTION = "1080p"


def _ensure_globals():
    """模拟 Colab 环境所需的 globals() 变量"""
    import __main__
    g = __main__.__dict__
    g["SENSENOVA_BASE_URL"] = os.environ["SENSENOVA_BASE_URL"]
    g["SENSENOVA_API_KEY"] = os.environ["SENSENOVA_API_KEY"]
    g["YOUTUBE_PODCAST_IMAGE_MODEL_PRIMARY"] = os.environ["YOUTUBE_PODCAST_IMAGE_MODEL_PRIMARY"]
    g["YOUTUBE_PODCAST_IMAGE_MODEL_RETRIES"] = int(os.environ["YOUTUBE_PODCAST_IMAGE_MODEL_RETRIES"])
    g["YOUTUBE_PODCAST_AI_RETRY_BASE_SECONDS"] = int(os.environ["YOUTUBE_PODCAST_AI_RETRY_BASE_SECONDS"])
    g["REQUEST_TIMEOUT"] = int(os.environ["REQUEST_TIMEOUT"])
    g["QUIET_RUNTIME_OUTPUT"] = False
    g["API_PRIORITY_ORDER"] = "sensenova"
    return g


def create_silent_test_audio(output_path, duration_seconds=30):
    """用 FFmpeg 生成一段静音测试音频"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
        "-t", str(duration_seconds),
        "-c:a", "libmp3lame", "-b:a", "128k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.exists(output_path):
        print(f"❌ 测试音频生成失败: {result.stderr}")
        return False
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"✅ 测试音频已生成: {output_path} ({size_mb:.2f} MB, {duration_seconds}s)")
    return True


def test_step1_generate_cover_with_sensenova(book_name, book_desc, output_dir):
    """测试步骤 1：使用 Sensenova 生成 2K 封面图 + 自动压缩"""
    print("\n" + "=" * 60)
    print("📌 测试步骤 1：Sensenova 封面图生成 + PIL 压缩")
    print("=" * 60)

    # 从 test.py 导入并执行
    from test import _sensenova_generate_cover_fallback, _call_sensenova_for_draw_prompt

    cover_path = os.path.join(output_dir, f"{book_name}_cover.jpg")

    # 1a. 先生成封面绘图提示词
    print("\n1a. 生成封面绘图提示词...")
    draw_prompt = _call_sensenova_for_draw_prompt(book_name, book_desc)
    if not draw_prompt:
        print("❌ 封面提示词生成失败")
        return None

    # 打印提示词摘要
    prompt_preview = draw_prompt[:80] + "..." if len(draw_prompt) > 80 else draw_prompt
    print(f"✅ 封面提示词生成成功 ({len(draw_prompt)} 字符)")
    print(f"   预览: {prompt_preview}")

    # 1b. 生成封面图片（自动压缩为 1920x1080 JPEG）
    print("\n1b. 生成封面图片（Sensenova 2K → 自动压缩为 1920x1080）...")
    success = _sensenova_generate_cover_fallback(
        output_path=cover_path,
        draw_prompt=draw_prompt,
        resolution="1080p",
    )
    if not success or not os.path.exists(cover_path):
        print("❌ 封面图片生成失败")
        return None

    size_mb = os.path.getsize(cover_path) / 1024 / 1024
    print(f"✅ 封面图片生成成功: {cover_path}")
    print(f"   文件大小: {size_mb:.2f} MB")

    # 检查图片实际尺寸
    try:
        from PIL import Image
        with Image.open(cover_path) as img:
            print(f"   图片尺寸: {img.width}x{img.height}")
            print(f"   图片格式: {img.format}")
    except Exception as e:
        print(f"   ⚠️ 无法读取图片信息: {e}")

    return cover_path


def test_step2_ffmpeg_mux(cover_path, audio_path, output_dir, resolution="1080p"):
    """测试步骤 2：FFmpeg 封面+音频封装为 MP4"""
    print("\n" + "=" * 60)
    print("📌 测试步骤 2：FFmpeg MP4 封装")
    print("=" * 60)

    if not os.path.exists(cover_path):
        print(f"❌ 封面文件不存在: {cover_path}")
        return False
    if not os.path.exists(audio_path):
        print(f"❌ 音频文件不存在: {audio_path}")
        return False

    # 从 test.py 导入 generate_video
    from test import generate_video

    video_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(cover_path))[0]}_final.mp4")

    print(f"   封面: {cover_path} ({os.path.getsize(cover_path)/1024/1024:.2f} MB)")
    print(f"   音频: {audio_path} ({os.path.getsize(audio_path)/1024/1024:.2f} MB)")
    print(f"   分辨率: {resolution}")
    print(f"   输出: {video_path}")
    print()

    success = generate_video(
        audio_path=audio_path,
        image_path=cover_path,
        output_path=video_path,
        resolution=resolution,
    )

    if success and os.path.exists(video_path):
        size_mb = os.path.getsize(video_path) / 1024 / 1024
        print(f"\n✅ MP4 封装成功！")
        print(f"   输出文件: {video_path}")
        print(f"   文件大小: {size_mb:.2f} MB")
        return True
    else:
        print(f"\n❌ MP4 封装失败！")
        return False


def test_step3_compare_raw_vs_compressed(book_name, book_desc, output_dir, audio_path):
    """测试步骤 3（可选）：对比原始 2K 图片 vs 压缩后图片的 FFmpeg 封装效果"""
    print("\n" + "=" * 60)
    print("📌 测试步骤 3（可选）：原始 2K vs 压缩 JPEG 对比测试")
    print("=" * 60)

    print("\n⚠️  此步骤会先生成原始未压缩版本，再生成压缩版本，")
    print("   分别调用 FFmpeg 封装，对比两者的成功/失败情况。")
    print("   注意：这会消耗两次 Sensenova API 调用额度。")
    print()

    choice = input("是否执行对比测试？(y/N): ").strip().lower()
    if choice != "y":
        print("⏭️  跳过对比测试")
        return None

    # 先禁用压缩逻辑：直接调用 download_file 保存原始文件
    print("\n3a. 生成原始 2K 图片（跳过 PIL 压缩）...")
    raw_cover = _generate_raw_sensenova_cover(book_name, book_desc, output_dir)
    if not raw_cover:
        print("❌ 原始 2K 图片生成失败，跳过对比")
        return None

    raw_size_mb = os.path.getsize(raw_cover) / 1024 / 1024
    print(f"   原始图片大小: {raw_size_mb:.2f} MB")

    # 3b. 用压缩方式再生成一张
    print("\n3b. 生成压缩版图片...")
    from test import _sensenova_generate_cover_fallback
    compressed_cover = os.path.join(output_dir, f"{book_name}_cover_compressed.jpg")
    success = _sensenova_generate_cover_fallback(
        output_path=compressed_cover,
        draw_prompt=book_desc,  # fallback prompt
        resolution="1080p",
    )
    if not success:
        print("❌ 压缩版图片生成失败")
        return None

    comp_size_mb = os.path.getsize(compressed_cover) / 1024 / 1024
    print(f"   压缩后大小: {comp_size_mb:.2f} MB")
    print(f"   压缩比: {comp_size_mb/raw_size_mb*100:.1f}%")

    # 3c. 分别封装
    print("\n3c. 原始 2K FFmpeg 封装测试...")
    raw_ok = test_step2_ffmpeg_mux(raw_cover, audio_path, output_dir, TEST_RESOLUTION)

    print("\n3d. 压缩版 FFmpeg 封装测试...")
    comp_ok = test_step2_ffmpeg_mux(compressed_cover, audio_path, output_dir, TEST_RESOLUTION)

    print("\n" + "=" * 60)
    print("📊 对比测试结果")
    print("=" * 60)
    print(f"   原始 2K 图片 ({raw_size_mb:.1f} MB): {'✅ 成功' if raw_ok else '❌ 失败'}")
    print(f"   压缩 JPEG ({comp_size_mb:.1f} MB):  {'✅ 成功' if comp_ok else '❌ 失败'}")

    return {"raw_ok": raw_ok, "compressed_ok": comp_ok, "raw_size_mb": raw_size_mb, "comp_size_mb": comp_size_mb}


def _generate_raw_sensenova_cover(book_name, book_desc, output_dir):
    """生成未经 PIL 压缩的原始 Sensenova 封面图（用于对比测试）"""
    from openai import OpenAI
    from test import download_file, _podcast_error_text, _podcast_ai_retry_sleep_seconds
    import time

    client = OpenAI(
        base_url=str(os.environ["SENSENOVA_BASE_URL"]),
        api_key=str(os.environ["SENSENOVA_API_KEY"]),
    )
    model_name = os.environ["YOUTUBE_PODCAST_IMAGE_MODEL_PRIMARY"]
    retries = int(os.environ["YOUTUBE_PODCAST_IMAGE_MODEL_RETRIES"])

    cover_path = os.path.join(output_dir, f"{book_name}_cover_raw.jpg")

    for attempt in range(retries):
        try:
            response = client.images.generate(
                model=model_name,
                prompt=f"YouTube thumbnail for audiobook '{book_name}': {book_desc}",
                size="2752x1536",
                n=1,
            )
            image_url = str(response.data[0].url or "").strip()
            if not image_url:
                raise ValueError("No URL returned")

            if download_file(image_url, cover_path):
                return cover_path

        except Exception as e:
            print(f"   ⚠️ 第 {attempt+1}/{retries} 次失败: {e}")
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))

    return None


def main():
    print("=" * 60)
    print("🧪 Sensenova 封面图 + FFmpeg MP4 封装测试")
    print(f"   书籍: {TEST_BOOK_NAME}")
    print(f"   时间: 2026-06-17")
    print("=" * 60)

    # 设置全局变量
    _ensure_globals()

    # 输出目录
    output_dir = os.path.join(PROJECT_ROOT, "test", "test_output", "sensenova_cover_test")
    os.makedirs(output_dir, exist_ok=True)

    # 生成测试音频（30 秒静音）
    audio_path = os.path.join(output_dir, "test_audio.mp3")
    if not create_silent_test_audio(audio_path, duration_seconds=30):
        print("❌ 测试音频生成失败，退出。")
        sys.exit(1)

    # 步骤 1：Sensenova 生成封面 + 自动压缩
    cover_path = test_step1_generate_cover_with_sensenova(
        TEST_BOOK_NAME, TEST_BOOK_DESC, output_dir
    )
    if not cover_path:
        print("\n❌ 步骤 1 失败，退出测试。")
        print("   提示：请检查 SENSENOVA_API_KEY 和网络连接。")
        sys.exit(1)

    # 步骤 2：FFmpeg 封装 MP4
    mp4_ok = test_step2_ffmpeg_mux(cover_path, audio_path, output_dir, TEST_RESOLUTION)

    # 步骤 3（可选）对比测试
    test_step3_compare_raw_vs_compressed(
        TEST_BOOK_NAME, TEST_BOOK_DESC, output_dir, audio_path
    )

    # 最终总结
    print("\n" + "=" * 60)
    print("🏁 测试完成")
    print("=" * 60)
    print(f"   输出目录: {output_dir}")
    if os.path.exists(cover_path):
        print(f"   封面文件: {cover_path} ({os.path.getsize(cover_path)/1024/1024:.2f} MB)")
    if mp4_ok:
        video_path = os.path.join(output_dir, f"{TEST_BOOK_NAME}_final.mp4")
        print(f"   视频文件: {video_path} ({os.path.getsize(video_path)/1024/1024:.2f} MB)")
    print()


if __name__ == "__main__":
    main()
