# Prompt Cleaner Studio v1.0.0

Windows 桌面提示詞工具，提供提示詞淨化、圖片生成資訊檢視與批次移除中繼資料。支援繁體中文／English、深色／淺色介面。

## 下載 Windows 版

[下載 v1.0.0（Windows x64 ZIP）](https://github.com/kekinai30108/PromptCleanerStudio/releases/download/v1.0.0/PromptCleanerStudio-v1.0.0-windows-x64.zip)

解壓縮後執行 `PromptCleanerStudio.exe`，不需要安裝 Python。
壓縮檔內含 EXE 與授權文件；再次散布時請保留授權文件。
此版本尚未進行程式碼簽章。

[發布說明與所有下載檔案](https://github.com/kekinai30108/PromptCleanerStudio/releases/tag/v1.0.0) · [最新發布版](https://github.com/kekinai30108/PromptCleanerStudio/releases/latest)

## 功能

- 提示詞淨化：黑名單、去重、移除 LoRA／LyCORIS、強調權重、中文字元及尾端計數；支援複製與匯出 TXT。
- 圖片資訊：解析 PNG、JPEG、WebP 中可辨識的 A1111／ComfyUI 提示詞、模型、LoRA 與生成參數。
- 圖片預覽：等比例置中，點擊預覽即可重新選擇圖片，支援本機及網頁圖片拖放。
- 批次清理：在來源資料夾的 Cleaned_Output 建立乾淨 PNG 副本，不覆寫來源或既有輸出。
- 圓角介面、繁英與深淺色切換按鈕、文字右鍵選單。

## 安裝與執行

需要 Windows x64 與 Python 3.12（含 Tcl/Tk）。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

本機功能不需要網路；安裝套件與從網址載入圖片時需要網路。

## 使用方式與限制

淨化頁貼上提示詞、選取規則後，按「執行淨化」或 Ctrl+Enter。黑名單以逗號或換行分隔，完整標籤比對並忽略大小寫與底線／空白差異。保留首次出現順序，BREAK 與 AND 保留每次出現。歷史及草稿只保存在記憶體，關閉前請匯出重要內容。

圖片頁按「選擇圖片」、點擊預覽，或拖入圖片。JPEG／WebP 支援可辨識的 EXIF UserComment、ImageDescription 與 comment；結果取決於圖片實際保留的資料。ComfyUI 依節點型別與名稱分類，未完整追蹤節點連線。每個顯示區最多 24,000 字元與 16 筆，原始資料複製上限為 1 MiB。大型 workflow 不直接渲染至結果欄。

網頁拖放接受 HTTP(S) 圖片網址，最多 25 MiB，不攜帶瀏覽器 Cookie。來源可能只有縮圖或已移除中繼資料；不支援 blob/data 網址與需登入的圖片。

批次功能只支援靜態 PNG／JPEG／WebP，移除 EXIF、PNG 文字、生成參數及 ICC，先套用 EXIF Orientation 並保留透明度。16-bit、灰階與 CMYK 會轉為 8-bit RGB／RGBA；移除 ICC 可能影響色彩顯示。不能移除像素內的文字、浮水印或隱寫內容。

## 設定

- 原始碼執行：專案目錄的 `settings.json`。
- EXE 執行：`%LOCALAPPDATA%\PromptCleanerStudio\settings.json`。

保存黑名單、規則、語言與主題，不保存原始圖片或提示詞草稿。使用原子寫入與備份，備份檔可能逐次增加，可自行整理。個人設定及舊版程式已排除於版本控制。

## 測試

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe tests\smoke_ui.py
```

UI 測試需要可互動的 Windows 桌面，會短暫顯示測試視窗。

## 建置 EXE

```powershell
.\.venv\Scripts\python.exe build_compact.py
```

輸出為 `release_compact/PromptCleanerStudio.exe`，使用 PyInstaller 單檔視窗模式，啟動時會解壓至系統暫存目錄。建置環境版本見 `requirements-build-lock.txt`。發布 EXE 時須附上實際內含元件的授權文字，詳見 [第三方元件告知](THIRD_PARTY_NOTICES.md)。

## 專案結構

```text
app.py                  三頁介面與背景工作
core.py                 提示詞解析與淨化
metadata_parser.py      生成資訊解析
metadata_remover.py     建立乾淨 PNG 副本
image_source.py         拖放與圖片載入
settings.py             設定驗證與保存
theme.py                深淺配色
widgets.py              圓角控制項
window_chrome.py        Windows 視窗控制
assets/                 應用程式圖示
tests/                  單元與介面測試
build_compact.py        EXE 建置
```

## 作者與授權

Copyright (c) 2026 [kekinai30108](https://github.com/kekinai30108)。
本專案程式碼與作者自製圖示採用 [MIT License](LICENSE)，第三方元件保留各自授權。
部分程式碼及介面實作使用 OpenAI Codex 協助開發。
