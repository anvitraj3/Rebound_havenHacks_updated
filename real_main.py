import pygame
import random
import os
import math
from player.spritesheet import Spritesheet
import asyncio

pygame.init()

try:
    pygame.mixer.init()
    mixer_ready = True
except pygame.error:
    mixer_ready = False

WIDTH = 1280
HEIGHT = 720
FPS = 60

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("REBOUND")
clock = pygame.time.Clock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "assets", "images")
SOUND_DIR = os.path.join(BASE_DIR, "assets", "sounds")
BACKGROUND_DIR = os.path.join(BASE_DIR, "assets", "backgrounds")
FONT_DIR = os.path.join(BASE_DIR, "assets", "fonts")
HIGH_SCORE_FILE = os.path.join(BASE_DIR, "highscore.txt")

WHITE = (240, 240, 235)
GREEN = (130, 190, 170)
DARK = (24, 25, 28)
YELLOW = (255, 255, 0)
RED = (220, 75, 85)
GOLD = (255, 215, 90)
ORANGE = (235, 140, 60)
PURPLE = (170, 100, 230)

FONT_PATH = os.path.join(FONT_DIR, "Kenney Pixel Square.ttf")
FONT_SCALE = 1.0

SPIKE_IMAGE_PATH = os.path.join(IMAGE_DIR, "spike.png")
MOVING_OBSTACLE_IMAGE_PATH = os.path.join(IMAGE_DIR, "saw2.png")

# Put these three music files in assets/sounds/.
# Change the filenames below to match your actual files.
MUSIC_PATHS = {
    1: os.path.join(SOUND_DIR, "short.ogg"),
    2: os.path.join(SOUND_DIR, "mid.ogg"),
    3: os.path.join(SOUND_DIR, "fast.ogg")
}
MUSIC_VOLUME = 0.4
DEATH_EFFECT_TIME = 1.0
SAW_BLACK_THRESHOLD = 40
SAW_SPIN_SPEED = 360


def resolve_path(path):
    if os.path.isabs(path):
        return path

    return os.path.join(BASE_DIR, path)


def find_file(path):
    full_path = resolve_path(path)

    if os.path.exists(full_path):
        return full_path

    name = os.path.basename(full_path)
    stem = os.path.splitext(name)[0].lower()
    folders = [os.path.dirname(full_path), SOUND_DIR, IMAGE_DIR, FONT_DIR, BASE_DIR]

    for same_name in (True, False):
        for folder in folders:
            if not os.path.isdir(folder):
                continue

            try:
                files = os.listdir(folder)
            except OSError:
                continue

            for filename in files:
                if same_name:
                    match = filename.lower() == name.lower()
                else:
                    match = os.path.splitext(filename)[0].lower() == stem

                if match:
                    found = os.path.join(folder, filename)
                    print(f"Using {found} (asked for {full_path})")
                    return found

    print(f"Could not find file: {full_path}")

    parent = os.path.dirname(full_path)

    if os.path.isdir(parent):
        print(f"That folder exists and contains: {sorted(os.listdir(parent))}")
    else:
        print(f"That folder does not exist: {parent}")

    print(f"The game folder is: {BASE_DIR}")
    return None


def find_font_path():
    if not FONT_PATH:
        return None

    return find_file(FONT_PATH)


font_path = find_font_path()


def make_font(size, bold=False):
    size = max(1, int(size * FONT_SCALE))

    if font_path:
        try:
            return pygame.font.Font(font_path, size)
        except (pygame.error, FileNotFoundError, OSError) as error:
            print(f"Could not load font {font_path}: {error}")

    return pygame.font.SysFont("Arial", size, bold=bold)


if font_path:
    print(f"Using custom font: {font_path}")

title_font = make_font(76, bold=True)
heading_font = make_font(44, bold=True)
font = make_font(26)
small_font = make_font(19)

START_Y = 600
SCORE_DIVISOR = 10
LEVEL_2_SCORE = 200
LEVEL_3_SCORE = 500
WIN_SCORE = 600
LEVEL_BANNER_TIME = 2.0

LEVEL_SETTINGS = {
    1: {
        "gap": (50, 100), "width": (100, 170),
        "spike_every": 5, "moving_every": 0,
        "moving_speed": (80, 120)
    },
    2: {
        "gap": (60, 115), "width": (80, 150),
        "spike_every": 4, "moving_every": 6,
        "moving_speed": (90, 140)
    },
    3: {
        "gap": (70, 125), "width": (70, 120),
        "spike_every": 3, "moving_every": 4,
        "moving_speed": (110, 170)
    },
}

