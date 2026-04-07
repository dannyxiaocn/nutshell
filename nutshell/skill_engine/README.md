# nutshell/skill_engine

一句话定位：负责从磁盘加载 skill 并把 skill 集合渲染成 Agent 可消费的 prompt 片段。

## 文件列表
- `__init__.py`：导出 `SkillLoader` 与 `build_skills_block`。
- `loader.py`：加载 `SKILL.md` / 兼容旧式单文件 `.md`，解析 YAML frontmatter。
- `renderer.py`：把 skills 渲染为 system prompt block，支持 progressive disclosure。

## 关键设计 / 架构说明
- 优先使用目录式 skill：`skills/<name>/SKILL.md`；同时兼容历史平铺 `skills/<name>.md`。
- frontmatter 与正文分离：`name`、`description` 用于目录与激活，正文在真正加载后再注入。
- skill 分为两类：
  - 文件型 skill：只在 prompt 中注入目录项，模型按需调用 `load_skill` 再读取全文。
  - 内联 skill：直接把正文写进 prompt。
- 这种 progressive disclosure 设计减少默认 prompt 体积，适合 skill 数量较多的实体。

## 主要对外接口
### `class SkillLoader`
```python
from pathlib import Path
from nutshell.skill_engine import SkillLoader

loader = SkillLoader()
skill = loader.load(Path('skills/reasoning'))
skills = loader.load_dir(Path('skills'))
```
- `load(path)`：加载单个目录式或单文件 skill。
- `load_dir(directory)`：按目录顺序加载整个 skill 目录。

### `build_skills_block(skills)`
```python
from nutshell.skill_engine import build_skills_block
prompt_block = build_skills_block(skills)
```
作用：把 `list[Skill]` 渲染成 system prompt 片段。

## 与其他模块的依赖关系
- 依赖 `nutshell.core.skill.Skill` 与 `nutshell.core.loader.BaseLoader`。
- 被 `nutshell.runtime.session.Session` 调用，用于从 session `core/skills/` 载入能力。
- 被 `nutshell.core.agent.Agent` 调用，通过 `renderer.build_skills_block()` 将 skills 注入 prompt。
- 与 `entity/`、`sessions/*/core/skills/` 的文件布局直接对应。
