"""Build game-format translations for the character appearance setting."""
from pathlib import Path
import argparse

LABELS = {
    "de": ("Figurenstil", "Original", "Kleine Pandas"),
    "en": ("Character style", "Original", "Red pandas"),
    "es": ("Estilo de los personajes", "Original", "Pandas rojos"),
    "fr": ("Apparence des personnages", "Originale", "Pandas roux"),
    "it": ("Aspetto dei personaggi", "Originale", "Panda rossi"),
    "ja": ("キャラクターの外見", "オリジナル", "レッサーパンダ"),
    "ko": ("캐릭터 외형", "기본", "레서판다"),
    "pt-br": ("Aparência dos personagens", "Original", "Pandas-vermelhos"),
    "ru": ("Облик персонажей", "Оригинальный", "Малые панды"),
    "s-cn": ("角色外观", "原版", "小熊猫"),
    "t-cn": ("角色外觀", "原版", "小熊貓"),
}


def build(source, output):
    files = sorted(source.glob("*.localization"))
    if not files or source.resolve() == output.resolve():
        raise ValueError("Expected game strings and a separate output directory")
    merged = {}
    for path in files:
        data = path.read_bytes()
        lines = data.decode("utf-8-sig").splitlines()
        if "`menu_graphics" not in lines:
            raise ValueError(f"Missing graphics menu in {path.name}")
        title, original, panda = LABELS[path.stem]
        separator = "：" if path.stem in ("s-cn", "t-cn", "ja") else " : " if path.stem == "fr" else ": "
        additions = []
        for style, label in (("original", original), ("panda", panda)):
            key = "`red_panda_character_style_" + style
            if key in lines:
                raise ValueError(f"Duplicate {key} in {path.name}")
            additions.extend((key, title + separator + label, ""))
        newline = "\r\n" if b"\r\n" in data else "\n"
        merged[path.name] = data + (newline * 2 + newline.join(additions)).encode("utf-8")
    output.mkdir(parents=True, exist_ok=True)
    for name, data in merged.items():
        (output / name).write_bytes(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.source, args.output)