LEVEL_COLORS = {
    1: (35, 35, 55),
    2: (30, 55, 70),
    3: (60, 30, 55),
}

PARALLAX_SPEEDS = (0.15, 0.35, 0.65)

PANEL_ALPHA = 150

state = "menu"
running = True
final_score = 0


def load_high_score():
    try:
        with open(HIGH_SCORE_FILE) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def save_high_score(value):
    try:
        with open(HIGH_SCORE_FILE, "w") as f:
            f.write(str(value))
    except OSError:
        print("Could not save high score.")


high_score = load_high_score()


def draw_text(text, font_type, color, x, y):
    image = font_type.render(text, True, color)
    screen.blit(image, image.get_rect(center=(x, y)))


def make_fallback_layer(layer_number, speed):
    rng = random.Random(layer_number)
    count = 40 - layer_number * 12
    return [
        (
            rng.randint(0, WIDTH),
            rng.randint(0, HEIGHT + 100),
            3 + layer_number * 5
        )
        for _ in range(count)
    ]


def load_backgrounds():
    layers = []

    for number, speed in enumerate(PARALLAX_SPEEDS, start=1):
        filename = f"layer_{number}.png"
        path = os.path.join(BACKGROUND_DIR, filename)

        layer = {"image": None, "speed": speed, "shapes": make_fallback_layer(number - 1, speed)}

        if not os.path.exists(path):
            print(f"Background not found, using shapes instead: {path}")
            layers.append(layer)
            continue

        try:
            image = pygame.image.load(path).convert_alpha()

            scale = WIDTH / image.get_width()
            new_height = max(1, int(image.get_height() * scale))

            layer["image"] = pygame.transform.scale(
                image,
                (WIDTH, new_height)
            )
            print(f"Loaded background {filename} ({WIDTH}x{new_height})")

        except pygame.error as error:
            print(f"Could not load background {filename}: {error}")

        layers.append(layer)

    return layers


background_layers = load_backgrounds()


def draw_background(camera_y, level):
    screen.fill(LEVEL_COLORS[level])

    base = LEVEL_COLORS[level]

    for number, layer in enumerate(background_layers):
        speed = layer["speed"]
        image = layer["image"]

        scroll = -camera_y * speed

        if image is not None:
            image_height = image.get_height()
            y = int(scroll) % image_height - image_height

            while y < HEIGHT:
                screen.blit(image, (0, y))
                y += image_height

        else:
            color = tuple(min(255, c + 25 * (number + 1)) for c in base)

            for x, y, radius in layer["shapes"]:
                screen_y = (y + scroll) % (HEIGHT + 100) - 50
                pygame.draw.circle(screen, color, (x, int(screen_y)), radius)


side_panel_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)


LEFT_SIDE = pygame.Rect(0, 0, 415, HEIGHT)
RIGHT_SIDE = pygame.Rect(870, 0, WIDTH - 870, HEIGHT)


def draw_side_panels(left_side, right_side):
    side_panel_surface.fill((0, 0, 0, 0))
    side_panel_surface.fill((0, 0, 0, PANEL_ALPHA), left_side)
    side_panel_surface.fill((0, 0, 0, PANEL_ALPHA), right_side)
    screen.blit(side_panel_surface, (0, 0))


def load_game_assets():
    idle_spritesheet = Spritesheet(
        os.path.join(IMAGE_DIR, "idle_animation.png")
    )

    idle = [
        idle_spritesheet.parse_sprite(
            f"sprite-animation-frame-{i:03}.png"
        )
        for i in range(1, 12)
    ]

    run_spritesheet = Spritesheet(
        os.path.join(IMAGE_DIR, "run.png")
    )

    run = [
        run_spritesheet.parse_sprite(
            f"sprite-animation (1)-frame-{i:03}.png"
        )
        for i in range(1, 12)
    ]

    jump_image = pygame.image.load(
        os.path.join(IMAGE_DIR, "Jump (32x32).png")
    ).convert_alpha()

    fall_image = pygame.image.load(
        os.path.join(IMAGE_DIR, "Fall (32x32).png")
    ).convert_alpha()

    return idle, run, jump_image, fall_image


