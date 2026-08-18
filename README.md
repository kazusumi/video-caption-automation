# 動画字幕自動化（Windows）

日本語音声を `faster-whisper large-v3` で文字起こしし、4層の装飾字幕を
焼き込んだ MP4 を作成します。入力動画と生成物は Git 管理されません。

## 必要環境

- Windows 10/11
- Python 3.11（64 bit）
- NVIDIA GPUを使う場合は、対応するCUDA/cuDNN
- [FFmpeg](https://www.gyan.dev/ffmpeg/builds/)（`ffmpeg` と `ffprobe` にPATHを通す）
- Dela Gothic One（未インストールならスクリプトが自動取得します）

## セットアップ

PowerShellでリポジトリ直下へ移動し、次を実行します。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

PowerShellでスクリプト実行が禁止されている場合は、先に以下を実行します。

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## 実行

素材をリポジトリ直下へ `input.mkv` として置き、次を実行します。

```powershell
python caption_video.py input.mkv --output-dir output
```

GPUが使えない場合はCPUを指定できます。

```powershell
python caption_video.py input.mkv --output-dir output --device cpu --compute-type int8
```

生成物は `output` に保存されます。

- `transcript_raw.txt`：認識直後の全文
- `transcript_corrected.txt`：用語置換後の全文
- `subtitles_corrected.srt`：通常字幕
- `subtitles_styled.ass`：4層装飾字幕
- `captioned_video.mp4`：字幕焼き込み済み動画

専門用語の自動修正を追加する場合は、`caption_video.py` の
`TERM_CORRECTIONS`へ置換前・置換後の組を追加してください。自動認識には誤りが
残る可能性があるため、最終書き出し前にテキストとSRTを確認してください。

90 MB以上になった場合は、CRFによる初回出力を残さず、目標容量に収まる映像
ビットレートで自動的に再エンコードします。入力素材は変更しません。
