# Windows 兼容性

> 2026-10-30，Windows 11 + Python 3.11.9（控制台 cp936）实测。

## 这次修了什么

| 问题 | 位置 | 修法 |
|---|---|---|
| 配置带 UTF-8 BOM 时读不了（记事本另存 JSON 默认带 BOM） | `pick.py` / `recall.py` / `bump.py` / `extract.py` | 读配置统一 `utf-8-sig` |
| Windows 写 `resident.md` 是 CRLF，文件字数比打印的多 | `pick.py` | 写入时 `newline="\n"`，统一 LF |
| 子进程输出按 locale 解码，`PYTHONIOENCODING=utf-8` 时会崩 | `tests/smoke.py` | `subprocess.run(..., encoding="utf-8", errors="replace")` |
| `/tmp` 在 Windows 上不存在 | `README.md` | 增加 PowerShell 段（`$env:TEMP`） |
| `python3` 常指向 Microsoft Store 占位符 | `README.md` | 增加说明 |

更早的提交里已修：`gen-corpus.py` 的占位符错填/噪声被追加/时区不稳，`recall.py` 只认中文二元组与空标题，`extract.py` 的 zip 后缀大小写与缺失 jsonl。

## 验证

```bash
python tests/smoke.py
```

三平台都应输出 `[ok] 三步跑通：300 条 → 常驻 542 字`，exit 0。

CI 建议用矩阵跑 `tests/smoke.py`：ubuntu / windows / macos 各一遍，并额外跑一次 `PYTHONIOENCODING=utf-8`。

## 注意

- Windows 上 `/tmp` 会解析成「当前盘符根目录 + tmp」；不存在就先建，或改用 `$env:TEMP`。
- 常驻文件统一 LF；贴进别处不会被换行符搞乱字数。
- 配置里的路径在 Windows 上要用双反斜杠（JSON）或正斜杠。