idle, run, jump_image, fall_image = load_game_assets()


# Resolve all three tracks once at startup.
music_files = {}
current_music_level = None

if mixer_ready:
    for level, path in MUSIC_PATHS.items():
        music_files[level] = find_file(path)
        if music_files[level]:
            print(f"Level {level} music: {music_files[level]}")


def stop_music():
    global current_music_level

    if mixer_ready:
        pygame.mixer.music.stop()

    current_music_level = None


def start_music(level):
    """Start the looping music track assigned to the requested level."""
    global current_music_level

    if not mixer_ready:
        return

    music_file = music_files.get(level)
    if not music_file:
        print(f"No music file found for level {level}. Check MUSIC_PATHS.")
        current_music_level = level
        return

    # Avoid reloading/restarting the same track every frame.
    if current_music_level == level and pygame.mixer.music.get_busy():
        return

    try:
        pygame.mixer.music.stop()
        pygame.mixer.music.load(music_file)
        pygame.mixer.music.set_volume(MUSIC_VOLUME)
        pygame.mixer.music.play(-1)
        current_music_level = level
    except pygame.error as error:
        print(f"Could not play level {level} music: {error}")
        current_music_level = level


def level_for_score(score):
    if score >= LEVEL_3_SCORE:
        return 3
    if score >= LEVEL_2_SCORE:
        return 2
    return 1


def next_goal_for_level(level):
    if level == 1:
        return LEVEL_2_SCORE
    if level == 2:
        return LEVEL_3_SCORE
    return WIN_SCORE


def load_optional_image(path):
    if not path:
        return None

    full_path = find_file(path)

    if full_path is None:
        return None

    try:
        return pygame.image.load(full_path).convert_alpha()
    except pygame.error as error:
        print(f"Could not load obstacle image {full_path}: {error}")
        return None


