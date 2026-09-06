"""Verify the generated Wonderland 16x16 sprite package.

This checks the machine-facing invariants that are easy to break while
editing a source atlas: frame sizes, binary alpha, palette indices, layer
composition, and atlas row/column order.
"""
from pathlib import Path
import json
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
DIRS = ["front", "left", "back", "right"]
HEADS = [f"M{i}" for i in range(1, 5)] + [f"F{i}" for i in range(1, 9)]
BODIES = ["B1", "B2"]
MATERIALS = {
    "skin": {3, 4, 5},
    "hair": {6, 7, 8},
    "top": {9, 10, 11},
    "bottom": {12, 13, 14},
    "leather": {15, 16, 17},
}


def fail(message):
    raise AssertionError(message)


def png_ids(path):
    image = Image.open(path).convert("RGBA")
    if image.size != (16, 16):
        fail(f"{path}: expected 16x16, got {image.size}")
    rgba = np.asarray(image)
    alpha = rgba[..., 3]
    if not np.isin(alpha, [0, 255]).all():
        fail(f"{path}: alpha is not binary")
    if np.any((alpha == 0) & np.any(rgba[..., :3] != 0, axis=-1)):
        fail(f"{path}: transparent pixels carry RGB data")
    colors = set(map(tuple, rgba[alpha > 0, :3]))
    palette = set(tuple(bytes.fromhex(x[1:])) for x in DATA["palette"][1:])
    if not colors <= palette:
        fail(f"{path}: colors outside sprites.json palette: {colors - palette}")
    index_by_rgb = {tuple(bytes.fromhex(x[1:])): i for i, x in enumerate(DATA["palette"])}
    ids = np.zeros((16, 16), dtype=np.uint8)
    for rgb, index in index_by_rgb.items():
        ids[np.all(rgba[..., :3] == rgb, axis=-1) & (alpha > 0)] = index
    if np.any((alpha > 0) & (ids == 0)):
        fail(f"{path}: opaque pixel has no palette index")
    return ids


def compose(head, body):
    rear = np.asarray(head["rear"], dtype=np.uint8)
    torso = np.asarray(body, dtype=np.uint8)
    front = np.asarray(head["front"], dtype=np.uint8)
    result = rear.copy()
    result[torso > 0] = torso[torso > 0]
    result[front > 0] = front[front > 0]
    return result


def check_matrix(matrix, label):
    if len(matrix) != 16 or any(len(row) != 16 for row in matrix):
        fail(f"{label}: expected a 16x16 matrix")
    values = {int(value) for row in matrix for value in row}
    if not values <= set(range(len(DATA["palette"]))):
        fail(f"{label}: invalid palette indices {values - set(range(len(DATA['palette'])))}")


DATA = json.loads((ASSETS / "sprites.json").read_text(encoding="utf-8"))


def main():
    assert DATA["version"] == 1
    assert DATA["frame"] == [16, 16]
    assert DATA["directions"] == DIRS
    assert DATA["layer_order"] == ["rear", "body", "front"]
    assert DATA["materials"] == {key: sorted(values) for key, values in MATERIALS.items()}
    assert set(DATA["heads"]) == set(HEADS)
    assert set(DATA["bodies"]) == set(BODIES)

    for head in HEADS:
        for direction in DIRS:
            frame = DATA["heads"][head]["frames"][direction]
            check_matrix(frame["rear"], f"head {head} {direction} rear")
            check_matrix(frame["front"], f"head {head} {direction} front")
            for layer in ("rear", "front"):
                actual = png_ids(ASSETS / "heads" / head / f"{direction}_{layer}.png")
                if not np.array_equal(actual, frame[layer]):
                    fail(f"{head}/{direction}/{layer}: PNG and matrix disagree")
            face = np.asarray(frame["front"])
            eye_y, eye_x = np.where(face == 2)
            expected_eyes = 0 if direction == "back" else 2 if direction == "front" else 1
            if len(eye_x) != expected_eyes:
                fail(f"{head}/{direction}: expected {expected_eyes} eye pixels, got {len(eye_x)}")
            if direction == "front" and (eye_y[0] != eye_y[1] or eye_x[1]-eye_x[0] < 2):
                fail(f"{head}: front eyes must be level and separated")

    for body in BODIES:
        for direction in DIRS:
            frame = DATA["bodies"][body]["frames"][direction]
            check_matrix(frame, f"body {body} {direction}")
            if not np.array_equal(png_ids(ASSETS / "bodies" / body / f"{direction}.png"), frame):
                fail(f"{body}/{direction}: PNG and matrix disagree")

    atlas = np.asarray(Image.open(ASSETS / "characters-atlas.png").convert("RGBA"))
    if atlas.shape[:2] != (16 * 24, 16 * 4):
        fail(f"characters-atlas.png: expected 64x384, got {atlas.shape[1]}x{atlas.shape[0]}")

    count = 0
    for head_index, head in enumerate(HEADS):
        for body_index, body in enumerate(BODIES):
            row = head_index * 2 + body_index
            for direction_index, direction in enumerate(DIRS):
                expected = compose(
                    DATA["heads"][head]["frames"][direction],
                    DATA["bodies"][body]["frames"][direction],
                )
                path = ASSETS / "composed" / f"{head}_{body}" / f"{direction}.png"
                actual = png_ids(path)
                if not np.array_equal(actual, expected):
                    fail(f"{path}: PNG does not match sprites.json layer composition")
                atlas_cell = png_ids_from_rgba(atlas[ row * 16 : (row + 1) * 16,
                                                      direction_index * 16 : (direction_index + 1) * 16 ])
                if not np.array_equal(atlas_cell, expected):
                    fail(f"characters-atlas.png: wrong cell at row {row}, direction {direction}")
                if not np.any(actual):
                    fail(f"{path}: empty composite")
                count += 1

    print(f"OK: {count} composites, {len(HEADS) * len(DIRS) * 2} head layers, {len(BODIES) * len(DIRS)} body frames")


def png_ids_from_rgba(rgba):
    alpha = rgba[..., 3]
    if not np.isin(alpha, [0, 255]).all():
        fail("atlas: alpha is not binary")
    index_by_rgb = {tuple(bytes.fromhex(x[1:])): i for i, x in enumerate(DATA["palette"])}
    ids = np.zeros(alpha.shape, dtype=np.uint8)
    for rgb, index in index_by_rgb.items():
        ids[np.all(rgba[..., :3] == rgb, axis=-1) & (alpha > 0)] = index
    if np.any((alpha > 0) & (ids == 0)):
        fail("atlas: opaque pixel has no palette index")
    return ids


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, KeyError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
