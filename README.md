# 思维课程数据看板 Streamlit 部署包

启动命令：

```bash
streamlit run dashboard.py
```

入口文件：

```text
dashboard.py
```

说明：

- 这个包用于云端长期部署 Streamlit 原版看板。
- 已排除 `.env`、`auth_state.json`、`venv`、日志和自动化脚本。
- 当前数据是本地快照，来自 `data/latest.json` 和根目录的分析 JSON 文件。
