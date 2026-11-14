
import pygame
import json
import os


class Spritesheet:
    def __init__(self, filename):
        self.filename = filename
        self.spritesheet = pygame.image.load(filename).convert_alpha()
        self.meta_data = os.path.splitext(filename)[0] + ".json"

        with open(self.meta_data) as f:
            self.data = json.load(f)

    def get_sprite(self, x, y, w, h):
        sprite = pygame.Surface((w, h), pygame.SRCALPHA)
        sprite.blit(self.spritesheet, (0, 0), (x, y, w, h))

        for px in range(w):
            for py in range(h):
                color = sprite.get_at((px, py))

                if color.r == 0 and color.g == 0 and color.b == 0 and color.a > 0:
                    sprite.set_at((px, py), (0, 0, 0, 0))

        return sprite

    def parse_sprite(self, name):
        for frame in self.data['frames']:
            if frame['name'] == name:
                sprite = frame['frame']

                x = sprite["x"]
                y = sprite["y"]
                w = sprite["w"]
                h = sprite["h"]

                return self.get_sprite(x, y, w, h)

        raise ValueError(f"Sprite not found: {name}")