def remove_black_background(image, threshold):
    if image is None:
        return None

    longest = max(image.get_size())

    if longest > 256:
        scale = 256 / longest
        image = pygame.transform.smoothscale(
            image,
            (
                max(1, int(image.get_width() * scale)),
                max(1, int(image.get_height() * scale))
            )
        )

    width, height = image.get_size()

    near_black = pygame.mask.from_threshold(
        image,
        (0, 0, 0, 255),
        (threshold, threshold, threshold, 255)
    )

    border = pygame.mask.Mask((width, height))

    for x in range(width):
        border.set_at((x, 0), 1)
        border.set_at((x, height - 1), 1)

    for y in range(height):
        border.set_at((0, y), 1)
        border.set_at((width - 1, y), 1)

    background = pygame.mask.Mask((width, height))

    for component in near_black.connected_components():
        if component.overlap(border, (0, 0)):
            background.draw(component, (0, 0))

    content = background.copy()
    content.invert()
    rects = content.get_bounding_rects()

    if not rects:
        return image

    bounds = rects[0].unionall(rects[1:])

    cutout = background.to_surface(
        setcolor=(0, 0, 0, 0),
        unsetcolor=(255, 255, 255, 255)
    )

    cleaned = image.copy()
    cleaned.blit(cutout, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    cropped = cleaned.subsurface(bounds).copy()

    size = max(bounds.size)
    square = pygame.Surface((size, size), pygame.SRCALPHA)
    square.blit(cropped, cropped.get_rect(center=(size // 2, size // 2)))

    return square


raw_obstacle_images = {
    "spike": load_optional_image(SPIKE_IMAGE_PATH),
    "moving": remove_black_background(
        load_optional_image(MOVING_OBSTACLE_IMAGE_PATH),
        SAW_BLACK_THRESHOLD
    )
}

scaled_obstacle_images = {}


def get_obstacle_image(kind, size):
    raw_image = raw_obstacle_images.get(kind)

    if raw_image is None:
        return None

    key = (kind, size)

    if key not in scaled_obstacle_images:
        scaled_obstacle_images[key] = pygame.transform.smoothscale(raw_image, size)

    return scaled_obstacle_images[key]


def make_obstacle(kind, platform, settings):
    if kind == "spike":
        width = random.randint(25, 40)
        height = 28
    else:
        width = 36
        height = 36

    x = random.randint(platform.left, platform.right - width)

    rect = pygame.Rect(x, platform.top - height, width, height)

    obstacle = {
        "kind": kind,
        "rect": rect,
        "image": get_obstacle_image(kind, (width, height))
    }

    if kind == "moving":
        obstacle["x"] = float(x)
        obstacle["min_x"] = platform.left
        obstacle["max_x"] = platform.right - width
        obstacle["speed"] = random.randint(*settings["moving_speed"])
        obstacle["direction"] = random.choice((-1, 1))
        obstacle["angle"] = random.uniform(0, 360)

    return obstacle


def pick_obstacle_kind(count, platform, settings):
    if count < 3:
        return None

    if settings["spike_every"] and count % settings["spike_every"] == 0:
        return "spike"

    if (
        settings["moving_every"]
        and count % settings["moving_every"] == 0
        and platform.width >= 80
    ):
        return "moving"

    return None


def build_tower():
    platforms = [
        pygame.Rect(640, START_Y, 100, 10)
    ]
    obstacles = []

    previous_y = START_Y
    level_height = LEVEL_2_SCORE * SCORE_DIVISOR

    for level in (1, 2, 3):
        settings = LEVEL_SETTINGS[level]

        top_of_level = START_Y - level * level_height
        if level == 3:
            top_of_level -= 600

        count = 0

        while previous_y > top_of_level:
            vertical_gap = random.randint(*settings["gap"])
            y = previous_y - vertical_gap - 10

            width = random.randint(*settings["width"])
            x = random.randint(420, 870 - width)

            platform = pygame.Rect(x, y, width, 10)
            platforms.append(platform)
            count += 1

            kind = pick_obstacle_kind(count, platform, settings)

            if kind:
                obstacles.append(make_obstacle(kind, platform, settings))

            previous_y = y

    return platforms, obstacles


def create_game():
    gravity = 1200
    jump_strength = 600
    jumps_remaining = 2

    grounded = False

    player_vel = pygame.math.Vector2(0, 0)
    camera_y = 0

    idle_index = 0
    run_index = 0

    idle_timer = 0
    run_timer = 0

    animation_speed = 0.1
    flip_img = False

    player_original = pygame.transform.scale(idle[0], (50, 50))
    player = player_original.copy()

    player_hitbox = player.get_rect()
    player_hitbox.center = (640, 360)

    platforms, obstacles = build_tower()

    return {
        "gravity": gravity,
        "jump_strength": jump_strength,
        "jumps_remaining": jumps_remaining,
        "grounded": grounded,
        "player_vel": player_vel,
        "camera_y": camera_y,
        "idle_index": idle_index,
        "run_index": run_index,
        "idle_timer": idle_timer,
        "run_timer": run_timer,
        "animation_speed": animation_speed,
        "flip_img": flip_img,
        "player_original": player_original,
        "player": player,
        "player_hitbox": player_hitbox,
        "platforms": platforms,
        "obstacles": obstacles,
        "score": 0,
        "level": 1,
        "highest_point": START_Y,
        "level_banner": LEVEL_BANNER_TIME,
        "particles": [],
        "death_timer": 0
    }


game = None


def finish_run(next_state):
    global state, final_score, high_score

    final_score = game["score"]

    if final_score > high_score:
        high_score = final_score
        save_high_score(high_score)

    if next_state == "end":
        start_death_effect()
    else:
        state = next_state


def start_death_effect():
    global state

    hitbox = game["player_hitbox"]
    x = hitbox.centerx
    y = hitbox.centery

    if hitbox.top - game["camera_y"] > HEIGHT:
        y = game["camera_y"] + HEIGHT - 10

    colors = (RED, WHITE, ORANGE, GOLD)

    game["particles"] = [
        {
            "x": x,
            "y": y,
            "vx": random.uniform(-350, 350),
            "vy": random.uniform(-550, 100),
            "life": random.uniform(0.6, 1.0),
            "size": random.randint(4, 9),
            "color": random.choice(colors)
        }
        for _ in range(45)
    ]

    game["death_timer"] = DEATH_EFFECT_TIME

    stop_music()

    state = "dying"


def draw_scene(show_player=True, shake=0):
    camera_y = game["camera_y"]

    if shake:
        camera_y += random.randint(-shake, shake)

    draw_background(camera_y, game["level"])

    for platform in game["platforms"]:
        if -10 <= platform.y - camera_y <= HEIGHT:
            draw_platform(platform, camera_y)

    for obstacle in game["obstacles"]:
        if -40 <= obstacle["rect"].y - camera_y <= HEIGHT:
            draw_obstacle(obstacle, camera_y)

    if show_player:
        player_screen_rect = game["player_hitbox"].copy()
        player_screen_rect.y -= camera_y
        screen.blit(game["player"], player_screen_rect)

    for particle in game["particles"]:
        pygame.draw.rect(
            screen,
            particle["color"],
            (
                particle["x"],
                particle["y"] - camera_y,
                particle["size"],
                particle["size"]
            )
        )

    draw_side_panels(LEFT_SIDE, RIGHT_SIDE)
    draw_scoreboard()
    draw_level_banner()


def update_dying(dt):
    global state

    game["death_timer"] -= dt

    for particle in game["particles"]:
        particle["x"] += particle["vx"] * dt
        particle["y"] += particle["vy"] * dt
        particle["vy"] += 900 * dt
        particle["life"] -= dt

    game["particles"] = [p for p in game["particles"] if p["life"] > 0]

    ratio = max(0.0, game["death_timer"] / DEATH_EFFECT_TIME)

    draw_scene(show_player=False, shake=int(12 * ratio))

    flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    flash.fill((220, 40, 50, int(140 * ratio)))
    screen.blit(flash, (0, 0))

    if game["death_timer"] <= 0:
        state = "end"


def draw_platform(platform, camera_y):
    pygame.draw.rect(
        screen,
        YELLOW,
        (
            platform.x,
            platform.y - camera_y,
            platform.width,
            platform.height
        )
    )


def move_obstacles(obstacles, dt):
    for obstacle in obstacles:
        if obstacle["kind"] != "moving":
            continue

        obstacle["x"] += obstacle["speed"] * obstacle["direction"] * dt

        if obstacle["x"] >= obstacle["max_x"]:
            obstacle["x"] = obstacle["max_x"]
            obstacle["direction"] = -1
        elif obstacle["x"] <= obstacle["min_x"]:
            obstacle["x"] = obstacle["min_x"]
            obstacle["direction"] = 1

        obstacle["rect"].x = int(obstacle["x"])
        obstacle["angle"] = (
            obstacle["angle"] + obstacle["direction"] * SAW_SPIN_SPEED * dt
        ) % 360


def draw_obstacle(obstacle, camera_y):
    rect = obstacle["rect"]
    image = obstacle["image"]

    if image is not None:
        if obstacle["kind"] == "moving":
            rotated = pygame.transform.rotozoom(image, -obstacle["angle"], 1.0)
            center = (rect.centerx, rect.centery - camera_y)
            screen.blit(rotated, rotated.get_rect(center=center))
        else:
            screen.blit(image, rect.move(0, -camera_y))
        return

    kind = obstacle["kind"]

    if kind == "spike":
        points = [
            (rect.left, rect.bottom - camera_y),
            (rect.centerx, rect.top - camera_y),
            (rect.right, rect.bottom - camera_y)
        ]
        pygame.draw.polygon(screen, RED, points)

    else:
        center = (rect.centerx, rect.centery - camera_y)
        radius = rect.width // 2

        pygame.draw.circle(screen, PURPLE, center, radius)
        pygame.draw.circle(screen, WHITE, center, radius, 3)

        for i in range(4):
            spoke = math.radians(obstacle["angle"] + i * 90)
            end = (
                center[0] + math.cos(spoke) * radius,
                center[1] + math.sin(spoke) * radius
            )
            pygame.draw.line(screen, WHITE, center, end, 3)


def draw_scoreboard():
    level = game["level"]
    score = game["score"]
    goal = next_goal_for_level(level)

    draw_text("SCORE", small_font, GREEN, 207, 70)
    draw_text(str(score), title_font, WHITE, 207, 130)

    draw_text(f"LEVEL {level} / 3", heading_font, GOLD, 207, 230)

    if level < 3:
        draw_text(f"Level {level + 1} at {goal} pts", small_font, WHITE, 207, 285)
    else:
        draw_text(f"Win at {goal} pts", small_font, WHITE, 207, 285)

    bar = pygame.Rect(107, 320, 200, 14)
    previous_goal = 0 if level == 1 else next_goal_for_level(level - 1)
    progress = (score - previous_goal) / max(1, goal - previous_goal)
    progress = max(0.0, min(1.0, progress))

    pygame.draw.rect(screen, (60, 60, 70), bar, border_radius=7)
    pygame.draw.rect(
        screen,
        GREEN,
        (bar.x, bar.y, int(bar.width * progress), bar.height),
        border_radius=7
    )

    draw_text("BEST", small_font, GREEN, 207, 410)
    draw_text(str(max(high_score, score)), heading_font, WHITE, 207, 455)


def draw_level_banner():
    if game["level_banner"] <= 0:
        return

    band = pygame.Surface((455, 90), pygame.SRCALPHA)
    band.fill((24, 25, 28, 200))
    screen.blit(band, (415, 150))

    draw_text(f"LEVEL {game['level']}", heading_font, GOLD, 642, 195)


def draw_menu():
    screen.fill(DARK)

    draw_text("REBOUND", title_font, WHITE, 640, 230)
    draw_text("A PLATFORMING CHALLENGE", small_font, GREEN, 640, 295)

    draw_text("PRESS ENTER TO START", font, WHITE, 640, 405)
    draw_text("PRESS H FOR HOW TO PLAY", font, GREEN, 640, 455)
    draw_text("PRESS ESC TO QUIT", small_font, (150, 150, 160), 640, 525)

    draw_text(f"BEST SCORE: {high_score}", small_font, GOLD, 640, 600)


def draw_how_to_play():
    screen.fill(DARK)

    draw_text("HOW TO PLAY", heading_font, WHITE, 640, 120)

    instructions = [
        "A / D or LEFT / RIGHT  - Move",
        "W or UP ARROW  - Jump",
        "Press jump again in the air  - Double jump",
        "Land on platforms to climb higher",
        "The higher you climb, the more points you score",
        f"Reach {LEVEL_2_SCORE} points for level 2, {LEVEL_3_SCORE} for level 3",
        f"Reach {WIN_SCORE} points to win",
        "Avoid spikes and moving hazards",
        "Falling or touching spikes ends the run"
    ]

    for index, instruction in enumerate(instructions):
        draw_text(
            instruction,
            font,
            WHITE,
            640,
            205 + index * 42
        )

    draw_text("PRESS ENTER TO RETURN", small_font, GREEN, 640, 635)


def draw_end_screen():
    screen.fill(DARK)

    draw_text("GAME OVER", title_font, RED, 640, 200)
    draw_text("YOU FELL OR HIT AN OBSTACLE", font, WHITE, 640, 295)

    draw_text(f"SCORE: {final_score}", heading_font, WHITE, 640, 365)
    draw_text(f"BEST: {high_score}", font, GOLD, 640, 415)

    draw_text("PRESS R TO RESTART", font, GREEN, 640, 490)
    draw_text("PRESS ENTER FOR MAIN MENU", font, WHITE, 640, 540)
    draw_text("PRESS ESC TO QUIT", small_font, (150, 150, 160), 640, 605)


def draw_win_screen():
    screen.fill(DARK)

    draw_text("YOU WIN!", title_font, GOLD, 640, 200)
    draw_text(f"YOU REACHED {WIN_SCORE} POINTS", font, WHITE, 640, 295)

    draw_text(f"SCORE: {final_score}", heading_font, WHITE, 640, 365)
    draw_text(f"BEST: {high_score}", font, GOLD, 640, 415)

    draw_text("PRESS R TO PLAY AGAIN", font, GREEN, 640, 490)
    draw_text("PRESS ENTER FOR MAIN MENU", font, WHITE, 640, 540)
    draw_text("PRESS ESC TO QUIT", small_font, (150, 150, 160), 640, 605)


def update_game(dt):
    global game, state

    player_hitbox = game["player_hitbox"]
    player_vel = game["player_vel"]
    platforms = game["platforms"]
    obstacles = game["obstacles"]

    keys = pygame.key.get_pressed()

    left_side = pygame.Rect(0, 0, 415, HEIGHT)
    right_side = pygame.Rect(870, 0, WIDTH - 870, HEIGHT)

    move_x = 0

    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        move_x = -500 * dt
        game["flip_img"] = True

    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        move_x = 500 * dt
        game["flip_img"] = False

    player_hitbox.x += move_x

    if player_hitbox.left < left_side.right:
        player_hitbox.left = left_side.right

    if player_hitbox.right > right_side.left:
        player_hitbox.right = right_side.left

    previous_bottom = player_hitbox.bottom

    player_vel.y += game["gravity"] * dt
    player_hitbox.y += player_vel.y * dt

    game["grounded"] = False

    for platform in platforms:
        if (
            previous_bottom <= platform.top
            and player_hitbox.bottom >= platform.top
            and player_hitbox.right > platform.left
            and player_hitbox.left < platform.right
            and player_vel.y >= 0
        ):
            player_hitbox.bottom = platform.top
            player_vel.y = 0
            game["grounded"] = True
            game["jumps_remaining"] = 2

    move_obstacles(obstacles, dt)

    for obstacle in obstacles:
        if player_hitbox.colliderect(obstacle["rect"]):
            finish_run("end")
            return

    if player_hitbox.top - game["camera_y"] > HEIGHT:
        finish_run("end")
        return

    if player_hitbox.bottom < game["highest_point"]:
        game["highest_point"] = player_hitbox.bottom

    game["score"] = max(
        0,
        int((START_Y - game["highest_point"]) / SCORE_DIVISOR)
    )

    new_level = level_for_score(game["score"])

    if new_level != game["level"]:
        game["level"] = new_level
        game["level_banner"] = LEVEL_BANNER_TIME

    game["level_banner"] = max(0, game["level_banner"] - dt)

    if game["score"] >= WIN_SCORE:
        finish_run("win")
        return

    if player_vel.y < 0:
        game["player_original"] = pygame.transform.scale(
            jump_image,
            (50, 50)
        )

    elif player_vel.y > 0:
        game["player_original"] = pygame.transform.scale(
            fall_image,
            (50, 50)
        )

    elif move_x != 0 and game["grounded"]:
        game["run_timer"] += dt

        if game["run_timer"] >= game["animation_speed"]:
            game["run_index"] = (
                game["run_index"] + 1
            ) % len(run)

            game["run_timer"] = 0

        game["player_original"] = pygame.transform.scale(
            run[game["run_index"]],
            (50, 50)
        )

        game["idle_index"] = 0
        game["idle_timer"] = 0

    else:
        game["idle_timer"] += dt

        if game["idle_timer"] >= game["animation_speed"]:
            game["idle_index"] = (
                game["idle_index"] + 1
            ) % len(idle)

            game["idle_timer"] = 0

        game["player_original"] = pygame.transform.scale(
            idle[game["idle_index"]],
            (50, 50)
        )

        game["run_index"] = 0
        game["run_timer"] = 0

    game["player"] = pygame.transform.flip(
        game["player_original"],
        game["flip_img"],
        False
    )

    camera_target = player_hitbox.centery - 360

    if camera_target < game["camera_y"]:
        game["camera_y"] = camera_target

    draw_scene()


async def main():
    global running, game, state

    while running:
        dt = clock.tick(FPS) / 1000

        # Use the level's track during gameplay; use level 1 music in menus.
        # pygame.mixer.music.play() is non-blocking, so asyncio keeps running.
        if mixer_ready and state in ("menu", "how_to_play", "playing"):
            music_level = game["level"] if state == "playing" and game else 1

            if (
                current_music_level != music_level
                or not pygame.mixer.music.get_busy()
            ):
                start_music(music_level)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:

                if state == "menu":
                    if event.key == pygame.K_RETURN:
                        game = create_game()
                        state = "playing"

                    elif event.key == pygame.K_h:
                        state = "how_to_play"

                    elif event.key == pygame.K_ESCAPE:
                        running = False

                elif state == "how_to_play":
                    if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                        state = "menu"

                elif state == "playing":
                    if event.key in (pygame.K_w, pygame.K_UP):
                        if game["jumps_remaining"] > 0:
                            game["player_vel"].y = -game["jump_strength"]
                            game["jumps_remaining"] -= 1
                            game["grounded"] = False

                    elif event.key == pygame.K_ESCAPE:
                        state = "menu"

                elif state in ("end", "win"):
                    if event.key == pygame.K_r:
                        game = create_game()
                        state = "playing"

                    elif event.key == pygame.K_RETURN:
                        state = "menu"

                    elif event.key == pygame.K_ESCAPE:
                        running = False

        if state == "menu":
            draw_menu()

        elif state == "how_to_play":
            draw_how_to_play()

        elif state == "playing":
            update_game(dt)

        elif state == "dying":
            update_dying(dt)

        elif state == "end":
            draw_end_screen()

        elif state == "win":
            draw_win_screen()

        pygame.display.flip()



asyncio.run(main())
