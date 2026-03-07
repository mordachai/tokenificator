# RPG Token Processor

A local Python script that turns portrait images into clean, Foundry VTT-ready tokens — no subscriptions, no uploads, fully offline after the first run.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

1. **Removes the background** from any portrait image using an AI model ([rembg](https://github.com/danielgatis/rembg))
2. **Scales** the result to a 1024×1024 transparent canvas
3. **Applies an arc mask** — a 682px circle with the SE quarter (3 → 6 o'clock) cut away, leaving room for Foundry's token UI elements (HP bar, condition icons, etc.)

### Mask shape

```
        12
    ┌───●───┐
    │  ###  │
  9 ●  ###  ●  ← kept (¾ circle)
    │  ###  │
    └───────┘
          6
     3──────6  ← this quarter is transparent
```

The output is a `.png` with transparency, ready to use as a Foundry VTT token portrait.

---

## Requirements

- Python 3.10+
- pip

---

## Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/rpg-token-processor.git
cd rpg-token-processor

# Install dependencies
pip install rembg pillow
```

> **First run note:** `rembg` will automatically download its AI segmentation model (~100 MB). This happens once and is cached locally.

---

## Usage

```bash
# Output saved as <input>_token.png in the same folder
python token_processor.py portrait.jpg

# Specify a custom output path
python token_processor.py portrait.jpg tokens/my_character.png
```

### Example

```
Input:   wizard_portrait.jpg   (any size, any background)
Output:  wizard_portrait_token.png  (1024×1024, transparent BG, arc mask)
```

---

## Output specs

| Property | Value |
|---|---|
| Canvas size | 1024 × 1024 px |
| Mask shape | Circle, 682px diameter |
| Cutout | SE quarter (3 o'clock → 6 o'clock) |
| Format | PNG (RGBA) |

---

## Foundry VTT usage

1. Run the script on your portrait images
2. Place the output `.png` files in your Foundry `Data/` folder (or any accessible path)
3. Assign them as token images — the transparent SE corner keeps HP bars and status icons clear of the subject's face

---

## License

MIT — free to use, modify, and distribute.
