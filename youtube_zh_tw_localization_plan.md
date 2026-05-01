# 简体频道补充繁体标题/简介方案

## 背景与目标

- 当前频道的默认 YouTube 标题和简介使用简体中文。
- 本次目标是在不改变现有简体主文案的前提下，额外补充一个繁体中文版本。
- 默认语言固定为 `zh-CN`，新增繁体本地化版本使用 `zh-TW`。
- 覆盖范围包括新上传视频、历史视频、新建播放列表和历史播放列表。

## 可行性结论

- YouTube Data API 原生支持视频和播放列表的多语言标题/简介。
- 默认语言通过 `snippet.defaultLanguage` 指定。
- 繁体标题和简介通过 `localizations["zh-TW"]` 写入。
- 当前仓库的主要改造点不在 API 能力，而在本地元数据结构、上传请求体和历史回填脚本。

## 实施方案

### 1. 默认语言与本地化策略

- 默认语言保持为 `zh-CN`。
- 新增一个繁体中文版本：`zh-TW`。
- 简体仍然写入 `snippet.title` 和 `snippet.description`。
- 繁体版本写入 `localizations["zh-TW"] = { "title": "...", "description": "..." }`。

### 2. 繁体文案来源

- 采用自动简繁转换生成繁体版本，不新增第二套 AI 翻译流程。
- 推荐使用纯 Python 的 OpenCC 实现，例如 `opencc-python-reimplemented`。
- 默认先用稳定的简转繁规则，不做地区化词汇改写。
- `tags`、URL、时间轴、链接等内容保持原样，不参与简繁转换。

### 3. 新上传视频

- 在视频上传时，直接把简体和繁体一起写入 YouTube。
- 上传请求体需要包含：
  - `snippet.title`
  - `snippet.description`
  - `snippet.defaultLanguage = "zh-CN"`
  - `localizations["zh-TW"]`
- 这样可以避免上传后再单独执行一次元数据回填。

### 4. 播放列表同步

- 新建或更新播放列表时，同样写入：
  - `snippet.title`
  - `snippet.description`
  - `snippet.defaultLanguage = "zh-CN"`
  - `localizations["zh-TW"]`
- 分 P 后的 playlist 排序与视频增删逻辑保持原状，只扩展元数据字段。

### 5. 本地数据结构

- 当前单语言 SEO 数据需要升级为“默认语言 + 本地化映射”结构。
- 推荐结构：

```json
{
  "defaultLanguage": "zh-CN",
  "title": "简体标题",
  "Description": "简体简介",
  "label": "#标签",
  "localizations": {
    "zh-TW": {
      "title": "繁體標題",
      "description": "繁體簡介"
    }
  }
}
```

- `seo_description.json`、split state、上传回执统一使用这套结构，避免单视频与 playlist 的语言数据不一致。

## 历史资源回填

- 需要补齐频道里已经存在的视频和播放列表。
- 建议新增一个一次性回填脚本或 notebook 单元，处理流程如下：
  - 列出频道自有视频和自有播放列表。
  - 读取现有简体标题和简介。
  - 自动转换出繁体版本。
  - 如果资源缺少 `zh-TW`，则写回 `localizations["zh-TW"]`。
- 对视频：
  - 先 `videos.list(part="snippet,localizations,status")`
  - 再 merge 后执行 `videos.update(part="snippet,localizations,status")`
- 对播放列表：
  - 先 `playlists.list(part="snippet,localizations,status", mine=true)`
  - 再 merge 后执行 `playlists.update(part="snippet,localizations,status")`
- 已存在 `zh-TW` 的资源默认跳过，避免覆盖人工调整过的繁体文案。

## 测试要点

- 新上传视频后，确认 `defaultLanguage` 为 `zh-CN`，且能读取到 `localizations.zh-TW`。
- 新建播放列表后，确认 playlist 同样包含 `zh-TW` 本地化。
- 对历史视频和历史播放列表执行回填后，确认未丢失原有简体主文案。
- 重复执行回填任务时，应保持幂等，避免重复覆盖已有 `zh-TW` 内容。
- 检查简繁转换后：
  - 中文字符正确转为繁体
  - emoji 不丢失
  - URL 不变
  - 时间轴文本格式不被破坏

## 结论

- 该方案实现成本中等，但技术路径明确。
- 对当前项目来说，重点是补齐元数据结构、上传请求体和历史资源回填，而不是解决 API 可用性问题。
- 先支持 `zh-CN + zh-TW` 这一组固定语言即可，后续如需扩展更多语言，再把本地化结构推广为通用方案。
