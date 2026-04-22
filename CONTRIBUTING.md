# 贡献指南

感谢你改进 Personal Execution Library。

## 开发环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp pelib.example.toml pelib.toml
```

编辑 `pelib.toml`，让 `wiki_root` 指向本地测试目录。

## 校验

运行 Python 测试：

```bash
python3 -m unittest discover -s tests -v
```

如果改动了 `llm-wiki-skill` 的 web 或插件代码，也请在对应子项目执行 npm 构建。

## 卫生规范

- 不要提交个人 wiki 内容、本地配置、虚拟环境、`node_modules` 或构建产物。
- 不要在仓库中提交用户机器专属路径。
- 保留 `third_party_licenses/` 下的第三方归属声明。
