# 贡献指南

感谢你考虑改进 llm-wiki。

## 开发环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

或者直接用 `python3 -m pelib.cli`,无需安装。

## 本地配置

```bash
cp pelib.example.toml pelib.toml
```

把 `wiki_root` 指向一个本地测试目录(默认是仓库同级的 `../LLM-WIKI Vault`)。

## 跑测试

```bash
python3 -m unittest discover -s tests -v
```

## 风格

- 不引入第三方依赖,只用 Python 3.11+ 的标准库。
- 模块边界清晰:`config / wiki / frontmatter / log / markdown / skill / inbox / memory / query / correct / cli`。
- 写新功能时同时写单测。
- 不要把用户本机绝对路径硬编码进仓库。

## 不要提交的东西

- `pelib.toml` 本地配置
- `.pelib/` 生成产物
- `.venv/`
- 任何在仓库内意外创建的 `raw/` / `wiki/` / `site/`
