"""Bind raster evidence to its source chapter, SVG and PNG bytes."""
import hashlib
import json
from pathlib import Path


def source_key(chapter, root):
    path = Path(chapter)
    path = (Path(root) / path).resolve()
    try:
        return path.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return "external/" + hashlib.sha256(str(path).encode()).hexdigest() + "/" + path.name


def proof_directory(chapter, root, output_root):
    return Path(output_root) / Path(source_key(chapter, root)).with_suffix("")


def proof_matches(chapter, figure_id, svg_hash, root, output_root):
    directory = proof_directory(chapter, root, output_root)
    try:
        proof = json.loads((directory / (figure_id + ".json")).read_text(encoding="utf-8"))
        png = directory / (figure_id + ".png")
        return (proof.get("source") == source_key(chapter, root)
                and proof.get("figure_id") == figure_id
                and proof.get("svg_sha256") == svg_hash
                and proof.get("png") == png.name
                and proof.get("png_sha256") == hashlib.sha256(png.read_bytes()).hexdigest())
    except (OSError, ValueError, TypeError, AttributeError):
        return False
