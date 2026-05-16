# uwispr (Flow)

Local voice dictation for **macOS**. Hold a hotkey, speak, release — text is pasted into the active app. No cloud; uses [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) on Apple Silicon (GPU/Metal).

## Requirements

- macOS 13+, **Apple Silicon** (M1–M4)
- Python 3.11+ (3.12 recommended)
- ~1.5 GB disk for the default model (downloaded once)

## Install & run

```bash
git clone https://github.com/sigayyury-ai/uwispr.git
cd uwispr

chmod +x scripts/*.sh
./scripts/install.sh
./scripts/run.sh
```

Stop before starting again (avoids duplicate menu bar icons):

```bash
./scripts/stop.sh
```

First launch downloads the Whisper model (1–2 minutes).

## Usage

1. Focus any text field.
2. Hold **Right Option** (~1–2 s), speak, release.
3. Text is inserted via clipboard + ⌘V.

Language: `auto` in `config.toml` (default), or set `ru`, `en`, etc.

## macOS permissions

**System Settings → Privacy & Security**

- **Microphone** — for Terminal / Cursor (where you run the app)
- **Accessibility** — enable **Python** and your terminal app (required for paste)

Check: menu bar mic icon → **Check permissions**.

## Config (`config.toml`)

| Key | Default | Notes |
|-----|---------|--------|
| `mlx_model` | `whisper-medium-mlx` | `small` = faster, `large-v3-turbo` = best quality |
| `language` | `auto` | or `ru`, `en`, … |
| `hotkey` | `right_option` | also `left_option`, `f5` |
| `glossary` | `glossary.txt` | terms + `wrong => right` fixes |

**Glossary example:**

```text
TryGo
whisper => Whisper
```

Menu → **Reload glossary** after edits.

## Autostart

```bash
./scripts/install-autostart.sh    # enable
./scripts/uninstall-autostart.sh  # disable
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Multiple menu icons | `./scripts/stop.sh` |
| Stuck on “Transcribing…” | Menu → **Reset stuck state** |
| No paste | Add **Python** under Accessibility |
| Slow | Use `whisper-small-mlx` in config |

Logs: `tail -f flow.log`

## Privacy

Audio stays on your Mac. Only the model weights are fetched from Hugging Face on first run.

## License

MIT — see [LICENSE](LICENSE). Whisper weights: see [OpenAI Whisper](https://github.com/openai/whisper) (MIT).
